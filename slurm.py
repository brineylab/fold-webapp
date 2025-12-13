from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path


class SlurmError(Exception):
    pass


def _job_base_dir() -> Path:
    try:
        from django.conf import settings  # type: ignore

        return Path(getattr(settings, "JOB_BASE_DIR"))
    except Exception:
        return Path(os.environ.get("JOB_BASE_DIR", "./job_data"))


def _fake_slurm_enabled() -> bool:
    try:
        from django.conf import settings  # type: ignore

        return bool(getattr(settings, "FAKE_SLURM", False))
    except Exception:
        return os.environ.get("FAKE_SLURM", "0") == "1"


def submit(script_content: str, workdir: Path) -> str:
    """
    Write script to workdir/job.sbatch, call sbatch, return SLURM job ID.

    In FAKE_SLURM mode, returns FAKE-<job_uuid> and stores timestamp in workdir.
    """
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    if _fake_slurm_enabled():
        job_uuid = workdir.name
        slurm_job_id = f"FAKE-{job_uuid}"
        (workdir / ".fake_slurm_started_at").write_text(str(time.time()), encoding="utf-8")
        # ensure output dir exists
        (workdir / "output").mkdir(parents=True, exist_ok=True)
        return slurm_job_id

    script_path = workdir / "job.sbatch"
    script_path.write_text(script_content, encoding="utf-8")

    try:
        p = subprocess.run(
            ["sbatch", str(script_path)],
            cwd=str(workdir),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise SlurmError(f"sbatch failed (rc={e.returncode}): {e.stderr.strip() or e.stdout.strip()}") from e

    match = re.search(r"Submitted batch job (\d+)", p.stdout)
    if not match:
        raise SlurmError(f"Could not parse sbatch output: {p.stdout.strip()}")
    return match.group(1)


def check_status(slurm_job_id: str) -> str:
    """
    Return one of: PENDING, RUNNING, COMPLETED, FAILED, UNKNOWN.

    In FAKE_SLURM mode, transitions based on time since submit.
    """
    slurm_job_id = str(slurm_job_id)

    if slurm_job_id.startswith("FAKE-") or _fake_slurm_enabled():
        job_uuid = slurm_job_id.removeprefix("FAKE-")
        workdir = _job_base_dir() / job_uuid
        canceled = workdir / ".fake_slurm_canceled"
        if canceled.exists():
            return "FAILED"

        started_path = workdir / ".fake_slurm_started_at"
        if not started_path.exists():
            return "UNKNOWN"

        try:
            started_at = float(started_path.read_text(encoding="utf-8").strip())
        except Exception:
            return "UNKNOWN"

        elapsed = time.time() - started_at
        if elapsed < 5:
            return "PENDING"
        if elapsed < 15:
            return "RUNNING"

        # Mark completed and create dummy output if needed
        outdir = workdir / "output"
        outdir.mkdir(parents=True, exist_ok=True)
        dummy = outdir / "results.txt"
        if not dummy.exists():
            dummy.write_text("FAKE_SLURM completed successfully.\n", encoding="utf-8")
        return "COMPLETED"

    # Active jobs: squeue
    squeue = subprocess.run(
        ["squeue", "-j", slurm_job_id, "-h", "-o", "%T"],
        capture_output=True,
        text=True,
    )
    state = squeue.stdout.strip() if squeue.returncode == 0 else ""
    if state:
        # Common states: PENDING, RUNNING, COMPLETING, CONFIGURING, SUSPENDED
        if state in {"PENDING", "CONFIGURING"}:
            return "PENDING"
        if state in {"RUNNING", "COMPLETING", "SUSPENDED"}:
            return "RUNNING"
        # Unknown active state, still treat as running-ish
        return "RUNNING"

    # Completed jobs: sacct (may include step lines; pick first non-empty)
    sacct = subprocess.run(
        ["sacct", "-j", slurm_job_id, "-n", "-o", "State", "-X"],
        capture_output=True,
        text=True,
    )
    if sacct.returncode != 0:
        return "UNKNOWN"

    lines = [ln.strip() for ln in sacct.stdout.splitlines() if ln.strip()]
    if not lines:
        return "UNKNOWN"

    raw_state = lines[0].split()[0]
    raw_state = raw_state.split("+")[0]  # e.g. CANCELLED+ => CANCELLED

    if raw_state == "COMPLETED":
        return "COMPLETED"
    if raw_state in {"PENDING", "CONFIGURING"}:
        return "PENDING"
    if raw_state in {"RUNNING", "COMPLETING"}:
        return "RUNNING"
    if raw_state in {"CANCELLED", "FAILED", "TIMEOUT", "NODE_FAIL", "OUT_OF_MEMORY", "PREEMPTED"}:
        return "FAILED"

    return "FAILED"


def cancel(slurm_job_id: str) -> None:
    """Cancel a job via scancel (or mark canceled in FAKE_SLURM mode)."""
    slurm_job_id = str(slurm_job_id)

    if slurm_job_id.startswith("FAKE-") or _fake_slurm_enabled():
        job_uuid = slurm_job_id.removeprefix("FAKE-")
        workdir = _job_base_dir() / job_uuid
        workdir.mkdir(parents=True, exist_ok=True)
        (workdir / ".fake_slurm_canceled").write_text(str(time.time()), encoding="utf-8")
        return

    subprocess.run(["scancel", slurm_job_id], check=False, capture_output=True, text=True)


