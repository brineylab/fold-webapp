from __future__ import annotations

import secrets
import string

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from console.decorators import console_required, superops_required
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
    users = users[:200]
    
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
        "running": Job.objects.filter(owner=user, status=Job.Status.RUNNING).count(),
        "pending": Job.objects.filter(owner=user, status=Job.Status.PENDING).count(),
    }

    # API keys
    from api.models import APIKey

    api_keys = APIKey.objects.filter(user=user).order_by("-created_at")

    context = {
        "user_obj": user,
        "quota": quota,
        "quota_status": quota_status,
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
    
    try:
        quota.max_concurrent_jobs = int(request.POST.get("max_concurrent_jobs", quota.max_concurrent_jobs))
        quota.max_queued_jobs = int(request.POST.get("max_queued_jobs", quota.max_queued_jobs))
        quota.jobs_per_day = int(request.POST.get("jobs_per_day", quota.jobs_per_day))
        quota.retention_days = int(request.POST.get("retention_days", quota.retention_days))
        quota.save()
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
    
    messages.success(request, f"Account disabled for {user.username}.")
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
    
    messages.success(request, f"Account enabled for {user.username}.")
    return redirect("console:user_detail", user_id=user_id)


@superops_required
@require_POST
def user_reset_password(request, user_id):
    """
    Generate a temporary password for the user.
    
    In production, you'd typically send a password reset email instead.
    This is a simple implementation for admin-initiated resets.
    """
    user = get_object_or_404(User, id=user_id)
    
    # Prevent resetting your own password via this method
    if user == request.user:
        messages.error(request, "Please use the standard password change flow for your own account.")
        return redirect("console:user_detail", user_id=user_id)
    
    # Generate a random temporary password
    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for _ in range(16))
    
    user.password = make_password(temp_password)
    user.save(update_fields=["password"])
    
    # In production, you'd email this or use Django's password reset flow
    messages.success(
        request,
        f"Password reset for {user.username}. Temporary password: {temp_password} "
        "(Please share this securely with the user)"
    )
    
    return redirect("console:user_detail", user_id=user_id)


@superops_required
@require_POST
def user_toggle_active(request, user_id):
    """Toggle a user's is_active status (Django's built-in account active flag)."""
    user = get_object_or_404(User, id=user_id)
    
    # Prevent deactivating yourself
    if user == request.user:
        messages.error(request, "You cannot deactivate your own account.")
        return redirect("console:user_detail", user_id=user_id)
    
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    
    status = "activated" if user.is_active else "deactivated"
    messages.success(request, f"Account {status} for {user.username}.")
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

    messages.success(request, f"API key revoked for {user.username}.")
    return redirect("console:user_detail", user_id=user_id)


@console_required
@require_POST
def user_delete_api_key(request, user_id, key_id):
    """Permanently delete an API key."""
    from api.models import APIKey

    user = get_object_or_404(User, id=user_id)
    api_key = get_object_or_404(APIKey, id=key_id, user=user)

    api_key.delete()

    messages.success(request, f"API key deleted for {user.username}.")
    return redirect("console:user_detail", user_id=user_id)

