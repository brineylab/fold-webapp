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
class BoltzGenRunner(Runner):
    key = "boltzgen"
    name = "BoltzGen"

    def build_script(self, job, config=None) -> str:
        workdir = Path(job.workdir)
        outdir = workdir / "output"

        image = (
            config.image_uri
            if config and config.image_uri
            else settings.BOLTZGEN_IMAGE
        )

        cache_dir = settings.BOLTZGEN_CACHE_DIR

        params = job.params or {}
        protocol = params.get("protocol", "protein-anything")
        num_designs = params.get("num_designs", 100)
        budget = params.get("budget", 10)
        alpha = params.get("alpha", 0.001)

        # Build boltzgen command args
        cmd_args = [
            "run /work/input/design.yaml",
            "--output /work/output",
        ]

        # Only pass --protocol for non-yaml_upload modes
        if protocol != "yaml_upload":
            cmd_args.append(f"--protocol {protocol}")

        cmd_args.extend([
            f"--num_designs {num_designs}",
            f"--budget {budget}",
            f"--alpha {alpha}",
        ])

        cmd_str = " \\\n    ".join(cmd_args)

        docker_args = [
            "docker run --rm --gpus all",
            *docker_resource_flags(
                shm_size=settings.BOLTZGEN_DOCKER_SHM_SIZE,
                ipc_mode=settings.BOLTZGEN_DOCKER_IPC_MODE,
            ),
            "-e NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}",
            "${cuda_visible_devices_flag}",
            f"-v {workdir}:/work",
            f"-v {cache_dir}:/cache",
        ]
        docker_args.append(image)
        docker_args.append(cmd_str)
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
