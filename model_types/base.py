from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict

from django import forms


class InputPayload(TypedDict):
    """Typed contract between normalize_inputs() and the service layer.

    Every ModelType.normalize_inputs() must return a dict matching this shape.
    """

    sequences: str
    """FASTA text. Empty string for models that don't use FASTA input."""

    params: dict
    """Model-specific parameters, stored in Job.params."""

    files: dict[str, bytes]
    """Filename -> content for uploaded files to write to the job workdir."""


class BaseModelType(ABC):
    key: str = ""
    name: str = ""
    template_name: str = ""
    form_class: type[forms.Form] = forms.Form
    help_text: str = ""

    def get_form(self, *args, **kwargs) -> forms.Form:
        return self.form_class(*args, **kwargs)

    @abstractmethod
    def validate(self, cleaned_data: dict) -> None:
        """Model-specific validation beyond what the form enforces.

        Raise ``ValidationError`` on failure.  Do **not** duplicate form-level
        required-field checks here -- the form already handles those.  Use this
        for cross-field constraints and domain-specific rules only (e.g.
        "multi-chain complexes require at least two sequences").
        """
        ...

    @abstractmethod
    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        """Convert form *cleaned_data* into a typed :class:`InputPayload`.

        Must return a dict with ``sequences``, ``params``, and ``files`` keys.
        """
        ...

    @abstractmethod
    def resolve_runner_key(self, cleaned_data: dict) -> str:
        """Return the runner key to use for this submission."""
        ...
