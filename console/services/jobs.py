from __future__ import annotations

from django.utils import timezone

from jobs.models import Job
import slurm


def cancel_job(job: Job, actor) -> bool:
    """
    Cancel a single job via SLURM and update its status.
    
    Args:
        job: The Job instance to cancel
        actor: The user performing the action (for audit trail)
    
    Returns:
        True if the job was cancelled, False if it was not cancellable
    """
    if job.status not in {Job.Status.PENDING, Job.Status.RUNNING}:
        return False
    
    if not job.slurm_job_id:
        return False
    
    slurm.cancel(job.slurm_job_id)
    job.status = Job.Status.FAILED
    job.error_message = f"Cancelled by admin ({actor.username})"
    job.completed_at = timezone.now()
    job.save(update_fields=["status", "error_message", "completed_at"])
    
    return True


def bulk_cancel_jobs(queryset, actor) -> int:
    """
    Cancel multiple jobs via SLURM.
    
    Args:
        queryset: QuerySet of Job instances to cancel
        actor: The user performing the action (for audit trail)
    
    Returns:
        Number of jobs successfully cancelled
    """
    cancelled_count = 0
    
    for job in queryset.iterator():
        if cancel_job(job, actor):
            cancelled_count += 1
    
    return cancelled_count


def hide_job_from_owner(job: Job, actor) -> bool:
    """
    Soft-delete a job by hiding it from the owner.
    
    Args:
        job: The Job instance to hide
        actor: The user performing the action (for audit trail)
    
    Returns:
        True if the job was hidden, False if already hidden
    """
    if job.hidden_from_owner:
        return False
    
    # If job is still running, cancel it first
    if job.status in {Job.Status.PENDING, Job.Status.RUNNING} and job.slurm_job_id:
        slurm.cancel(job.slurm_job_id)
        job.status = Job.Status.FAILED
        job.error_message = f"Cancelled and hidden by admin ({actor.username})"
        job.completed_at = timezone.now()
    
    job.hidden_from_owner = True
    job.save(update_fields=["hidden_from_owner", "status", "error_message", "completed_at"])
    
    return True


def bulk_hide_jobs(queryset, actor) -> int:
    """
    Soft-delete multiple jobs by hiding them from their owners.
    
    Args:
        queryset: QuerySet of Job instances to hide
        actor: The user performing the action (for audit trail)
    
    Returns:
        Number of jobs successfully hidden
    """
    hidden_count = 0
    
    for job in queryset.iterator():
        if hide_job_from_owner(job, actor):
            hidden_count += 1
    
    return hidden_count

