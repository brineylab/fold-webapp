from __future__ import annotations

from pathlib import Path

from django.conf import settings

from runners import Runner, register


@register
class RFdiffusionRunner(Runner):
    key = "rfdiffusion"
    name = "RFdiffusion"

    def build_script(self, job, config=None) -> str:
        workdir = Path(job.host_workdir)
        outdir = workdir / "output"

        image = (
            config.image_uri
            if config and config.image_uri
            else settings.RFDIFFUSION_IMAGE
        )

        slurm_directives = config.get_slurm_directives() if config else ""

        params = job.params or {}
        mode = params.get("mode", "unconditional")
        num_designs = params.get("num_designs", 10)
        timesteps = params.get("timesteps", 50)
        contigs = params.get("contigs", "")

        # Build Hydra overrides
        hydra_overrides = [
            f"inference.output_prefix=/work/output/design",
            f"inference.model_directory_path=/app/RFdiffusion/models",
            f"inference.num_designs={num_designs}",
            f"diffuser.T={timesteps}",
        ]

        # Input PDB for modes that need it
        if mode == "binder":
            hydra_overrides.append("inference.input_pdb=/work/input/target.pdb")
        elif mode in ("motif", "partial"):
            hydra_overrides.append("inference.input_pdb=/work/input/input.pdb")

        # Contig string (single-quoted to prevent shell expansion of brackets)
        if contigs:
            hydra_overrides.append(f"'contigmap.contigs={contigs}'")

        # Hotspot residues for binder design
        hotspot = params.get("hotspot_residues", "")
        if hotspot:
            # Format: [A30,A33,A34] -> RFdiffusion ppi_hotspot format
            hotspot_str = hotspot.strip()
            if not hotspot_str.startswith("["):
                hotspot_str = f"[{hotspot_str}]"
            hydra_overrides.append(f"'ppi.hotspot_res={hotspot_str}'")

        # Partial diffusion
        if mode == "partial":
            partial_T = params.get("partial_T", 10)
            hydra_overrides.append(f"diffuser.partial_T={partial_T}")

        # Symmetric oligomer
        config_name = "base"
        if mode == "symmetric":
            config_name = "symmetry"
            sym_type = params.get("symmetry_type", "cyclic")
            sym_order = params.get("symmetry_order", 3)
            hydra_overrides.append(f"inference.symmetry={sym_type}")
            hydra_overrides.append(f"inference.symmetry_order={sym_order}")

        override_str = " \\\n    ".join(hydra_overrides)

        docker_args = [
            "docker run --rm --gpus all",
            f"-v {workdir}:/work",
        ]
        if config:
            for k, v in (config.extra_env or {}).items():
                docker_args.append(f"-e {k}={v}")
            for mount in config.extra_mounts or []:
                docker_args.append(f"-v {mount['source']}:{mount['target']}")
        docker_args.append("-e PYTHONUNBUFFERED=1")
        docker_args.append(image)
        docker_args.append(
            f"--config-name {config_name} \\\n"
            f"    {override_str}"
        )
        docker_cmd = " \\\n  ".join(docker_args)

        return f"""#!/bin/bash
#SBATCH --job-name=rfdiffusion-{job.id}
#SBATCH --output={outdir}/slurm-%j.out
#SBATCH --error={outdir}/slurm-%j.err
{slurm_directives}

set -euo pipefail

mkdir -p {outdir}

{docker_cmd}

# Ensure output is readable by the webapp
chmod -R a+rX {outdir} 2>/dev/null || true
"""
