from __future__ import annotations

from pathlib import Path

from django.conf import settings

from runners import Runner, register


@register
class BoltzRunner(Runner):
    key = "boltz-2"
    name = "Boltz-2"

    def build_script(self, job) -> str:
        workdir = Path(job.workdir)
        outdir = workdir / "output"
        input_path = workdir / "input" / "sequences.fasta"
        cache_dir = Path(settings.BOLTZ_CACHE_DIR)
        image = settings.BOLTZ_IMAGE

        params = job.params or {}
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

        return f"""#!/bin/bash
#SBATCH --job-name=boltz-{job.id}
#SBATCH --output={outdir}/slurm-%j.out
#SBATCH --error={outdir}/slurm-%j.err

set -euo pipefail

mkdir -p {outdir} {cache_dir}

docker run --rm --gpus all \\
  -e BOLTZ_CACHE=/cache \\
  -e BOLTZ_MSA_USERNAME \\
  -e BOLTZ_MSA_PASSWORD \\
  -v {workdir}:/work \\
  -v {cache_dir}:/cache \\
  {image} predict /work/input/sequences.fasta --out_dir /work/output --cache /cache {flag_str}
"""
