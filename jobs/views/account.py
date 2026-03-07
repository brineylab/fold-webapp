from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from console.services.audit import log_action


@login_required
def account_view(request):
    from api.models import APIKey
    from console.services.quota import get_user_quota

    quota = get_user_quota(request.user)
    api_keys = APIKey.objects.filter(user=request.user).order_by("-created_at")

    return render(
        request,
        "jobs/account.html",
        {
            "quota": quota,
            "api_keys": api_keys,
        },
    )


@login_required
@require_POST
def account_create_api_key(request):
    from api.models import APIKey
    from console.services.quota import get_user_quota

    quota = get_user_quota(request.user)
    if not quota.api_enabled:
        messages.error(request, "API access is not enabled for your account.")
        return redirect("account")

    label = request.POST.get("label", "").strip()
    api_key = APIKey(user=request.user, label=label)
    api_key.save()
    log_action(
        scope="api",
        action="api_key_created",
        actor=request.user,
        source="account",
        target_user=request.user,
        message="Created API key from the account page.",
        metadata={"label": label},
    )

    messages.success(
        request,
        f"API key created. Copy it now - it cannot be shown again: {api_key.key}",
    )
    return redirect("account")


@login_required
@require_POST
def account_revoke_api_key(request, key_id):
    from api.models import APIKey

    api_key = get_object_or_404(APIKey, id=key_id, user=request.user)
    label = api_key.label
    api_key.is_active = False
    api_key.save(update_fields=["is_active"])
    log_action(
        scope="api",
        action="api_key_revoked",
        actor=request.user,
        source="account",
        target_user=request.user,
        message="Revoked API key from the account page.",
        metadata={"label": label},
    )

    messages.success(request, "API key revoked.")
    return redirect("account")
