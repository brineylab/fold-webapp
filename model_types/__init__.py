from __future__ import annotations

from model_types.registry import get_default_model_type, get_model_type, register_model_type
from model_types.runner import RunnerModelType


register_model_type(RunnerModelType())

__all__ = ["get_default_model_type", "get_model_type", "register_model_type"]
