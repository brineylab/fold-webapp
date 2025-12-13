from __future__ import annotations

from runners import Runner, register


@register
class ChaiRunner(Runner):
    key = "chai-1"
    name = "Chai-1"

    def build_script(self, job) -> str:
        workdir = job.workdir
        outdir = workdir / "output"
        return f"""#!/bin/bash
#SBATCH --job-name=chai-{job.id}
#SBATCH --output={outdir}/slurm-%j.out
#SBATCH --error={outdir}/slurm-%j.err

set -euo pipefail

cd {workdir}
mkdir -p output

echo "Chai stub runner. Replace this with real Chai execution." > output/README.txt
echo "job_id={job.id}" >> output/README.txt
echo "runner={self.key}" >> output/README.txt

sleep 2
echo "done" > output/status.txt
"""
