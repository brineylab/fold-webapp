from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from console.decorators import console_required, superops_required
from console.services.audit import log_action
from console.models import UserQuota
from console.services.quota import get_user_quota, get_quota_status
from jobs.models import Job

User = get_user_model()


@console_required
def user_list(request):
    """List all users with search/filter, job counts, and quota status."""
    users = User.objects.annotate(
        total_jobs=Count("job"),
        running_jobs=Count("job", filter=Q(job__status=Job.Status.RUNNING)),
        pending_jobs=Count("job", filter=Q(job__status=Job.Status.PENDING)),
    ).select_related("quota").order_by("-date_joined")
    
    # Search
    search = request.GET.get("search", "").strip()
    if search:
        users = users.filter(
            Q(username__icontains=search) |
            Q(email__icontains=search) |
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)
        )
    
    # Filter by status
    status = request.GET.get("status", "")
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)
    elif status == "staff":
        users = users.filter(is_staff=True)
    elif status == "disabled":
        users = users.filter(quota__is_disabled=True)
    
    # Pagination (simple limit for now)
    users = list(users[:200])
    quota_map = {
        quota.user_id: quota
        for quota in UserQuota.objects.filter(user_id__in=[user.id for user in users])
    }
    for user in users:
        user.policy_quota = quota_map.get(user.id)
    
    context = {
        "users": users,
        "search": search,
        "status": status,
    }
    return render(request, "console/users/list.html", context)


@console_required
def user_detail(request, user_id):
    """View user profile, job history, and quota settings."""
    user = get_object_or_404(
        User.objects.select_related("quota"),
        id=user_id,
    )
    
    # Get or create quota
    quota = get_user_quota(user)
    quota_status = get_quota_status(user)
    
    # Get recent jobs
    recent_jobs = Job.objects.filter(owner=user).order_by("-created_at")[:20]
    
    # Job statistics
    job_stats = {
        "total": Job.objects.filter(owner=user).count(),
        "completed": Job.objects.filter(owner=user, status=Job.Status.COMPLETED).count(),
        "failed": Job.objects.filter(owner=user, status=Job.Status.FAILED).count(),
        "cancelled": Job.objects.filter(owner=user, status=Job.Status.CANCELLED).count(),
        "running": Job.objects.filter(owner=user, status=Job.Status.RUNNING).count(),
        "pending": Job.objects.filter(owner=user, status=Job.Status.PENDING).count(),
    }

    # API keys
    from api.models import APIKey

    api_keys = APIKey.objects.filter(user=user).order_by("-created_at")

    context = {
        "user_obj": user,
        "admin_change_url": reverse(
            f"admin:{user._meta.app_label}_{user._meta.model_name}_change",
            args=[user.id],
        ),
        "quota": quota,
        "quota_status": quota_status,
        "priority_tier_choices": UserQuota.PriorityTier.choices,
        "recent_jobs": recent_jobs,
        "job_stats": job_stats,
        "api_keys": api_keys,
    }
    return render(request, "console/users/detail.html", context)


@console_required
@require_POST
def user_update_quota(request, user_id):
    """Update a user's quota settings."""
    user = get_object_or_404(User, id=user_id)
    quota = get_user_quota(user)
    before = {
        "priority_tier": quota.priority_tier,
        "max_concurrent_jobs": quota.max_concurrent_jobs,
        "max_queued_jobs": quota.max_queued_jobs,
        "jobs_per_day": quota.jobs_per_day,
        "jobs_per_month": quota.jobs_per_month,
        "retention_days": quota.retention_days,
    }
    
    try:
        quota.max_concurrent_jobs = int(request.POST.get("max_concurrent_jobs", quota.max_concurrent_jobs))
        quota.max_queued_jobs = int(request.POST.get("max_queued_jobs", quota.max_queued_jobs))
        quota.jobs_per_day = int(request.POST.get("jobs_per_day", quota.jobs_per_day))
        quota.jobs_per_month = int(request.POST.get("jobs_per_month", quota.jobs_per_month))
        quota.retention_days = int(request.POST.get("retention_days", quota.retention_days))
        priority_tier = request.POST.get("priority_tier", quota.priority_tier)
        if priority_tier in {choice[0] for choice in UserQuota.PriorityTier.choices}:
            quota.priority_tier = priority_tier
        quota.save()
        after = {
            "priority_tier": quota.priority_tier,
            "max_concurrent_jobs": quota.max_concurrent_jobs,
            "max_queued_jobs": quota.max_queued_jobs,
            "jobs_per_day": quota.jobs_per_day,
            "jobs_per_month": quota.jobs_per_month,
            "retention_days": quota.retention_days,
        }
        log_action(
            scope="policy",
            action="quota_updated",
            actor=request.user,
            source="console",
            target_user=user,
            message=f"Updated quota policy for {user.username}.",
            metadata={"before": before, "after": after},
        )
        messages.success(request, f"Quota settings updated for {user.username}.")
    except (ValueError, TypeError) as e:
        messages.error(request, f"Invalid quota value: {e}")
    
    return redirect("console:user_detail", user_id=user_id)


@superops_required
@require_POST
def user_disable(request, user_id):
    """Disable a user's account (prevent new job submissions)."""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent disabling yourself
    if user == request.user:
        messages.error(request, "You cannot disable your own account.")
        return redirect("console:user_detail", user_id=user_id)
    
    quota = get_user_quota(user)
    reason = request.POST.get("reason", "").strip() or "Disabled by admin"
    
    quota.is_disabled = True
    quota.disabled_reason = reason
    quota.disabled_at = timezone.now()
    quota.save()
    log_action(
        scope="policy",
        action="submissions_disabled",
        actor=request.user,
        source="console",
        target_user=user,
        message=f"Disabled new job submissions for {user.username}.",
        metadata={"reason": reason},
    )
    
    messages.success(request, f"New job submissions disabled for {user.username}.")
    return redirect("console:user_detail", user_id=user_id)


@superops_required
@require_POST
def user_enable(request, user_id):
    """Re-enable a user's account."""
    user = get_object_or_404(User, id=user_id)
    quota = get_user_quota(user)
    
    quota.is_disabled = False
    quota.disabled_reason = ""
    quota.disabled_at = None
    quota.save()
    log_action(
        scope="policy",
        action="submissions_enabled",
        actor=request.user,
        source="console",
        target_user=user,
        message=f"Re-enabled job submissions for {user.username}.",
    )
    
    messages.success(request, f"New job submissions enabled for {user.username}.")
    return redirect("console:user_detail", user_id=user_id)


# ---------------------------------------------------------------------------
# API access & key management
# ---------------------------------------------------------------------------


@console_required
@require_POST
def user_toggle_api_access(request, user_id):
    """Toggle api_enabled on a user's quota."""
    user = get_object_or_404(User, id=user_id)
    quota = get_user_quota(user)

    quota.api_enabled = not quota.api_enabled
    quota.save(update_fields=["api_enabled"])
    log_action(
        scope="api",
        action="api_access_enabled" if quota.api_enabled else "api_access_disabled",
        actor=request.user,
        source="console",
        target_user=user,
        message=(
            f"API access {'enabled' if quota.api_enabled else 'disabled'} "
            f"for {user.username}."
        ),
        metadata={"api_enabled": quota.api_enabled},
    )

    status = "enabled" if quota.api_enabled else "disabled"
    messages.success(request, f"API access {status} for {user.username}.")
    return redirect("console:user_detail", user_id=user_id)


@console_required
@require_POST
def user_create_api_key(request, user_id):
    """Create an API key for a user."""
    from api.models import APIKey

    user = get_object_or_404(User, id=user_id)
    label = request.POST.get("label", "").strip()

    api_key = APIKey(user=user, label=label)
    api_key.save()
    log_action(
        scope="api",
        action="api_key_created",
        actor=request.user,
        source="console",
        target_user=user,
        message=f"Created API key for {user.username}.",
        metadata={"label": label},
    )

    messages.success(
        request,
        f"API key created for {user.username}. "
        f"Copy it now \u2014 it cannot be shown again: {api_key.key}",
    )
    return redirect("console:user_detail", user_id=user_id)


@console_required
@require_POST
def user_revoke_api_key(request, user_id, key_id):
    """Revoke (deactivate) an API key."""
    from api.models import APIKey

    user = get_object_or_404(User, id=user_id)
    api_key = get_object_or_404(APIKey, id=key_id, user=user)

    api_key.is_active = False
    api_key.save(update_fields=["is_active"])
    log_action(
        scope="api",
        action="api_key_revoked",
        actor=request.user,
        source="console",
        target_user=user,
        message=f"Revoked API key for {user.username}.",
        metadata={"label": api_key.label},
    )

    messages.success(request, f"API key revoked for {user.username}.")
    return redirect("console:user_detail", user_id=user_id)


@console_required
@require_POST
def user_delete_api_key(request, user_id, key_id):
    """Permanently delete an API key."""
    from api.models import APIKey

    user = get_object_or_404(User, id=user_id)
    api_key = get_object_or_404(APIKey, id=key_id, user=user)
    label = api_key.label
    api_key.delete()

    log_action(
        scope="api",
        action="api_key_deleted",
        actor=request.user,
        source="console",
        target_user=user,
        message=f"Deleted API key for {user.username}.",
        metadata={"label": label},
    )

    messages.success(request, f"API key deleted for {user.username}.")
    return redirect("console:user_detail", user_id=user_id)
