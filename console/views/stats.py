from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, Count, F
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone

from console.decorators import console_required
from jobs.models import Job


def _get_stats_summary() -> dict:
    """
    Generate summary statistics for jobs.
    
    Returns:
        Dictionary suitable for JSON serialization or template rendering.
    """
    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    
    # Jobs by day (last 30 days)
    jobs_by_day = list(
        Job.objects.filter(created_at__gte=last_30_days)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    # Convert dates to strings for JSON serialization
    for entry in jobs_by_day:
        entry["date"] = entry["date"].isoformat() if entry["date"] else None
    
    # Jobs by runner
    jobs_by_runner = dict(
        Job.objects.values("runner")
        .annotate(count=Count("id"))
        .values_list("runner", "count")
    )
    
    # Jobs by status
    jobs_by_status = dict(
        Job.objects.values("status")
        .annotate(count=Count("id"))
        .values_list("status", "count")
    )
    
    avg_runtime = (
        Job.objects.filter(
            status=Job.Status.COMPLETED,
            run_seconds__isnull=False,
        ).aggregate(avg_runtime=Avg("run_seconds"))["avg_runtime"]
    )
    
    return {
        "jobs_by_day": jobs_by_day,
        "jobs_by_runner": jobs_by_runner,
        "jobs_by_status": jobs_by_status,
        "avg_runtime_seconds": avg_runtime,
        "total_jobs": Job.objects.count(),
        "jobs_last_30_days": Job.objects.filter(created_at__gte=last_30_days).count(),
    }


@console_required
def stats(request):
    """Stats dashboard with placeholder cards for future charts."""
    summary = _get_stats_summary()
    return render(request, "console/stats.html", {"summary": summary})


@console_required
def stats_api_summary(request):
    """JSON API endpoint for stats summary data."""
    summary = _get_stats_summary()
    return JsonResponse(summary)
