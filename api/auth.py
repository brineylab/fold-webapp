from __future__ import annotations

from functools import wraps

from django.http import JsonResponse
from django.utils import timezone

from api.models import APIKey


def api_auth_required(view_func):
    """Decorator that authenticates API requests via Bearer token.

    Reads the ``Authorization: Bearer <key>`` header, verifies the key
    is active, checks that the user has API access enabled, and sets
    ``request.user``.
    """

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth_header.startswith("Bearer "):
            return JsonResponse(
                {"error": "Missing or malformed Authorization header. Use: Bearer <key>"},
                status=401,
            )

        token = auth_header[7:].strip()
        if not token:
            return JsonResponse({"error": "Empty API key."}, status=401)

        try:
            api_key = APIKey.objects.select_related("user").get(key=token)
        except APIKey.DoesNotExist:
            return JsonResponse({"error": "Invalid API key."}, status=401)

        if not api_key.is_active:
            return JsonResponse({"error": "API key has been revoked."}, status=401)

        user = api_key.user
        if not user.is_active:
            return JsonResponse({"error": "User account is inactive."}, status=403)

        # Check api_enabled on quota (import here to avoid circular imports)
        from console.services.quota import get_user_quota

        quota = get_user_quota(user)
        if not quota.api_enabled:
            return JsonResponse(
                {"error": "API access is not enabled for your account."},
                status=403,
            )

        # Update last_used_at for audit visibility
        api_key.last_used_at = timezone.now()
        api_key.save(update_fields=["last_used_at"])

        request.user = user
        request._api_key = api_key
        return view_func(request, *args, **kwargs)

    return wrapper
