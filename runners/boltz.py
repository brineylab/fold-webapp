from __future__ import annotations

from pathlib import Path

from django.conf import settings

from runners import Runner, register


@register
class BoltzRunner(Runner):
    key = "boltz-2"
    name = "Boltz-2"

    def build_script(self, job, config=None) -> str:
        workdir = Path(job.host_workdir)
        outdir = workdir / "output"
        cache_dir = Path(settings.BOLTZ_CACHE_DIR)

        # Use config image override, fall back to settings
        image = (
            config.image_uri
            if config and config.image_uri
            else settings.BOLTZ_IMAGE
        )

        # Build SLURM directives from config
        slurm_directives = config.get_slurm_directives() if config else ""

        params = job.params or {}
        input_filename = params.get("input_filename", "sequences.fasta")
        flags: list[str] = []
        if params.get("use_msa_server"):
            flags.append("--use_msa_server")
        if params.get("use_potentials"):
            flags.append("--use_potentials")
        if params.get("output_format"):
            flags.extend(["--output_format", str(params["output_format"])])
        if params.get("recycling_steps"):
            flags.extend(["--recycling_steps", str(params["recycling_steps"])])
        if params.get("sampling_steps"):
            flags.extend(["--sampling_steps", str(params["sampling_steps"])])
        if params.get("diffusion_samples"):
            flags.extend(["--diffusion_samples", str(params["diffusion_samples"])])

        flag_str = " ".join(flags)

        docker_args = [
            "docker run --rm --gpus all",
            "-e BOLTZ_CACHE=/cache",
            "-e BOLTZ_MSA_USERNAME",
            "-e BOLTZ_MSA_PASSWORD",
            f"-v {workdir}:/work",
            f"-v {cache_dir}:/cache",
        ]
        if config:
            for k, v in (config.extra_env or {}).items():
                docker_args.append(f"-e {k}={v}")
            for mount in config.extra_mounts or []:
                docker_args.append(f"-v {mount['source']}:{mount['target']}")
        docker_args.append(
            f"{image} predict /work/input/{input_filename} --out_dir /work/output --cache /cache {flag_str}"
        )
        docker_cmd = " \\\n  ".join(docker_args)

        return f"""#!/bin/bash
#SBATCH --job-name=boltz-{job.id}
#SBATCH --output={outdir}/slurm-%j.out
#SBATCH --error={outdir}/slurm-%j.err
{slurm_directives}

set -euo pipefail

mkdir -p {outdir} {cache_dir}

{docker_cmd}

# Ensure output is readable by the webapp
chmod -R a+rX {outdir} 2>/dev/null || true
"""
