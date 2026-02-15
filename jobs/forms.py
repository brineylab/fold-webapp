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
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "spellcheck": "false",
        }),
    )
    sequences = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 12,
                "placeholder": ">seq1\nMKTAYI\u2026\n",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
        help_text=(
            "Paste one or more FASTA-formatted sequences. "
            "Multiple sequences will be modeled as a single multimeric complex."
        ),
    )
    input_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
        help_text=(
            "Upload a Boltz-2 YAML input file. "
            "When provided, the Sequences field is ignored. "
            "Multiple sequences will be modeled as a single multimeric complex."
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


class ProteinMPNNSubmitForm(forms.Form):
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "spellcheck": "false",
        }),
    )
    pdb_file = forms.FileField(
        required=True,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
        help_text="Upload a PDB file.",
    )
    noise_level = forms.ChoiceField(
        choices=[
            ("v_48_002", "0.02 (low noise)"),
            ("v_48_010", "0.10"),
            ("v_48_020", "0.20 (default)"),
            ("v_48_030", "0.30 (high noise)"),
        ],
        initial="v_48_020",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    temperature = forms.FloatField(
        required=False,
        min_value=0.0,
        max_value=2.0,
        initial=0.1,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        help_text="Sampling temperature (0.0 - 2.0).",
    )
    num_sequences = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        initial=8,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Number of sequences to generate.",
    )
    chains_to_design = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "A, B\u2026",
            "autocomplete": "off",
            "spellcheck": "false",
        }),
        help_text="Comma-separated chain IDs (e.g., A,B). Leave blank to design all chains.",
    )
    fixed_residues = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "1 2 3 4\u2026",
            "autocomplete": "off",
            "spellcheck": "false",
        }),
        help_text="Space-separated residue numbers to keep fixed.",
    )
    seed = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Random seed for reproducibility.",
    )


class Chai1SubmitForm(forms.Form):
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "spellcheck": "false",
        }),
    )
    sequences = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 12,
                "placeholder": ">protein_A\nMKTAYI\u2026\n>protein_B\nMAGFL\u2026\n",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
        help_text=(
            "Paste one or more FASTA-formatted sequences. "
            "Multiple sequences will be modeled as a single multimeric complex."
        ),
    )
    fasta_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
        help_text=(
            "Upload a FASTA file. When provided, the Sequences field is ignored. "
            "Multiple sequences in the file will be modeled as a single multimeric complex."
        ),
    )
    restraints_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
        help_text=(
            "Optional: upload a CSV restraints file specifying inter-chain contacts "
            "or covalent bonds. See Chai-1 documentation for the required CSV format."
        ),
    )
    use_msa_server = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Generate MSAs via the ColabFold mmseqs2 server (requires network access).",
    )
    num_diffn_samples = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=25,
        initial=5,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Number of diffusion samples to generate (default: 5).",
    )
    seed = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Random seed for reproducibility.",
    )

    def clean(self):
        cleaned = super().clean()
        has_sequences = bool((cleaned.get("sequences") or "").strip())
        has_file = bool(cleaned.get("fasta_file"))
        if not has_sequences and not has_file:
            raise forms.ValidationError(
                "Provide either sequences or a FASTA file."
            )
        return cleaned


class BindCraftSubmitForm(forms.Form):
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "spellcheck": "false",
        }),
    )
    pdb_file = forms.FileField(
        required=True,
        help_text="Upload the target protein structure in PDB format.",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdb"}),
    )
    target_chain = forms.CharField(
        required=True,
        initial="A",
        help_text="Chain ID of the target protein (e.g., A).",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    hotspot_residues = forms.CharField(
        required=False,
        help_text="Target residue positions for binder contact (comma-separated, e.g., 56,78,102). Leave blank for no hotspot bias.",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. 56,78,102",
        }),
    )
    length_min = forms.IntegerField(
        required=True,
        initial=65,
        min_value=20,
        max_value=500,
        help_text="Minimum binder length (amino acids).",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    length_max = forms.IntegerField(
        required=True,
        initial=150,
        min_value=20,
        max_value=500,
        help_text="Maximum binder length (amino acids).",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    number_of_final_designs = forms.IntegerField(
        required=True,
        initial=10,
        min_value=1,
        max_value=1000,
        help_text="Number of final binder designs to generate.",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    filters_file = forms.FileField(
        required=False,
        help_text="Optional: upload a custom filters JSON. Uses BindCraft defaults if omitted.",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".json"}),
    )
    advanced_file = forms.FileField(
        required=False,
        help_text="Optional: upload a custom advanced settings JSON. Uses BindCraft defaults if omitted.",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".json"}),
    )

    def clean(self):
        cleaned = super().clean()
        length_min = cleaned.get("length_min")
        length_max = cleaned.get("length_max")
        if length_min and length_max and length_min > length_max:
            raise forms.ValidationError(
                "Minimum binder length cannot exceed maximum length."
            )
        return cleaned


class LigandMPNNSubmitForm(forms.Form):
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "spellcheck": "false",
        }),
    )
    pdb_file = forms.FileField(
        required=True,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
        help_text="Upload a PDB file.",
    )
    noise_level = forms.ChoiceField(
        choices=[
            ("v_32_005_25", "0.05 (low noise)"),
            ("v_32_010_25", "0.10 (default)"),
            ("v_32_020_25", "0.20"),
            ("v_32_030_25", "0.30 (high noise)"),
        ],
        initial="v_32_010_25",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    temperature = forms.FloatField(
        required=False,
        min_value=0.0,
        max_value=2.0,
        initial=0.1,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
        help_text="Sampling temperature (0.0 - 2.0).",
    )
    num_sequences = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        initial=8,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Number of sequences to generate.",
    )
    chains_to_design = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "A, B\u2026",
            "autocomplete": "off",
            "spellcheck": "false",
        }),
        help_text="Comma-separated chain IDs (e.g., A,B). Leave blank to design all chains.",
    )
    fixed_residues = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "1 2 3 4\u2026",
            "autocomplete": "off",
            "spellcheck": "false",
        }),
        help_text="Space-separated residue numbers to keep fixed.",
    )
    seed = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Random seed for reproducibility.",
    )
