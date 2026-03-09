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
class LigandMPNNRunner(Runner):
    key = "ligandmpnn"
    name = "LigandMPNN"

    def build_script(self, job, config=None) -> str:
        workdir = Path(job.workdir)
        outdir = workdir / "output"

        image = (
            config.image_uri
            if config and config.image_uri
            else settings.LIGANDMPNN_IMAGE
        )

        params = job.params or {}
        model_variant = params.get("model_variant", "protein_mpnn")
        noise_level = params.get("noise_level", "")

        # Build checkpoint path (foundry uses a unified --checkpoint_path flag)
        if model_variant == "protein_mpnn":
            ckpt_path = f"/app/checkpoints/proteinmpnn_{noise_level}.pt"
        else:
            ckpt_path = f"/app/checkpoints/ligandmpnn_{noise_level}.pt"

        flags = [
            f"--model_type {model_variant}",
            f"--checkpoint_path {ckpt_path}",
            "--is_legacy_weights True",
        ]

        if params.get("temperature"):
            flags.append(f"--temperature \"{params['temperature']}\"")
        if params.get("num_sequences"):
            flags.append(f"--number_of_batches {params['num_sequences']}")
        if params.get("seed") is not None:
            flags.append(f"--seed {params['seed']}")
        if params.get("chains_to_design"):
            flags.append(f"--designed_chains \"{params['chains_to_design']}\"")
        if params.get("fixed_residues"):
            flags.append(f"--fixed_residues \"{params['fixed_residues']}\"")

        flag_str = " \\\n  ".join(flags)

        docker_args = [
            "docker run --rm --gpus all",
            *docker_resource_flags(
                shm_size=settings.LIGANDMPNN_DOCKER_SHM_SIZE,
                ipc_mode=settings.LIGANDMPNN_DOCKER_IPC_MODE,
            ),
            "-e NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}",
            "${cuda_visible_devices_flag}",
            f"-v {workdir}:/work",
        ]
        docker_args.extend([
            f"{image}",
            "--structure_path /work/input/input.pdb",
            "--out_directory /work/output",
            "--batch_size 1",
            flag_str,
        ])
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

# Package results into a single archive without requiring host zip(1).
python3 - <<'PY'
from pathlib import Path
import zipfile

outdir = Path({str(outdir)!r})
archive_path = outdir / "results.zip"

with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(outdir.rglob("*")):
        if not path.is_file() or path == archive_path:
            continue
        archive.write(path, arcname=path.relative_to(outdir))
PY
"""
