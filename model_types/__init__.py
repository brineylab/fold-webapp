from __future__ import annotations

from model_types.base import InputPayload
from model_types.boltz2 import Boltz2ModelType
from model_types.registry import get_default_model_type, get_model_type, register_model_type
from model_types.runner import RunnerModelType


register_model_type(RunnerModelType())
register_model_type(Boltz2ModelType())

__all__ = [
    "InputPayload",
    "get_default_model_type",
    "get_model_type",
    "register_model_type",
]
