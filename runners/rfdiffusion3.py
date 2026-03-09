from __future__ import annotations

from pathlib import Path

from django.conf import settings

from runners import Runner, optional_cuda_visible_devices_env_setup, register


@register
class RFdiffusion3Runner(Runner):
    key = "rfdiffusion3"
    name = "RFdiffusion3"

    def build_script(self, job, config=None) -> str:
        workdir = Path(job.workdir)
        outdir = workdir / "output"

        image = (
            config.image_uri
            if config and config.image_uri
            else settings.RFDIFFUSION3_IMAGE
        )

        params = job.params or {}
        num_designs = params.get("num_designs", 8)
        n_batches = params.get("n_batches", 1)
        timesteps = params.get("timesteps", 200)
        step_scale = params.get("step_scale", 1.5)
        is_symmetric = params.get("symmetric", False)

        # Build rfd3 design command arguments
        rfd3_args = [
            "design",
            "out_dir=/work/output",
            "inputs=/work/input/input_spec.json",
            f"n_batches={n_batches}",
            f"diffusion_batch_size={num_designs}",
            f"inference_sampler.num_timesteps={timesteps}",
            f"inference_sampler.step_scale={step_scale}",
        ]
        if is_symmetric:
            rfd3_args.append("inference_sampler.kind=symmetry")

        rfd3_cmd = " \\\n    ".join(rfd3_args)

        docker_args = [
            "docker run --rm --gpus all",
            "-e NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}",
            "${cuda_visible_devices_flag}",
            f"-v {workdir}:/work",
        ]
        docker_args.append(image)
        docker_args.append(rfd3_cmd)
        docker_cmd = " \\\n  ".join(docker_args)

        return f"""#!/bin/bash
set -euo pipefail
umask 000

mkdir -p {outdir}

echo "=== GPU diagnostic ==="
nvidia-smi || echo "WARNING: nvidia-smi not available on this node"
echo "======================"

{optional_cuda_visible_devices_env_setup()}

{docker_cmd}

# Ensure output stays writable for follow-up inspection and downloads.
chmod -R a+rwX {outdir} 2>/dev/null || true
"""
