from __future__ import annotations

from uuid import UUID

from django.db.models import Q
from django.shortcuts import render

from console.decorators import console_required
from console.models import ActionLog
from jobs.models import Job, JobAttempt


@console_required
def audit_log(request):
    """Focused operations log backed by action records and job attempts."""
    log_qs = ActionLog.objects.select_related("actor", "job", "target_user")

    user_filter = request.GET.get("user", "").strip()
    if user_filter:
        log_qs = log_qs.filter(
            Q(actor__username__icontains=user_filter)
            | Q(target_user__username__icontains=user_filter)
            | Q(target_label__icontains=user_filter)
        )

    scope_filter = request.GET.get("scope", "").strip()
    valid_scopes = {choice[0] for choice in ActionLog.Scope.choices}
    if scope_filter in valid_scopes:
        log_qs = log_qs.filter(scope=scope_filter)

    job_filter = request.GET.get("job", "").strip()
    job_context = None
    job_attempts = []
    job_filter_error = ""
    if job_filter:
        try:
            job_uuid = UUID(job_filter)
        except ValueError:
            job_uuid = None
            job_filter_error = "Use a full job UUID to inspect a specific job timeline."

        if job_uuid is not None:
            log_qs = log_qs.filter(job_id=job_uuid)
            job_context = Job.objects.select_related("owner").filter(id=job_uuid).first()
            if job_context is not None:
                job_attempts = list(
                    JobAttempt.objects.filter(job=job_context).order_by("-attempt_number")
                )

    context = {
        "job_attempts": job_attempts,
        "job_context": job_context,
        "job_filter": job_filter,
        "job_filter_error": job_filter_error,
        "scope_filter": scope_filter,
        "scope_choices": ActionLog.Scope.choices,
        "user_filter": user_filter,
        "action_logs": list(log_qs[:200]),
    }
    return render(request, "console/audit.html", context)
