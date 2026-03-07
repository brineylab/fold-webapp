from __future__ import annotations

from jobs.services import cancel_job as shared_cancel_job
from jobs.services import hide_job_from_owner as shared_hide_job_from_owner


def cancel_job(job, actor) -> bool:
    return shared_cancel_job(job, actor=actor, source="admin")


def bulk_cancel_jobs(queryset, actor) -> int:
    cancelled_count = 0
    for job in queryset.iterator():
        if cancel_job(job, actor):
            cancelled_count += 1
    return cancelled_count


def hide_job_from_owner(job, actor) -> bool:
    return shared_hide_job_from_owner(job, actor=actor, source="admin")


def bulk_hide_jobs(queryset, actor) -> int:
    hidden_count = 0
    for job in queryset.iterator():
        if hide_job_from_owner(job, actor):
            hidden_count += 1
    return hidden_count
