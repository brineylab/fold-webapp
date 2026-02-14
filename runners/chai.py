from __future__ import annotations

from pathlib import Path

from django.conf import settings

from runners import Runner, register


@register
class ChaiRunner(Runner):
    key = "chai-1"
    name = "Chai-1"

    def build_script(self, job, config=None) -> str:
        workdir = Path(job.host_workdir)
        outdir = workdir / "output"
        cache_dir = Path(settings.CHAI_CACHE_DIR)

        # Use config image override, fall back to settings
        image = (
            config.image_uri
            if config and config.image_uri
            else settings.CHAI_IMAGE
        )

        # Build SLURM directives from config
        slurm_directives = config.get_slurm_directives() if config else ""

        params = job.params or {}
        flags: list[str] = []
        if params.get("use_msa_server"):
            flags.append("--use-msa-server")
        if params.get("num_diffn_samples"):
            flags.extend(["--num-diffn-samples", str(params["num_diffn_samples"])])
        if params.get("seed") is not None:
            flags.extend(["--seed", str(params["seed"])])

        # Restraints file: check filesystem first, fall back to params flag
        constraint_flag = ""
        if (Path(job.workdir) / "input" / "restraints.csv").exists():
            constraint_flag = "--constraint-path /work/input/restraints.csv"
        elif params.get("has_restraints"):
            constraint_flag = "--constraint-path /work/input/restraints.csv"

        flag_str = " ".join(flags)

        return f"""#!/bin/bash
#SBATCH --job-name=chai-{job.id}
#SBATCH --output={outdir}/slurm-%j.out
#SBATCH --error={outdir}/slurm-%j.err
{slurm_directives}

set -euo pipefail

mkdir -p {outdir} {cache_dir}

docker run --rm --gpus all \\
  -e CHAI_DOWNLOADS_DIR=/cache \\
  -v {workdir}:/work \\
  -v {cache_dir}:/cache \\
  {image} fold /work/input/sequences.fasta /work/output {constraint_flag} {flag_str}
"""
