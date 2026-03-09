from __future__ import annotations

from django import forms

from jobs.forms.shared import name_field


class Chai1SubmitForm(forms.Form):
    name = name_field()
    sequences = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 12,
                "placeholder": ">protein_A\nMKTAYI...\n>protein_B\nMAGFL...\n",
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
            raise forms.ValidationError("Provide either sequences or a FASTA file.")
        return cleaned
