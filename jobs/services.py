from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone

from jobs.models import Job
from runners import get_runner
import slurm


MAX_SEQUENCE_CHARS = 200_000  # coarse protection; refine later


def create_and_submit_job(*, owner, name: str = "", runner_key: str, sequences: str, params: dict) -> Job:
    """Create a Job, create its workdir, write inputs, submit to SLURM."""
    name = (name or "").strip()
    sequences = (sequences or "").strip()
    if not sequences:
        raise ValidationError("Sequences are required.")
    if len(sequences) > MAX_SEQUENCE_CHARS:
        raise ValidationError(f"Sequences too large (>{MAX_SEQUENCE_CHARS} chars).")

    runner = get_runner(runner_key)
    errors = runner.validate(sequences, params)
    if errors:
        raise ValidationError(errors)

    job = Job.objects.create(
        owner=owner,
        name=name,
        runner=runner_key,
        status=Job.Status.PENDING,
        sequences=sequences,
        params=params or {},
    )

    # Controlled filesystem layout under JOB_BASE_DIR/<uuid>/
    (job.workdir / "input").mkdir(parents=True, exist_ok=True)
    (job.workdir / "output").mkdir(parents=True, exist_ok=True)

    (job.workdir / "input" / "sequences.fasta").write_text(sequences, encoding="utf-8")

    try:
        script = runner.build_script(job)
        job.slurm_job_id = slurm.submit(script, job.workdir)
        job.submitted_at = timezone.now()
        job.save(update_fields=["slurm_job_id", "submitted_at"])
        return job
    except Exception as e:
        job.status = Job.Status.FAILED
        job.error_message = str(e)
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        raise


