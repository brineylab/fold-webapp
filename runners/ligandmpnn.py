from __future__ import annotations

from pathlib import Path

from django.conf import settings

from runners import Runner, register


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
            "-e NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}",
            "-e CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-}",
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

{docker_cmd}

# Ensure output stays writable for follow-up inspection and downloads.
chmod -R a+rwX {outdir} 2>/dev/null || true

# Package results into a single zip.
cd {outdir}
zip -r results.zip . -x 'results.zip'
"""
