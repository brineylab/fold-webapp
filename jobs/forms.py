from __future__ import annotations

from django import forms

from console.models import RunnerConfig
from runners import all_runners


def get_disabled_runners() -> list[dict]:
    """
    Get list of disabled runners with their details.

    Returns list of dicts with 'key', 'name', and 'reason' for disabled runners.
    """
    all_keys = {r.key for r in all_runners()}
    enabled_keys = RunnerConfig.get_enabled_runners()
    disabled_keys = all_keys - enabled_keys

    result = []
    for runner in all_runners():
        if runner.key in disabled_keys:
            config = RunnerConfig.get_config(runner.key)
            result.append({
                "key": runner.key,
                "name": runner.name,
                "reason": config.disabled_reason or "Temporarily unavailable",
            })
    return result


class Boltz2SubmitForm(forms.Form):
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    sequences = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 12,
                "placeholder": ">seq1\nMKTAYI...\n",
            }
        ),
        help_text="Paste one or more FASTA-formatted sequences.",
    )
    input_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
        help_text=(
            "Upload a Boltz-2 YAML input file. "
            "When provided, the Sequences field is ignored."
        ),
    )
    use_msa_server = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Generate MSAs via the mmseqs2 server (requires network access).",
    )
    use_potentials = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Apply inference-time potentials for improved physical plausibility.",
    )
    output_format = forms.ChoiceField(
        required=False,
        choices=[("mmcif", "mmCIF"), ("pdb", "PDB")],
        widget=forms.Select(attrs={"class": "form-select"}),
        initial="mmcif",
        help_text="Select the output structure format.",
    )
    recycling_steps = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Optional number of recycling steps (default: Boltz-2 setting).",
    )
    sampling_steps = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Optional number of sampling steps (default: Boltz-2 setting).",
    )
    diffusion_samples = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Optional number of diffusion samples (default: Boltz-2 setting).",
    )

    def clean(self):
        cleaned = super().clean()
        has_sequences = bool((cleaned.get("sequences") or "").strip())
        has_file = bool(cleaned.get("input_file"))
        if not has_sequences and not has_file:
            raise forms.ValidationError(
                "Provide either sequences or an input file."
            )
        return cleaned
