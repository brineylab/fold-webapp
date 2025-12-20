from __future__ import annotations

from functools import wraps

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied


def console_required(view_func):
    """
    Decorator that requires the user to be a staff member to access the view.
    
    This wraps Django's staff_member_required but provides a consistent
    entry point for future role-based access control (e.g., ops vs superops).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    
    return staff_member_required(wrapper)


def ops_required(view_func):
    """
    Decorator for operations that require 'ops' role.
    
    Currently just checks is_staff, but can be extended to check
    Django Groups/Permissions for finer-grained access control.
    
    Usage:
        @ops_required
        def my_view(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("Staff access required")
        # Future: check for 'ops' group membership
        # if not request.user.groups.filter(name='ops').exists():
        #     raise PermissionDenied("Ops role required")
        return view_func(request, *args, **kwargs)
    
    return wrapper


def superops_required(view_func):
    """
    Decorator for sensitive operations that require 'superops' role.
    
    Currently checks is_superuser, but can be extended to check
    Django Groups/Permissions for finer-grained access control.
    
    Usage:
        @superops_required
        def sensitive_view(request):
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied("Staff access required")
        if not request.user.is_superuser:
            raise PermissionDenied("Superuser access required")
        # Future: check for 'superops' group membership
        return view_func(request, *args, **kwargs)
    
    return wrapper

