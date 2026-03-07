from __future__ import annotations

from django import forms as djforms
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from api.auth import api_auth_required
from model_types import get_submittable_model_types


def _field_schema(field) -> dict:
    info = {
        "required": field.required,
        "help_text": str(field.help_text) if field.help_text else "",
    }
    if hasattr(field, "choices") and field.choices:
        info["choices"] = [{"value": value, "label": label} for value, label in field.choices]
    if hasattr(field, "min_value") and field.min_value is not None:
        info["min_value"] = field.min_value
    if hasattr(field, "max_value") and field.max_value is not None:
        info["max_value"] = field.max_value
    if hasattr(field, "initial") and field.initial is not None:
        info["default"] = field.initial

    if isinstance(field, djforms.BooleanField):
        info["type"] = "boolean"
    elif isinstance(field, djforms.IntegerField):
        info["type"] = "integer"
    elif isinstance(field, djforms.FloatField):
        info["type"] = "number"
    elif isinstance(field, djforms.FileField):
        info["type"] = "file"
    elif isinstance(field, djforms.ChoiceField):
        info["type"] = "choice"
    else:
        info["type"] = "string"
    return info


@csrf_exempt
@api_auth_required
@require_GET
def model_list(request):
    models = []
    for model_type in get_submittable_model_types():
        form = model_type.get_form()
        params = {}
        for field_name, field in form.fields.items():
            if field_name == "name":
                continue
            params[field_name] = _field_schema(field)

        models.append(
            {
                "key": model_type.key,
                "name": model_type.name,
                "category": model_type.category,
                "help_text": model_type.help_text,
                "parameters": params,
            }
        )

    return JsonResponse({"models": models})
