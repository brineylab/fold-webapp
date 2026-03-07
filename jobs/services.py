from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from console.models import RunnerConfig, SiteSettings
from console.services.quota import check_quota, get_user_quota
from jobs.models import Job, JobAttempt
from model_types.base import BaseModelType
from runners import get_runner
import slurm


MAX_SEQUENCE_CHARS = 200_000  # coarse protection; refine later
ACTIVE_JOB_STATUSES = {Job.Status.PENDING, Job.Status.RUNNING}
TERMINAL_JOB_STATUSES = {
    Job.Status.COMPLETED,
    Job.Status.FAILED,
    Job.Status.CANCELLED,
}


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


def submit_job(
    *,
    owner,
    model_type: BaseModelType,
    name: str = "",
    runner_key: str,
    sequences: str = "",
    params: dict,
    model_key: str,
    input_payload: dict | None = None,
) -> Job:
    """Create a Job, initialize its first attempt, and submit it to SLURM."""
    allowed, error = check_maintenance_mode()
    if not allowed:
        raise ValidationError(error)

    allowed, error = check_runner_enabled(runner_key)
    if not allowed:
        raise ValidationError(error)

    allowed, error = check_quota(owner)
    if not allowed:
        raise ValidationError(error)

    name = (name or "").strip()
    sequences = (sequences or "").strip()
    has_files = bool((input_payload or {}).get("files"))
    has_params = bool((input_payload or {}).get("params"))
    if not sequences and not has_files and not has_params:
        raise ValidationError("No input provided.")
    if len(sequences) > MAX_SEQUENCE_CHARS:
        raise ValidationError(f"Sequences too large (>{MAX_SEQUENCE_CHARS} chars).")

    runner = get_runner(runner_key)
    errors = runner.validate(sequences, params)
    if errors:
        raise ValidationError(errors)

    storage_payload = _sanitize_payload_for_storage(input_payload)
    quota = get_user_quota(owner)
    queued_at = timezone.now()

    with transaction.atomic():
        job = Job.objects.create(
            owner=owner,
            name=name,
            runner=runner_key,
            model_key=model_key,
            status=Job.Status.PENDING,
            sequences=sequences,
            params=params or {},
            input_payload=storage_payload,
            output_payload={},
            queued_at=queued_at,
            priority_tier_snapshot=quota.priority_tier,
            attempt_count=1,
        )
        attempt = JobAttempt.objects.create(
            job=job,
            attempt_number=1,
            status=JobAttempt.Status.PENDING,
        )

    try:
        model_type.prepare_workdir(job, input_payload or {})

        config = RunnerConfig.get_config(runner_key)
        script = runner.build_script(job, config=config)
        submitted_at = timezone.now()
        scheduler_job_id = slurm.submit(script, job.workdir, job.host_workdir)

        with transaction.atomic():
            job.slurm_job_id = scheduler_job_id
            job.submitted_at = submitted_at
            job.save(update_fields=["slurm_job_id", "submitted_at"])

            attempt.scheduler_job_id = scheduler_job_id
            attempt.save()
        return job
    except Exception as e:
        sync_job_status(
            job,
            Job.Status.FAILED,
            when=timezone.now(),
            error_message=str(e),
        )
        raise


def create_and_submit_job(**kwargs) -> Job:
    """Backward-compatible wrapper for the original submission entrypoint."""
    return submit_job(**kwargs)


def get_or_create_current_attempt(job: Job) -> JobAttempt:
    attempt = job.attempts.order_by("-attempt_number").first()
    if attempt:
        if job.attempt_count != attempt.attempt_number:
            job.attempt_count = attempt.attempt_number
            job.save(update_fields=["attempt_count"])
        return attempt

    attempt = JobAttempt.objects.create(
        job=job,
        attempt_number=1,
        status=job.status or Job.Status.PENDING,
        scheduler_job_id=job.slurm_job_id,
        started_at=job.started_at,
        finished_at=job.finished_at or job.completed_at,
        failure_summary=job.error_message,
    )
    if job.attempt_count != 1:
        job.attempt_count = 1
        job.save(update_fields=["attempt_count"])
    return attempt


def sync_job_status(
    job: Job,
    status: str,
    *,
    when=None,
    error_message: str | None = None,
    exit_code: int | None = None,
    scheduler_job_id: str | None = None,
) -> Job:
    """Keep the job row and its current attempt in sync during lifecycle changes."""
    when = when or timezone.now()

    with transaction.atomic():
        attempt = get_or_create_current_attempt(job)
        previous_status = job.status

        if scheduler_job_id and job.slurm_job_id != scheduler_job_id:
            job.slurm_job_id = scheduler_job_id
        if scheduler_job_id and attempt.scheduler_job_id != scheduler_job_id:
            attempt.scheduler_job_id = scheduler_job_id

        job.status = status
        attempt.status = status

        if status == Job.Status.RUNNING:
            if job.submitted_at is None:
                job.submitted_at = when
            if job.started_at is None:
                job.started_at = when
            if job.queued_at and job.wait_seconds is None and job.started_at:
                job.wait_seconds = max(
                    0, int((job.started_at - job.queued_at).total_seconds())
                )
            if attempt.started_at is None:
                attempt.started_at = job.started_at or when
            if error_message == "":
                job.error_message = ""
                attempt.failure_summary = ""

        elif status in TERMINAL_JOB_STATUSES:
            if status == Job.Status.CANCELLED and error_message is None:
                error_message = "Cancelled"
            if status == Job.Status.COMPLETED and error_message is None:
                error_message = ""

            if job.started_at is None and attempt.started_at is not None:
                job.started_at = attempt.started_at
            if (
                job.started_at is None
                and previous_status == Job.Status.RUNNING
                and job.submitted_at is not None
            ):
                job.started_at = job.submitted_at

            job.finished_at = when
            job.completed_at = when

            if job.wait_seconds is None and job.queued_at:
                wait_until = job.started_at or when
                job.wait_seconds = max(
                    0, int((wait_until - job.queued_at).total_seconds())
                )

            if job.started_at:
                job.run_seconds = max(0, int((when - job.started_at).total_seconds()))
                job.gpu_seconds = job.run_seconds

            if error_message is not None:
                job.error_message = error_message
                attempt.failure_summary = error_message
            elif status == Job.Status.COMPLETED:
                job.error_message = ""
                attempt.failure_summary = ""

            if attempt.started_at is None and job.started_at is not None:
                attempt.started_at = job.started_at
            attempt.finished_at = when
            if exit_code is not None:
                attempt.exit_code = exit_code

        if job.attempt_count != attempt.attempt_number:
            job.attempt_count = attempt.attempt_number

        job.save()
        attempt.save()

    return job


def cancel_job(
    job: Job,
    *,
    actor=None,
    source: str = "user",
    reason: str | None = None,
) -> bool:
    """Cancel a pending or running job and mark it as CANCELLED."""
    if job.status not in ACTIVE_JOB_STATUSES:
        return False

    if job.slurm_job_id:
        slurm.cancel(job.slurm_job_id)

    sync_job_status(
        job,
        Job.Status.CANCELLED,
        when=timezone.now(),
        error_message=reason or _build_cancel_reason(actor=actor, source=source),
    )
    return True


def hide_job(
    job: Job,
    *,
    actor=None,
    source: str = "user",
    cancel_if_active: bool = True,
) -> bool:
    """Soft-delete a job by hiding it from the owner."""
    if job.hidden_from_owner:
        return False

    if cancel_if_active and job.status in ACTIVE_JOB_STATUSES:
        cancel_job(
            job,
            actor=actor,
            source=source,
            reason=_build_hide_cancel_reason(actor=actor, source=source),
        )

    job.hidden_from_owner = True
    job.save(update_fields=["hidden_from_owner"])
    return True


def hide_job_from_owner(job: Job, actor=None, source: str = "user") -> bool:
    return hide_job(job, actor=actor, source=source)


def list_output_files(job: Job) -> list[dict]:
    outdir = job.workdir / "output"
    files = []
    if outdir.exists() and outdir.is_dir():
        for path in sorted(outdir.rglob("*")):
            if path.is_file():
                rel = path.relative_to(outdir)
                files.append({"name": str(rel), "size": path.stat().st_size})
    return files


def serialize_job(
    job: Job,
    *,
    include_params: bool = False,
    include_output_files: bool = False,
    include_attempts: bool = False,
) -> dict:
    payload = {
        "id": str(job.id),
        "name": job.name,
        "model_key": job.model_key,
        "runner": job.runner,
        "status": job.status,
        "error_message": job.error_message,
        "created_at": _isoformat(job.created_at),
        "queued_at": _isoformat(job.queued_at),
        "submitted_at": _isoformat(job.submitted_at),
        "started_at": _isoformat(job.started_at),
        "completed_at": _isoformat(job.completed_at),
        "finished_at": _isoformat(job.finished_at),
        "wait_seconds": job.wait_seconds,
        "run_seconds": job.run_seconds,
        "gpu_seconds": job.gpu_seconds,
        "priority_tier_snapshot": job.priority_tier_snapshot,
        "attempt_count": job.attempt_count,
    }
    if include_params:
        payload["params"] = job.params
    if include_output_files:
        payload["output_files"] = list_output_files(job)
    if include_attempts:
        payload["attempts"] = [
            _serialize_attempt(attempt)
            for attempt in job.attempts.order_by("attempt_number")
        ]
    return payload


def _sanitize_payload_for_storage(input_payload: dict | None) -> dict:
    """Strip binary file content from input_payload for JSON-safe DB storage.

    Replaces the ``files`` dict (filename -> bytes) with a list of filenames.
    """
    if not input_payload:
        return {}
    return {
        "sequences": input_payload.get("sequences", ""),
        "params": input_payload.get("params", {}),
        "files": list(input_payload.get("files", {}).keys()),
    }


def _serialize_attempt(attempt: JobAttempt) -> dict:
    return {
        "attempt_number": attempt.attempt_number,
        "status": attempt.status,
        "scheduler_job_id": attempt.scheduler_job_id,
        "container_id": attempt.container_id,
        "gpu_index": attempt.gpu_index,
        "started_at": _isoformat(attempt.started_at),
        "finished_at": _isoformat(attempt.finished_at),
        "exit_code": attempt.exit_code,
        "stdout_path": attempt.stdout_path,
        "stderr_path": attempt.stderr_path,
        "failure_summary": attempt.failure_summary,
    }


def _isoformat(value) -> str | None:
    return value.isoformat() if value else None


def _build_cancel_reason(*, actor=None, source: str = "user") -> str:
    actor_name = getattr(actor, "username", None) or "system"
    if source == "api":
        return f"Cancelled by {actor_name} via API"
    if source == "admin":
        return f"Cancelled by admin ({actor_name})"
    if source == "system":
        return "Cancelled by system"
    return f"Cancelled by {actor_name}"


def _build_hide_cancel_reason(*, actor=None, source: str = "user") -> str:
    actor_name = getattr(actor, "username", None) or "system"
    if source == "admin":
        return f"Cancelled and hidden by admin ({actor_name})"
    return f"Cancelled and hidden by {actor_name}"
