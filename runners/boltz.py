from __future__ import annotations

from pathlib import Path

from django.conf import settings

from runners import (
    Runner,
    docker_resource_flags,
    optional_cuda_visible_devices_env_setup,
    register,
)


@register
class BoltzRunner(Runner):
    key = "boltz-2"
    name = "Boltz-2"

    def build_script(self, job, config=None) -> str:
        workdir = Path(job.workdir)
        outdir = workdir / "output"
        cache_dir = Path(settings.BOLTZ_CACHE_DIR)

        image = (
            config.image_uri
            if config and config.image_uri
            else settings.BOLTZ_IMAGE
        )

        params = job.params or {}
        input_filename = params.get("input_filename", "sequences.fasta")
        flags: list[str] = []
        if params.get("use_msa_server"):
            flags.append("--use_msa_server")
        if params.get("use_potentials"):
            flags.append("--use_potentials")
        if params.get("no_kernels"):
            flags.append("--no_kernels")
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
            *docker_resource_flags(
                shm_size=settings.BOLTZ_DOCKER_SHM_SIZE,
                ipc_mode=settings.BOLTZ_DOCKER_IPC_MODE,
            ),
            "-e NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}",
            "${cuda_visible_devices_flag}",
            "-e BOLTZ_CACHE=/cache",
            "-e BOLTZ_MSA_USERNAME",
            "-e BOLTZ_MSA_PASSWORD",
            f"-v {workdir}:/work",
            f"-v {cache_dir}:/cache",
        ]
        docker_args.append(
            f"{image} predict /work/input/{input_filename} --out_dir /work/output --cache /cache {flag_str}"
        )
        docker_cmd = " \\\n  ".join(docker_args)

        return f"""#!/bin/bash
set -euo pipefail
umask 000

mkdir -p {outdir} {cache_dir}

echo "=== GPU diagnostic ==="
nvidia-smi || echo "WARNING: nvidia-smi not available on this node"
echo "======================"

{optional_cuda_visible_devices_env_setup()}

{docker_cmd}

# Ensure output stays writable for follow-up inspection and downloads.
chmod -R a+rwX {outdir} 2>/dev/null || true
"""
