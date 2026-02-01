from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils import timezone

from console.models import RunnerConfig, SiteSettings
from console.services.quota import check_quota
from jobs.models import Job
from runners import get_runner
import slurm


MAX_SEQUENCE_CHARS = 200_000  # coarse protection; refine later


def check_maintenance_mode() -> tuple[bool, str | None]:
    """
    Check if site is in maintenance mode.
    
    Returns:
        Tuple of (allowed, error_message).
        If allowed is True (not in maintenance), error_message is None.
        If allowed is False (in maintenance), error_message is the maintenance message.
    """
    site_settings = SiteSettings.get_settings()
    if site_settings.maintenance_mode:
        return False, site_settings.maintenance_message
    return True, None


def check_runner_enabled(runner_key: str) -> tuple[bool, str | None]:
    """
    Check if a specific runner is enabled.
    
    Returns:
        Tuple of (allowed, error_message).
        If allowed is True, error_message is None.
        If allowed is False, error_message explains why.
    """
    if not RunnerConfig.is_runner_enabled(runner_key):
        config = RunnerConfig.get_config(runner_key)
        reason = config.disabled_reason or "This runner is temporarily unavailable."
        return False, f"Runner is disabled: {reason}"
    return True, None


def create_and_submit_job(
    *,
    owner,
    name: str = "",
    runner_key: str,
    sequences: str,
    params: dict,
    model_key: str,
    input_payload: dict | None = None,
) -> Job:
    """Create a Job, create its workdir, write inputs, submit to SLURM."""
    # Check maintenance mode first
    allowed, error = check_maintenance_mode()
    if not allowed:
        raise ValidationError(error)
    
    # Check if runner is enabled
    allowed, error = check_runner_enabled(runner_key)
    if not allowed:
        raise ValidationError(error)
    
    # Check quota before proceeding
    allowed, error = check_quota(owner)
    if not allowed:
        raise ValidationError(error)
    
    name = (name or "").strip()
    sequences = (sequences or "").strip()
    has_files = bool((input_payload or {}).get("files"))
    if not sequences and not has_files:
        raise ValidationError("No input provided (sequences or files required).")
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
        model_key=model_key,
        status=Job.Status.PENDING,
        sequences=sequences,
        params=params or {},
        input_payload=input_payload or {},
        output_payload={},
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

