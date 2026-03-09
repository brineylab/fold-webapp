from __future__ import annotations

from runners import Runner, register


@register
class AlphaFoldRunner(Runner):
    key = "alphafold3"
    name = "AlphaFold 3"

    def build_script(self, job, config=None) -> str:
        workdir = job.workdir
        outdir = workdir / "output"
        return f"""#!/bin/bash
set -euo pipefail
umask 000

cd {workdir}
mkdir -p output

echo "AlphaFold stub runner. Replace this with real AlphaFold execution." > output/README.txt
echo "job_id={job.id}" >> output/README.txt
echo "runner={self.key}" >> output/README.txt

sleep 2
echo "done" > output/status.txt

chmod -R a+rwX output 2>/dev/null || true
"""
