from __future__ import annotations

from django.db.models import Prefetch

from jobs.models import Job, JobAttempt


def _job_queryset_for(user):
    latest_attempts = Prefetch(
        "attempts",
        queryset=JobAttempt.objects.order_by("-attempt_number"),
        to_attr="prefetched_attempts",
    )
    return Job.objects.filter(owner=user, hidden_from_owner=False).select_related(
        "owner"
    ).prefetch_related(latest_attempts)
