from __future__ import annotations

from pathlib import Path

from django.conf import settings

from runners import Runner, register


@register
class BoltzGenRunner(Runner):
    key = "boltzgen"
    name = "BoltzGen"

    def build_script(self, job, config=None) -> str:
        workdir = Path(job.host_workdir)
        outdir = workdir / "output"

        image = (
            config.image_uri
            if config and config.image_uri
            else settings.BOLTZGEN_IMAGE
        )

        cache_dir = settings.BOLTZGEN_CACHE_DIR

        slurm_directives = config.get_slurm_directives() if config else ""

        params = job.params or {}
        protocol = params.get("protocol", "protein-anything")
        num_designs = params.get("num_designs", 100)
        budget = params.get("budget", 10)
        alpha = params.get("alpha", 0.001)

        # Build boltzgen command args
        cmd_args = [
            "boltzgen run /work/input/design.yaml",
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
            f"-v {workdir}:/work",
            f"-v {cache_dir}:/cache",
        ]
        if config:
            for k, v in (config.extra_env or {}).items():
                docker_args.append(f"-e {k}={v}")
            for mount in config.extra_mounts or []:
                docker_args.append(f"-v {mount['source']}:{mount['target']}")
        docker_args.append(image)
        docker_args.append(cmd_str)
        docker_cmd = " \\\n  ".join(docker_args)

        return f"""#!/bin/bash
#SBATCH --job-name=boltzgen-{job.id}
#SBATCH --output={outdir}/slurm-%j.out
#SBATCH --error={outdir}/slurm-%j.err
{slurm_directives}

set -euo pipefail

mkdir -p {outdir}

{docker_cmd}

# Ensure output is readable by the webapp
chmod -R a+rX {outdir} 2>/dev/null || true
"""
