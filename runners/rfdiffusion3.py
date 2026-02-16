from __future__ import annotations

from pathlib import Path

from django.conf import settings

from runners import Runner, register


@register
class RFdiffusion3Runner(Runner):
    key = "rfdiffusion3"
    name = "RFdiffusion3"

    def build_script(self, job, config=None) -> str:
        workdir = Path(job.host_workdir)
        outdir = workdir / "output"

        image = (
            config.image_uri
            if config and config.image_uri
            else settings.RFDIFFUSION3_IMAGE
        )

        slurm_directives = config.get_slurm_directives() if config else ""

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

        precision = None
        if config:
            precision = (config.extra_env or {}).get("RFD3_PRECISION")
        if precision:
            rfd3_args.append(f"trainer.precision={precision}")

        rfd3_cmd = " \\\n    ".join(rfd3_args)

        docker_args = [
            "docker run --rm --gpus all",
            "-e NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}",
            "-e CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES}",
            f"-v {workdir}:/work",
        ]
        if config:
            for k, v in (config.extra_env or {}).items():
                docker_args.append(f"-e {k}={v}")
            for mount in config.extra_mounts or []:
                docker_args.append(f"-v {mount['source']}:{mount['target']}")
        docker_args.append(image)
        docker_args.append(rfd3_cmd)
        docker_cmd = " \\\n  ".join(docker_args)

        return f"""#!/bin/bash
#SBATCH --job-name=rfdiffusion3-{job.id}
#SBATCH --output={outdir}/slurm-%j.out
#SBATCH --error={outdir}/slurm-%j.err
{slurm_directives}

set -euo pipefail

mkdir -p {outdir}

echo "=== GPU diagnostic ==="
nvidia-smi || echo "WARNING: nvidia-smi not available on this node"
echo "======================"

{docker_cmd}

# Ensure output is readable by the webapp
chmod -R a+rX {outdir} 2>/dev/null || true
"""
