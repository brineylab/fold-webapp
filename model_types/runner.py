from __future__ import annotations

from django import forms

from jobs.forms import JobForm, get_enabled_runner_choices
from model_types.base import BaseModelType, InputPayload


class RunnerModelType(BaseModelType):
    key = "runner"
    name = "Runner-based submission"
    template_name = "jobs/submit.html"
    form_class = JobForm
    help_text = "Submit a job using an enabled runner."

    def get_form(self, *args, **kwargs) -> forms.Form:
        form = super().get_form(*args, **kwargs)
        # Exclude runners that have their own dedicated ModelType
        from model_types.registry import get_dedicated_runner_keys

        dedicated = get_dedicated_runner_keys()
        form.fields["runner"].choices = get_enabled_runner_choices(
            exclude_keys=dedicated
        )
        return form

    def validate(self, cleaned_data: dict) -> None:
        # Form enforces that sequences is required and non-empty.
        # Add domain-specific cross-field checks here as needed.
        pass

    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        sequences = (cleaned_data.get("sequences") or "").strip()
        return {
            "sequences": sequences,
            "params": {},
            "files": {},
        }

    def resolve_runner_key(self, cleaned_data: dict) -> str:
        return cleaned_data["runner"]
