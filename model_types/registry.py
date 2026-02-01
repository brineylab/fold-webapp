from __future__ import annotations

from model_types.base import BaseModelType


MODEL_TYPES: dict[str, BaseModelType] = {}


def register_model_type(model_type: BaseModelType) -> BaseModelType:
    MODEL_TYPES[model_type.key] = model_type
    return model_type


def get_model_type(key: str) -> BaseModelType:
    return MODEL_TYPES[key]


def get_default_model_type() -> BaseModelType:
    return MODEL_TYPES["runner"]


def get_dedicated_runner_keys() -> set[str]:
    """Return the set of runner keys that have dedicated (non-generic) ModelTypes.

    These runners should be excluded from the generic runner dropdown since
    they have their own specialized submission forms.
    """
    keys: set[str] = set()
    for mt in MODEL_TYPES.values():
        runner_key = getattr(mt, "_runner_key", None)
        if runner_key:
            keys.add(runner_key)
    return keys


def get_submittable_model_types() -> list[BaseModelType]:
    """Return all registered model types suitable for the model selection page.

    Excludes the generic "runner" fallback if it would have no runners
    to offer (i.e., all runners have dedicated model types).
    """
    from jobs.forms import get_enabled_runner_choices

    result = []
    dedicated = get_dedicated_runner_keys()
    for mt in MODEL_TYPES.values():
        if mt.key == "runner":
            # Only include generic runner if it has non-dedicated runners
            if get_enabled_runner_choices(exclude_keys=dedicated):
                result.append(mt)
        else:
            result.append(mt)
    return result
