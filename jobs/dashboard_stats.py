from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count
from django.utils import timezone

from jobs.models import Job


def get_user_dashboard_stats(user) -> dict[str, Any]:
    """
    Get dashboard statistics scoped to a single user's visible jobs.
    """
    now = timezone.now()
    last_24h = now - timedelta(hours=24)

    all_jobs = Job.objects.filter(owner=user, hidden_from_owner=False)
    jobs_24h = all_jobs.filter(created_at__gte=last_24h)

    status_counts_all = dict(
        all_jobs.values("status").annotate(count=Count("id")).values_list("status", "count")
    )
    status_counts_24h = dict(
        jobs_24h.values("status").annotate(count=Count("id")).values_list("status", "count")
    )

    queue_depth = all_jobs.filter(status=Job.Status.PENDING).count()

    recent_failures = list(
        all_jobs.filter(status=Job.Status.FAILED)
        .order_by("-completed_at")[:5]
        .values("id", "name", "error_message", "completed_at")
    )

    return {
        "status_counts_all": {
            "pending": status_counts_all.get(Job.Status.PENDING, 0),
            "running": status_counts_all.get(Job.Status.RUNNING, 0),
            "completed": status_counts_all.get(Job.Status.COMPLETED, 0),
            "failed": status_counts_all.get(Job.Status.FAILED, 0),
            "cancelled": status_counts_all.get(Job.Status.CANCELLED, 0),
        },
        "status_counts_24h": {
            "pending": status_counts_24h.get(Job.Status.PENDING, 0),
            "running": status_counts_24h.get(Job.Status.RUNNING, 0),
            "completed": status_counts_24h.get(Job.Status.COMPLETED, 0),
            "failed": status_counts_24h.get(Job.Status.FAILED, 0),
            "cancelled": status_counts_24h.get(Job.Status.CANCELLED, 0),
        },
        "queue_depth": queue_depth,
        "recent_failures": recent_failures,
        "total_jobs": all_jobs.count(),
        "jobs_24h": jobs_24h.count(),
    }
