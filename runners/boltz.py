from __future__ import annotations

from runners import Runner, register


@register
class BoltzRunner(Runner):
    key = "boltz-2"
    name = "Boltz-2"

    def build_script(self, job) -> str:
        workdir = job.workdir
        outdir = workdir / "output"
        return f"""#!/bin/bash
#SBATCH --job-name=boltz-{job.id}
#SBATCH --output={outdir}/slurm-%j.out
#SBATCH --error={outdir}/slurm-%j.err

set -euo pipefail

cd {workdir}
mkdir -p output

echo "Boltz stub runner. Replace this with real Boltz execution." > output/README.txt
echo "job_id={job.id}" >> output/README.txt
echo "runner={self.key}" >> output/README.txt

sleep 2
echo "done" > output/status.txt
"""
