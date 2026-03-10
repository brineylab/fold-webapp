from __future__ import annotations

from django import forms

from console.models import RunnerConfig
from runners import all_runners

# Widget type → Tailwind CSS class
_WIDGET_CSS = {
    forms.TextInput: "ui-input",
    forms.Textarea: "ui-input",
    forms.NumberInput: "ui-input",
    forms.EmailInput: "ui-input",
    forms.URLInput: "ui-input",
    forms.PasswordInput: "ui-input",
    forms.ClearableFileInput: "ui-input",
    forms.FileInput: "ui-input",
    forms.Select: "ui-select",
    forms.SelectMultiple: "ui-select",
    forms.CheckboxInput: "ui-checkbox",
}


class TailwindFormMixin:
    """Applies Tailwind CSS classes to form widgets automatically."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = _WIDGET_CSS.get(type(field.widget))
            if css_class:
                field.widget.attrs["class"] = css_class


def name_field() -> forms.CharField:
    return forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "spellcheck": "false",
            }
        ),
    )


def _looks_like_mmcif(uploaded_file) -> bool:
    name = (getattr(uploaded_file, "name", "") or "").lower()
    if name.endswith((".cif", ".mmcif")):
        return True

    try:
        pos = uploaded_file.tell()
    except Exception:
        pos = None

    try:
        header = uploaded_file.read(2048)
    finally:
        if pos is not None:
            try:
                uploaded_file.seek(pos)
            except Exception:
                pass

    if isinstance(header, str):
        text = header
    else:
        text = header.decode("utf-8", errors="ignore")

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped == "#":
            continue
        return (
            stripped.startswith("data_")
            or stripped.startswith("loop_")
            or stripped.startswith("_entry.")
            or stripped.startswith("_atom_site.")
        )
    return False


def validate_pdb_upload(uploaded_file) -> None:
    if uploaded_file and _looks_like_mmcif(uploaded_file):
        raise forms.ValidationError(
            "mmCIF uploads are not supported for this tool yet. Please upload a PDB file."
        )


def get_disabled_runners() -> list[dict]:
    """Return disabled runners with display metadata for the submit page."""
    all_keys = {runner.key for runner in all_runners()}
    enabled_keys = RunnerConfig.get_enabled_runners()
    disabled_keys = all_keys - enabled_keys

    result = []
    for runner in all_runners():
        if runner.key in disabled_keys:
            config = RunnerConfig.get_config(runner.key)
            result.append(
                {
                    "key": runner.key,
                    "name": runner.name,
                    "reason": config.disabled_reason or "Temporarily unavailable",
                }
            )
    return result
