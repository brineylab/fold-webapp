from __future__ import annotations

from model_types import get_model_types_by_category


def sidebar_context(request):
    if not request.user.is_authenticated:
        return {}

    return {
        "sidebar_model_categories": get_model_types_by_category(),
    }
