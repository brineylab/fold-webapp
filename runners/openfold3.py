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
class OpenFold3Runner(Runner):
    key = "openfold3"
    name = "OpenFold3"

    def build_script(self, job, config=None) -> str:
        workdir = Path(job.workdir)
        outdir = workdir / "output"
        cache_dir = Path(settings.OPENFOLD3_CACHE_DIR)

        image = (
            config.image_uri
            if config and config.image_uri
            else settings.OPENFOLD3_IMAGE
        )

        params = job.params or {}
        flags: list[str] = []

        # Boolean flags: explicit --flag / --no-flag form
        if params.get("use_msa_server"):
            flags.append("--use-msa-server")
        else:
            flags.append("--no-use-msa-server")

        if params.get("use_templates"):
            flags.append("--use-templates")
        else:
            flags.append("--no-use-templates")

        if params.get("num_diffusion_samples"):
            flags.extend(["--num-diffusion-samples", str(params["num_diffusion_samples"])])
        if params.get("num_model_seeds"):
            flags.extend(["--num-model-seeds", str(params["num_model_seeds"])])
        if params.get("seed") is not None:
            flags.extend(["--seed", str(params["seed"])])

        # Output format via runner YAML preset
        runner_yaml_setup = ""
        runner_yaml_flag = ""
        output_format = params.get("output_format", "cif")
        if output_format == "pdb":
            runner_yaml_setup = (
                f'echo "structure_format: pdb" > {workdir / "input" / "output_settings.yaml"}'
            )
            runner_yaml_flag = "--runner-yaml /work/input/output_settings.yaml"

        flag_str = " ".join(flags)

        docker_args = [
            "docker run --rm --gpus all",
            *docker_resource_flags(
                shm_size=settings.OPENFOLD3_DOCKER_SHM_SIZE,
                ipc_mode=settings.OPENFOLD3_DOCKER_IPC_MODE,
            ),
            "-e NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}",
            "${cuda_visible_devices_flag}",
            "-e OPENFOLD_CACHE=/cache",
            f"-v {workdir}:/work",
            f"-v {cache_dir}:/cache",
        ]
        docker_args.append(
            f"{image} run_openfold predict"
            f" --query-json /work/input/query.json"
            f" --output-dir /work/output"
            f" {runner_yaml_flag} {flag_str}".rstrip()
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

{runner_yaml_setup}

{docker_cmd}

# Ensure output stays writable for follow-up inspection and downloads.
chmod -R a+rwX {outdir} 2>/dev/null || true
"""
