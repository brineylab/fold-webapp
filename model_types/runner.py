from __future__ import annotations

from django.core.exceptions import ValidationError

from jobs.forms import JobForm
from model_types.base import BaseModelType


class RunnerModelType(BaseModelType):
    key = "runner"
    name = "Runner-based submission"
    template_name = "jobs/submit.html"
    form_class = JobForm
    help_text = "Submit a job using an enabled runner."

    def validate(self, cleaned_data: dict) -> None:
        sequences = (cleaned_data.get("sequences") or "").strip()
        if not sequences:
            raise ValidationError("Sequences are required.")

    def normalize_inputs(self, cleaned_data: dict) -> dict:
        sequences = (cleaned_data.get("sequences") or "").strip()
        return {
            "sequences": sequences,
            "params": {},
        }

    def resolve_runner_key(self, cleaned_data: dict) -> str:
        return cleaned_data["runner"]
