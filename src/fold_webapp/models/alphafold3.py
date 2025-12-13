from __future__ import annotations

import logging
import re
import shlex
import subprocess
from pathlib import Path
from textwrap import dedent
from typing import Any

from fold_webapp.config import get_settings
from fold_webapp.models.base import PredictionModel
from fold_webapp.schemas import Entity, EntityType

logger = logging.getLogger(__name__)


class SlurmSubmissionError(RuntimeError):
    """Raised when Slurm job submission fails."""


_SBATCH_JOB_ID_RE = re.compile(r"Submitted batch job (\d+)")


class AlphaFold3Model(PredictionModel):
    key = "alphafold3"

    def prepare_input(
        self, *, job_name: str, model_seed: int, entities: list[Entity]
    ) -> dict[str, Any]:
        seqs: list[dict[str, Any]] = []
        for ent in entities:
            ids = [chr(ord(ent.id) + i) for i in range(ent.copies)]
            if ent.type == EntityType.protein:
                seqs.append({"protein": {"id": ids, "sequence": ent.seq.strip()}})
            elif ent.type == EntityType.dna:
                seqs.append({"dna": {"id": ids, "sequence": ent.seq.strip()}})
            elif ent.type == EntityType.rna:
                seqs.append({"rna": {"id": ids, "sequence": ent.seq.strip()}})
            else:  # pragma: no cover
                raise ValueError(f"Unsupported entity type: {ent.type}")

        return {
            "name": job_name,
            "dialect": "alphafold3",
            "version": 1,
            "modelSeeds": [model_seed],
            "sequences": seqs,
        }

    def submit_job(self, *, input_path: Path, output_dir: Path, nice: int = 0) -> str | None:
        """Submit an AlphaFold3 job to Slurm.

        Writes a batch script to `{output_dir}/logs/slurm_submit.sh`, submits it via `sbatch`,
        and returns the Slurm job id.
        """
        input_path = input_path.resolve()
        output_dir = output_dir.resolve()

        if not input_path.is_file():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        # Ensure output/log directories exist (JobManager creates job_dir; we ensure logs/)
        log_dir = output_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        job_name = self._sanitize_slurm_job_name(f"af3_{input_path.stem}")

        # Detect "re-run" mode (best-effort; matches legacy af3run behavior)
        is_rerun = input_path.name.endswith("_data.json")

        script_content = self._generate_batch_script(
            input_path=input_path,
            output_dir=output_dir,
            log_dir=log_dir,
            job_name=job_name,
            is_rerun=is_rerun,
            nice=nice,
        )

        script_path = log_dir / "slurm_submit.sh"
        script_path.write_text(script_content)
        script_path.chmod(0o755)

        logger.info(
            "Submitting AF3 job to Slurm: job_name=%s input=%s output=%s",
            job_name,
            input_path,
            output_dir,
        )

        try:
            res = subprocess.run(
                ["sbatch", str(script_path)],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired as e:
            raise SlurmSubmissionError("sbatch timed out after 30 seconds") from e
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "").strip()
            stdout = (e.stdout or "").strip()
            msg = "sbatch failed"
            if stderr or stdout:
                msg = f"{msg}: {stderr or stdout}"
            raise SlurmSubmissionError(msg) from e

        job_id = self._parse_job_id(res.stdout or "")
        logger.info("AF3 job submitted: job_id=%s", job_id)
        return job_id

    def _sanitize_slurm_job_name(self, name: str) -> str:
        # Allow only safe Slurm JobName chars (avoid whitespace/shell metacharacters)
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        return sanitized[:64]

    def _parse_job_id(self, sbatch_stdout: str) -> str:
        m = _SBATCH_JOB_ID_RE.search(sbatch_stdout)
        return m.group(1) if m else sbatch_stdout.strip()

    def _generate_batch_script(
        self,
        *,
        input_path: Path,
        output_dir: Path,
        log_dir: Path,
        job_name: str,
        is_rerun: bool,
        nice: int,
    ) -> str:
        settings = get_settings()

        mode_msg = "FAST MODE (Re-run)" if is_rerun else "SEARCH MODE (New Protein)"
        cpu_flags = (
            ""
            if is_rerun
            else f"--jackhmmer_n_cpu={settings.slurm_cpus} --nhmmer_n_cpu={settings.slurm_cpus}"
        )

        # Quote runtime args (paths) that are used in shell command context
        input_q = shlex.quote(str(input_path))
        out_q = shlex.quote(str(output_dir))
        run_script_q = shlex.quote(settings.af3_run_script)
        model_dir_q = shlex.quote(settings.af3_model_dir)
        db_dir_q = shlex.quote(settings.af3_db_dir)
        mamba_root_q = shlex.quote(settings.af3_mamba_prefix)
        mamba_exe_q = shlex.quote(settings.af3_mamba_exe)
        conda_env_q = shlex.quote(settings.af3_conda_env)
        jax_cache_q = shlex.quote(settings.jax_cache_dir)

        # Note: #SBATCH directive values are parsed by sbatch; keep them unquoted.
        script = dedent(
            f"""\
            #!/bin/bash
            #SBATCH --job-name={job_name}
            #SBATCH --output={log_dir}/%x_%j.out
            #SBATCH --error={log_dir}/%x_%j.err
            #SBATCH --partition={settings.slurm_partition}
            #SBATCH --nice={int(nice)}
            #SBATCH --nodes=1
            #SBATCH --ntasks=1
            #SBATCH --cpus-per-task={settings.slurm_cpus}
            #SBATCH --gres={settings.slurm_gpu}
            #SBATCH --mem={settings.slurm_mem}
            #SBATCH --time={settings.slurm_time}

            set -euo pipefail

            echo "=========================================="
            echo "Job ID:    $SLURM_JOB_ID"
            echo "Node:      $SLURMD_NODENAME"
            echo "Start:     $(date)"
            echo "Mode:      {mode_msg}"
            echo "=========================================="

            # --- ENVIRONMENT FIX ---
            export MAMBA_ROOT_PREFIX={mamba_root_q}

            # Initialize Micromamba
            eval "$({mamba_exe_q} shell hook --shell bash)"
            micromamba activate {conda_env_q}

            # Verify Python is found (for debugging logs)
            which python

            # --- JAX OPTIMIZATIONS ---
            export JAX_COMPILATION_CACHE_DIR={jax_cache_q}
            export JAX_PERSISTENT_CACHE_MIN_ENTRY_SIZE_BYTES=0
            export JAX_PERSISTENT_CACHE_MIN_COMPILE_TIME_SECS=0
            export JAX_PLATFORMS=cuda

            # --- RUN ALPHAFOLD ---
            time python {run_script_q} \\
                --json_path={input_q} \\
                --model_dir={model_dir_q} \\
                --db_dir={db_dir_q} \\
                --output_dir={out_q} \\
                {cpu_flags}

            echo "=========================================="
            echo "Done:      $(date)"
            echo "=========================================="
            """
        )
        return script

    def find_primary_structure_file(self, *, job_dir: Path) -> Path | None:
        matches = sorted(job_dir.glob("**/*model.cif"))
        return matches[0] if matches else None
