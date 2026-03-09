from __future__ import annotations

from django import forms

from jobs.forms.shared import name_field


class Boltz2SubmitForm(forms.Form):
    name = name_field()
    sequences = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 12,
                "placeholder": ">seq1\nMKTAYI...\n",
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
    no_kernels = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text=(
            "Disable Boltz CUDA kernels. Useful for troubleshooting older GPUs "
            "or cuequivariance kernel failures."
        ),
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
            raise forms.ValidationError("Provide either sequences or an input file.")
        return cleaned


class BoltzGenSubmitForm(forms.Form):
    PROTOCOL_CHOICES = [
        ("protein-anything", "Protein binder (any target)"),
        ("peptide-anything", "Peptide binder (any target)"),
        ("protein-small_molecule", "Protein binder (small molecule target)"),
        ("nanobody-anything", "Nanobody (any target)"),
        ("yaml_upload", "Upload YAML specification"),
    ]

    name = name_field()
    protocol = forms.ChoiceField(
        choices=PROTOCOL_CHOICES,
        initial="protein-anything",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_protocol"}),
        help_text="Select the BoltzGen design protocol.",
    )
    target_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": ".pdb,.cif,.mmcif",
            }
        ),
        help_text="Upload the target structure (PDB or CIF format).",
    )
    target_chains = forms.CharField(
        required=False,
        initial="A",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "A",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
        help_text="Comma-separated chain IDs to target (e.g., A or A,B).",
    )
    binder_length_min = forms.IntegerField(
        required=False,
        min_value=20,
        max_value=500,
        initial=80,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Minimum binder length in residues.",
    )
    binder_length_max = forms.IntegerField(
        required=False,
        min_value=20,
        max_value=500,
        initial=150,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Maximum binder length in residues.",
    )
    peptide_length_min = forms.IntegerField(
        required=False,
        min_value=3,
        max_value=50,
        initial=8,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Minimum peptide length in residues.",
    )
    peptide_length_max = forms.IntegerField(
        required=False,
        min_value=3,
        max_value=50,
        initial=20,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Maximum peptide length in residues.",
    )
    num_designs = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=100000,
        initial=100,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Number of initial designs to generate.",
    )
    budget = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=10000,
        initial=10,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Final number of high-quality designs after filtering.",
    )
    alpha = forms.FloatField(
        required=False,
        min_value=0.0,
        max_value=1.0,
        initial=0.001,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.001"}),
        help_text="Diversity vs quality tradeoff (0=quality, 1=diversity). Default for peptides is 0.01.",
    )
    yaml_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={
                "class": "form-control",
                "accept": ".yaml,.yml",
            }
        ),
        help_text="Upload a complete BoltzGen YAML design specification.",
    )

    def clean(self):
        cleaned = super().clean()
        protocol = cleaned.get("protocol")

        if protocol == "yaml_upload":
            if not cleaned.get("yaml_file"):
                self.add_error("yaml_file", "Required for YAML upload mode.")
            return cleaned

        if not cleaned.get("target_file"):
            self.add_error("target_file", "Required for protocol-based design.")

        if protocol in {"protein-anything", "protein-small_molecule"}:
            length_min = cleaned.get("binder_length_min")
            length_max = cleaned.get("binder_length_max")
            if length_min and length_max and length_min > length_max:
                self.add_error("binder_length_max", "Max length must be >= min length.")
        elif protocol == "peptide-anything":
            length_min = cleaned.get("peptide_length_min")
            length_max = cleaned.get("peptide_length_max")
            if length_min and length_max and length_min > length_max:
                self.add_error("peptide_length_max", "Max length must be >= min length.")

        return cleaned
