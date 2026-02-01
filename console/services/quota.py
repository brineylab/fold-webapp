from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from console.models import UserQuota
from jobs.models import Job

if TYPE_CHECKING:
    from django.contrib.auth.models import User


def get_user_quota(user: User) -> UserQuota:
    """
    Get or create a UserQuota for the given user.
    
    Uses default values from settings if available, otherwise model defaults.
    """
    quota, created = UserQuota.objects.get_or_create(
        user=user,
        defaults={
            "max_concurrent_jobs": getattr(settings, "DEFAULT_MAX_CONCURRENT_JOBS", 1),
            "max_queued_jobs": getattr(settings, "DEFAULT_MAX_QUEUED_JOBS", 5),
            "jobs_per_day": getattr(settings, "DEFAULT_JOBS_PER_DAY", 10),
            "retention_days": getattr(settings, "DEFAULT_RETENTION_DAYS", 30),
        },
    )
    return quota


def is_quota_exempt(user: User) -> bool:
    """
    Check if user is exempt from quota limits.
    
    Staff users are exempt by default.
    """
    return user.is_staff


def check_quota(user: User) -> tuple[bool, str | None]:
    """
    Check if a user is allowed to submit a new job based on their quota.
    
    Returns:
        Tuple of (allowed, error_message).
        If allowed is True, error_message is None.
        If allowed is False, error_message explains why.
    """
    # Staff users are exempt from quotas
    if is_quota_exempt(user):
        return True, None
    
    quota = get_user_quota(user)
    
    # Check if account is disabled
    if quota.is_disabled:
        reason = quota.disabled_reason or "Account is disabled"
        return False, f"Your account has been disabled: {reason}"
    
    # Check concurrent jobs (RUNNING status)
    running_count = Job.objects.filter(
        owner=user,
        status=Job.Status.RUNNING,
    ).count()
    
    if running_count >= quota.max_concurrent_jobs:
        return False, (
            f"You have reached the maximum number of concurrent jobs "
            f"({quota.max_concurrent_jobs}). Please wait for a job to complete."
        )
    
    # Check queued jobs (PENDING status)
    pending_count = Job.objects.filter(
        owner=user,
        status=Job.Status.PENDING,
    ).count()
    
    if pending_count >= quota.max_queued_jobs:
        return False, (
            f"You have reached the maximum number of queued jobs "
            f"({quota.max_queued_jobs}). Please wait for some jobs to start running."
        )
    
    # Check daily submission limit
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    jobs_today = Job.objects.filter(
        owner=user,
        created_at__gte=today_start,
    ).count()
    
    if jobs_today >= quota.jobs_per_day:
        return False, (
            f"You have reached the maximum number of jobs per day "
            f"({quota.jobs_per_day}). Please try again tomorrow."
        )
    
    return True, None


def get_quota_status(user: User) -> dict:
    """
    Get detailed quota status for a user.
    
    Returns a dictionary with current usage and limits.
    """
    quota = get_user_quota(user)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    running_count = Job.objects.filter(
        owner=user,
        status=Job.Status.RUNNING,
    ).count()
    
    pending_count = Job.objects.filter(
        owner=user,
        status=Job.Status.PENDING,
    ).count()
    
    jobs_today = Job.objects.filter(
        owner=user,
        created_at__gte=today_start,
    ).count()
    
    return {
        "is_exempt": is_quota_exempt(user),
        "is_disabled": quota.is_disabled,
        "disabled_reason": quota.disabled_reason,
        "concurrent_jobs": {
            "current": running_count,
            "max": quota.max_concurrent_jobs,
            "remaining": max(0, quota.max_concurrent_jobs - running_count),
        },
        "queued_jobs": {
            "current": pending_count,
            "max": quota.max_queued_jobs,
            "remaining": max(0, quota.max_queued_jobs - pending_count),
        },
        "daily_jobs": {
            "current": jobs_today,
            "max": quota.jobs_per_day,
            "remaining": max(0, quota.jobs_per_day - jobs_today),
        },
        "retention_days": quota.retention_days,
    }

