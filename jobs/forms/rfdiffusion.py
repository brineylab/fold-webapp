from __future__ import annotations

from django import forms

from jobs.forms.shared import name_field


class RFdiffusion3SubmitForm(forms.Form):
    MODE_CHOICES = [
        ("unconditional", "Unconditional generation"),
        ("protein_binder", "Protein binder design"),
        ("small_molecule_binder", "Small molecule binder design"),
        ("nucleic_acid_binder", "Nucleic acid binder design"),
        ("enzyme", "Enzyme design"),
        ("motif", "Motif scaffolding"),
        ("partial", "Partial diffusion"),
        ("symmetric", "Symmetric design"),
        ("json_upload", "Upload JSON specification"),
    ]

    name = name_field()
    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        initial="unconditional",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_mode"}),
        help_text="Select the RFdiffusion3 design mode.",
    )
    num_designs = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=1000,
        initial=8,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Number of designs per batch.",
    )
    n_batches = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        initial=1,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Number of batches.",
    )
    timesteps = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=1000,
        initial=200,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Diffusion timesteps (default: 200).",
    )
    step_scale = forms.FloatField(
        required=False,
        min_value=0.1,
        max_value=10.0,
        initial=1.5,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.1"}),
        help_text="Step size scaling (default: 1.5).",
    )

    length_min = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=1000,
        initial=50,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Minimum protein length.",
    )
    length_max = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=1000,
        initial=200,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Maximum protein length.",
    )

    target_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdb,.cif"}
        ),
        help_text="Upload the target protein structure (PDB or CIF).",
    )
    target_chain = forms.CharField(
        required=False,
        initial="A",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Chain ID of the target protein.",
    )
    binder_length_min = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=500,
        initial=40,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Minimum binder length.",
    )
    binder_length_max = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=500,
        initial=120,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Maximum binder length.",
    )
    hotspot_residues = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. E64,E88",
            }
        ),
        help_text="Target hotspot residues. Leave blank for no hotspot bias.",
    )
    is_non_loopy = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Generate non-loopy (structured) binders.",
    )

    sm_target_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdb,.cif"}
        ),
        help_text="Upload the target structure with ligand (PDB or CIF).",
    )
    sm_ligand_name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. HAX,OAA",
            }
        ),
        help_text="Ligand residue name(s) from the PDB file.",
    )
    sm_binder_length_min = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=500,
        initial=50,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Minimum binder length.",
    )
    sm_binder_length_max = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=500,
        initial=150,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Maximum binder length.",
    )

    na_target_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdb,.cif"}
        ),
        help_text="Upload the target nucleic acid structure (PDB or CIF).",
    )
    na_target_chain = forms.CharField(
        required=False,
        initial="B",
        widget=forms.TextInput(attrs={"class": "form-control"}),
        help_text="Chain ID of the nucleic acid target.",
    )
    na_binder_length_min = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=500,
        initial=50,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Minimum binder length.",
    )
    na_binder_length_max = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=500,
        initial=150,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Maximum binder length.",
    )

    enzyme_target_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdb,.cif"}
        ),
        help_text="Upload the target structure with substrate (PDB or CIF).",
    )
    enzyme_ligand_name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. SUB",
            }
        ),
        help_text="Substrate/ligand residue name from the PDB file.",
    )
    enzyme_catalytic_residues = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. A244,A274,A320",
            }
        ),
        help_text="Catalytic residue positions to fix (chain + residue number).",
    )
    enzyme_scaffold_length_min = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=1000,
        initial=100,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Minimum scaffold length.",
    )
    enzyme_scaffold_length_max = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=1000,
        initial=300,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Maximum scaffold length.",
    )

    motif_input_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdb,.cif"}
        ),
        help_text="Upload the input structure containing the motif (PDB or CIF).",
    )
    motif_contig = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. A40-60,70,A120-170",
            }
        ),
        help_text="Contig string specifying fixed motif and designable regions.",
    )
    motif_length_min = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=1000,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Minimum scaffold length.",
    )
    motif_length_max = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=1000,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Maximum scaffold length.",
    )

    partial_input_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdb,.cif"}
        ),
        help_text="Upload the input structure (PDB or CIF).",
    )
    partial_contig = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. A1-100",
            }
        ),
        help_text="Contig string specifying regions for partial diffusion.",
    )
    partial_t = forms.FloatField(
        required=False,
        min_value=0.1,
        max_value=100.0,
        initial=10.0,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "any"}),
        help_text="Noise level in angstroms (recommended 5-15).",
    )

    sym_contig = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. 100-100",
            }
        ),
        help_text="Contig string for each symmetric subunit.",
    )
    sym_type = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. C3, D2",
            }
        ),
        help_text="Symmetry type (e.g. C3, C6, D2).",
    )

    input_json = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".json,.yaml,.yml"}
        ),
        help_text="Upload a complete RFdiffusion3 JSON or YAML input specification.",
    )

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")

        if mode == "unconditional":
            if not cleaned.get("length_min"):
                self.add_error("length_min", "Required for unconditional generation.")
            if not cleaned.get("length_max"):
                self.add_error("length_max", "Required for unconditional generation.")
            if (
                cleaned.get("length_min")
                and cleaned.get("length_max")
                and cleaned["length_min"] > cleaned["length_max"]
            ):
                self.add_error("length_max", "Max length must be >= min length.")
        elif mode == "protein_binder":
            if not cleaned.get("target_pdb"):
                self.add_error("target_pdb", "Required for protein binder design.")
            if not cleaned.get("target_chain"):
                self.add_error("target_chain", "Required for protein binder design.")
            if not cleaned.get("binder_length_min"):
                self.add_error("binder_length_min", "Required for protein binder design.")
            if not cleaned.get("binder_length_max"):
                self.add_error("binder_length_max", "Required for protein binder design.")
            if (
                cleaned.get("binder_length_min")
                and cleaned.get("binder_length_max")
                and cleaned["binder_length_min"] > cleaned["binder_length_max"]
            ):
                self.add_error("binder_length_max", "Max length must be >= min length.")
        elif mode == "small_molecule_binder":
            if not cleaned.get("sm_target_pdb"):
                self.add_error("sm_target_pdb", "Required for small molecule binder design.")
            if not cleaned.get("sm_ligand_name"):
                self.add_error("sm_ligand_name", "Required for small molecule binder design.")
            if (
                cleaned.get("sm_binder_length_min")
                and cleaned.get("sm_binder_length_max")
                and cleaned["sm_binder_length_min"] > cleaned["sm_binder_length_max"]
            ):
                self.add_error("sm_binder_length_max", "Max length must be >= min length.")
        elif mode == "nucleic_acid_binder":
            if not cleaned.get("na_target_pdb"):
                self.add_error("na_target_pdb", "Required for nucleic acid binder design.")
            if (
                cleaned.get("na_binder_length_min")
                and cleaned.get("na_binder_length_max")
                and cleaned["na_binder_length_min"] > cleaned["na_binder_length_max"]
            ):
                self.add_error("na_binder_length_max", "Max length must be >= min length.")
        elif mode == "enzyme":
            if not cleaned.get("enzyme_target_pdb"):
                self.add_error("enzyme_target_pdb", "Required for enzyme design.")
            if not cleaned.get("enzyme_ligand_name"):
                self.add_error("enzyme_ligand_name", "Required for enzyme design.")
            if not cleaned.get("enzyme_catalytic_residues"):
                self.add_error(
                    "enzyme_catalytic_residues",
                    "Required for enzyme design.",
                )
            if (
                cleaned.get("enzyme_scaffold_length_min")
                and cleaned.get("enzyme_scaffold_length_max")
                and cleaned["enzyme_scaffold_length_min"]
                > cleaned["enzyme_scaffold_length_max"]
            ):
                self.add_error("enzyme_scaffold_length_max", "Max length must be >= min length.")
        elif mode == "motif":
            if not cleaned.get("motif_input_pdb"):
                self.add_error("motif_input_pdb", "Required for motif scaffolding.")
            if not cleaned.get("motif_contig"):
                self.add_error("motif_contig", "Required for motif scaffolding.")
        elif mode == "partial":
            if not cleaned.get("partial_input_pdb"):
                self.add_error("partial_input_pdb", "Required for partial diffusion.")
            if not cleaned.get("partial_contig"):
                self.add_error("partial_contig", "Required for partial diffusion.")
            if not cleaned.get("partial_t"):
                self.add_error("partial_t", "Required for partial diffusion.")
        elif mode == "symmetric":
            if not cleaned.get("sym_contig"):
                self.add_error("sym_contig", "Required for symmetric design.")
            if not cleaned.get("sym_type"):
                self.add_error("sym_type", "Required for symmetric design.")
        elif mode == "json_upload":
            if not cleaned.get("input_json"):
                self.add_error("input_json", "Required for JSON upload mode.")

        return cleaned
