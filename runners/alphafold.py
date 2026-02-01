from __future__ import annotations

from runners import Runner, register


@register
class AlphaFoldRunner(Runner):
    key = "alphafold3"
    name = "AlphaFold 3"

    def build_script(self, job, config=None) -> str:
        workdir = job.workdir
        outdir = workdir / "output"
        slurm_directives = config.get_slurm_directives() if config else ""
        return f"""#!/bin/bash
#SBATCH --job-name=af3-{job.id}
#SBATCH --output={outdir}/slurm-%j.out
#SBATCH --error={outdir}/slurm-%j.err
{slurm_directives}

set -euo pipefail

cd {workdir}
mkdir -p output

echo "AlphaFold stub runner. Replace this with real AlphaFold execution." > output/README.txt
echo "job_id={job.id}" >> output/README.txt
echo "runner={self.key}" >> output/README.txt

sleep 2
echo "done" > output/status.txt
"""
