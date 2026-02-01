from __future__ import annotations

from model_types.base import BaseModelType


MODEL_TYPES: dict[str, BaseModelType] = {}


def register_model_type(model_type: BaseModelType) -> BaseModelType:
    MODEL_TYPES[model_type.key] = model_type
    return model_type


def get_model_type(key: str) -> BaseModelType:
    return MODEL_TYPES[key]


def get_submittable_model_types() -> list[BaseModelType]:
    """Return all registered model types suitable for the model selection page."""
    return list(MODEL_TYPES.values())
