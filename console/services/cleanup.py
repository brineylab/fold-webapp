from __future__ import annotations

import shutil
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from console.models import UserQuota
from jobs.models import Job

if TYPE_CHECKING:
    from django.contrib.auth.models import User


def get_retention_days(user: User) -> int:
    """
    Get the retention period in days for a user's jobs.
    
    Staff users get the default retention (or 0 for no deletion).
    Regular users get their configured retention from UserQuota.
    """
    if user.is_staff:
        return getattr(settings, "DEFAULT_RETENTION_DAYS", 30)
    
    try:
        return user.quota.retention_days
    except UserQuota.DoesNotExist:
        return getattr(settings, "DEFAULT_RETENTION_DAYS", 30)


def get_jobs_for_cleanup(
    override_days: int | None = None,
    dry_run: bool = True,
) -> list[dict]:
    """
    Find jobs that are past their retention period and eligible for cleanup.
    
    Args:
        override_days: If provided, use this retention period for all users instead
                      of per-user settings.
        dry_run: If True, just return what would be cleaned up.
    
    Returns:
        List of dicts with job info and cleanup status.
    """
    now = timezone.now()
    results = []
    
    # Get completed/failed jobs only
    jobs = Job.objects.filter(
        status__in=[Job.Status.COMPLETED, Job.Status.FAILED],
        completed_at__isnull=False,
    ).select_related("owner")
    
    for job in jobs.iterator():
        if override_days is not None:
            retention_days = override_days
        else:
            retention_days = get_retention_days(job.owner)
        
        # retention_days == 0 means never delete
        if retention_days == 0:
            continue
        
        cutoff = now - timedelta(days=retention_days)
        
        if job.completed_at < cutoff:
            workdir = job.workdir
            workdir_exists = workdir.exists()
            workdir_size = get_directory_size(workdir) if workdir_exists else 0
            
            results.append({
                "job": job,
                "retention_days": retention_days,
                "completed_at": job.completed_at,
                "age_days": (now - job.completed_at).days,
                "workdir": str(workdir),
                "workdir_exists": workdir_exists,
                "workdir_size": workdir_size,
            })
    
    return results


def cleanup_job_workdir(job: Job) -> bool:
    """
    Delete a job's workdir files.
    
    The database record is preserved - only files are deleted.
    
    Args:
        job: The Job instance whose workdir should be cleaned up.
    
    Returns:
        True if workdir was deleted, False if it didn't exist.
    """
    workdir = job.workdir
    
    if not workdir.exists():
        return False
    
    try:
        shutil.rmtree(workdir)
        return True
    except OSError:
        return False


def cleanup_jobs(
    override_days: int | None = None,
    dry_run: bool = True,
) -> dict:
    """
    Clean up jobs past their retention period.
    
    Args:
        override_days: Override per-user retention with this value.
        dry_run: If True, don't actually delete anything.
    
    Returns:
        Dict with cleanup results.
    """
    jobs_for_cleanup = get_jobs_for_cleanup(override_days=override_days)
    
    cleaned = 0
    skipped = 0
    bytes_freed = 0
    errors = []
    
    for item in jobs_for_cleanup:
        job = item["job"]
        
        if dry_run:
            if item["workdir_exists"]:
                cleaned += 1
                bytes_freed += item["workdir_size"]
            else:
                skipped += 1
        else:
            if item["workdir_exists"]:
                if cleanup_job_workdir(job):
                    cleaned += 1
                    bytes_freed += item["workdir_size"]
                else:
                    errors.append(f"Failed to delete workdir for job {job.id}")
            else:
                skipped += 1
    
    return {
        "dry_run": dry_run,
        "total_candidates": len(jobs_for_cleanup),
        "cleaned": cleaned,
        "skipped": skipped,
        "bytes_freed": bytes_freed,
        "bytes_freed_mb": round(bytes_freed / (1024 * 1024), 2),
        "errors": errors,
        "jobs": jobs_for_cleanup if dry_run else [],
    }


def detect_orphan_workdirs() -> list[dict]:
    """
    Find workdirs in JOB_BASE_DIR that don't have a corresponding Job in the database.
    
    Returns:
        List of dicts with orphan workdir info.
    """
    job_base_dir = getattr(settings, "JOB_BASE_DIR", None)
    if not job_base_dir:
        return []
    
    job_base_dir = Path(job_base_dir)
    if not job_base_dir.exists():
        return []
    
    # Get all job IDs from database
    job_ids = set(str(j) for j in Job.objects.values_list("id", flat=True))
    
    orphans = []
    for path in job_base_dir.iterdir():
        if not path.is_dir():
            continue
        
        dir_name = path.name
        
        if dir_name not in job_ids:
            orphans.append({
                "path": str(path),
                "name": dir_name,
                "size": get_directory_size(path),
                "mtime": path.stat().st_mtime,
            })
    
    return orphans


def detect_orphan_jobs() -> QuerySet:
    """
    Find Jobs in the database whose workdirs don't exist on disk.
    
    These are jobs where the files have been manually deleted or lost.
    
    Returns:
        QuerySet of Job instances with missing workdirs.
    """
    orphan_ids = []
    
    for job in Job.objects.all().iterator():
        if not job.workdir.exists():
            orphan_ids.append(job.id)
    
    return Job.objects.filter(id__in=orphan_ids)


def delete_orphan_workdir(path: str | Path) -> bool:
    """
    Delete an orphan workdir.
    
    Args:
        path: Path to the orphan workdir.
    
    Returns:
        True if deleted successfully, False otherwise.
    """
    path = Path(path)
    
    if not path.exists():
        return False
    
    try:
        shutil.rmtree(path)
        return True
    except OSError:
        return False


def get_directory_size(path: Path) -> int:
    """
    Calculate the total size of a directory in bytes.
    
    Args:
        path: Path to the directory.
    
    Returns:
        Total size in bytes.
    """
    if not path.exists():
        return 0
    
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
    except OSError:
        pass
    
    return total


def get_cleanup_summary() -> dict:
    """
    Get a summary of cleanup status for the dashboard.
    
    Returns:
        Dict with cleanup statistics.
    """
    jobs_for_cleanup = get_jobs_for_cleanup()
    orphan_workdirs = detect_orphan_workdirs()
    orphan_jobs = detect_orphan_jobs()
    
    total_reclaimable = sum(j["workdir_size"] for j in jobs_for_cleanup if j["workdir_exists"])
    orphan_size = sum(o["size"] for o in orphan_workdirs)
    
    return {
        "jobs_pending_cleanup": len(jobs_for_cleanup),
        "jobs_reclaimable_bytes": total_reclaimable,
        "jobs_reclaimable_mb": round(total_reclaimable / (1024 * 1024), 2),
        "orphan_workdirs": len(orphan_workdirs),
        "orphan_workdirs_bytes": orphan_size,
        "orphan_workdirs_mb": round(orphan_size / (1024 * 1024), 2),
        "orphan_jobs": orphan_jobs.count(),
    }

