from __future__ import annotations

from pathlib import Path

from django.conf import settings

from runners import Runner, register


@register
class LigandMPNNRunner(Runner):
    key = "ligandmpnn"
    name = "LigandMPNN"

    def build_script(self, job, config=None) -> str:
        workdir = Path(job.host_workdir)
        outdir = workdir / "output"

        # Use config image override, fall back to settings
        image = (
            config.image_uri
            if config and config.image_uri
            else settings.LIGANDMPNN_IMAGE
        )

        # Build SLURM directives from config
        slurm_directives = config.get_slurm_directives() if config else ""

        params = job.params or {}
        model_variant = params.get("model_variant", "protein_mpnn")
        noise_level = params.get("noise_level", "")

        # Build checkpoint flag
        if model_variant == "protein_mpnn":
            ckpt_flag = f"--checkpoint_protein_mpnn /app/model_params/proteinmpnn_{noise_level}.pt"
        else:
            ckpt_flag = f"--checkpoint_ligand_mpnn /app/model_params/ligandmpnn_{noise_level}.pt"

        flags = [f"--model_type {model_variant}", ckpt_flag]

        if params.get("temperature"):
            flags.append(f"--sampling_temp \"{params['temperature']}\"")
        if params.get("num_sequences"):
            flags.append(f"--number_of_batches {params['num_sequences']}")
        if params.get("seed") is not None:
            flags.append(f"--seed {params['seed']}")
        if params.get("chains_to_design"):
            flags.append(f"--chains_to_design \"{params['chains_to_design']}\"")
        if params.get("fixed_residues"):
            flags.append(f"--fixed_positions \"{params['fixed_residues']}\"")

        flag_str = " \\\n  ".join(flags)

        return f"""#!/bin/bash
#SBATCH --job-name=ligandmpnn-{job.id}
#SBATCH --output={outdir}/slurm-%j.out
#SBATCH --error={outdir}/slurm-%j.err
{slurm_directives}

set -euo pipefail

mkdir -p {outdir}

docker run --rm --gpus all \\
  -v {workdir}:/work \\
  {image} \\
  --pdb_path /work/input/input.pdb \\
  --out_folder /work/output \\
  --batch_size 1 \\
  {flag_str}
"""
