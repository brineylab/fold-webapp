from __future__ import annotations

from pathlib import Path

from django.conf import settings

from runners import Runner, register


@register
class ChaiRunner(Runner):
    key = "chai-1"
    name = "Chai-1"

    def build_script(self, job, config=None) -> str:
        workdir = Path(job.workdir)
        outdir = workdir / "output"
        cache_dir = Path(settings.CHAI_CACHE_DIR)

        image = (
            config.image_uri
            if config and config.image_uri
            else settings.CHAI_IMAGE
        )

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

        docker_args = [
            "docker run --rm --gpus all",
            "-e NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}",
            "-e CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}",
            "-e CHAI_DOWNLOADS_DIR=/cache",
            f"-v {workdir}:/work",
            f"-v {cache_dir}:/cache",
        ]
        docker_args.append(
            f"{image} fold /work/input/sequences.fasta /work/output {constraint_flag} {flag_str}"
        )
        docker_cmd = " \\\n  ".join(docker_args)

        return f"""#!/bin/bash
set -euo pipefail
umask 000

mkdir -p {outdir} {cache_dir}

echo "=== GPU diagnostic ==="
nvidia-smi || echo "WARNING: nvidia-smi not available on this node"
echo "======================"

{docker_cmd}

# Ensure output stays writable for follow-up inspection and downloads.
chmod -R a+rwX {outdir} 2>/dev/null || true
"""
