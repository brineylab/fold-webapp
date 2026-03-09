from __future__ import annotations

from functools import wraps

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied


def console_required(view_func):
    """
    Require a staff user for console access.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    
    return staff_member_required(wrapper)


def superops_required(view_func):
    """
    Require a superuser for destructive console actions.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("Staff access required")
        if not request.user.is_superuser:
            raise PermissionDenied("Superuser access required")
        return view_func(request, *args, **kwargs)
    
    return wrapper
