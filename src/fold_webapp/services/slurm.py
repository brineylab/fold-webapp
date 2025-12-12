from __future__ import annotations

import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class SlurmSnapshot:
    job_count: int
    keys: set[str]


@dataclass(frozen=True)
class SlurmClient:
    """Small wrapper around `squeue` to inspect cluster activity."""

    squeue_cmd: str = "squeue"

    def get_snapshot(self) -> SlurmSnapshot:
        """Return a set of job identifiers we can match against logs.

        Includes both numeric JobID and JobName tokens to be resilient to
        site-specific SLURM configs.
        """
        try:
            # %i=JobID, %j=JobName
            out = subprocess.check_output(
                [self.squeue_cmd, "--noheader", "--format=%i %j"], text=True
            ).strip()
        except Exception:
            return SlurmSnapshot(job_count=0, keys=set())

        keys: set[str] = set()
        if not out:
            return SlurmSnapshot(job_count=0, keys=keys)

        lines = out.splitlines()
        for line in lines:
            parts = line.strip().split(maxsplit=1)
            if not parts:
                continue
            keys.add(parts[0])
            if len(parts) > 1:
                keys.add(parts[1])
        return SlurmSnapshot(job_count=len(lines), keys=keys)

    def get_active_job_keys(self) -> set[str]:
        return self.get_snapshot().keys


