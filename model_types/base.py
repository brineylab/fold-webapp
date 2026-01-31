from __future__ import annotations

from django import forms


class BaseModelType:
    key = ""
    name = ""
    template_name = ""
    form_class = forms.Form
    help_text = ""

    def get_form(self, *args, **kwargs) -> forms.Form:
        return self.form_class(*args, **kwargs)

    def validate(self, cleaned_data: dict) -> None:
        return None

    def normalize_inputs(self, cleaned_data: dict) -> dict:
        return dict(cleaned_data)

    def resolve_runner_key(self, cleaned_data: dict) -> str:
        raise NotImplementedError
