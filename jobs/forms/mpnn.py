from __future__ import annotations

from django import forms

from jobs.forms.shared import name_field, validate_pdb_upload


class ProteinMPNNSubmitForm(forms.Form):
    name = name_field()
    pdb_file = forms.FileField(
        required=True,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdb"}
        ),
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
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "A, B...",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
        help_text="Comma-separated chain IDs (e.g., A,B). Leave blank to design all chains.",
    )
    fixed_residues = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "1 2 3 4...",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
        help_text="Space-separated residue numbers to keep fixed.",
    )
    seed = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Random seed for reproducibility.",
    )

    def clean_pdb_file(self):
        pdb_file = self.cleaned_data.get("pdb_file")
        validate_pdb_upload(pdb_file)
        return pdb_file


class LigandMPNNSubmitForm(forms.Form):
    name = name_field()
    pdb_file = forms.FileField(
        required=True,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdb"}
        ),
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
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "A, B...",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
        help_text="Comma-separated chain IDs (e.g., A,B). Leave blank to design all chains.",
    )
    fixed_residues = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "1 2 3 4...",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
        help_text="Space-separated residue numbers to keep fixed.",
    )
    seed = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Random seed for reproducibility.",
    )

    def clean_pdb_file(self):
        pdb_file = self.cleaned_data.get("pdb_file")
        validate_pdb_upload(pdb_file)
        return pdb_file
