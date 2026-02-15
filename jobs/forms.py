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


class RFdiffusionSubmitForm(forms.Form):
    MODE_CHOICES = [
        ("unconditional", "Unconditional generation"),
        ("binder", "Binder design"),
        ("motif", "Motif scaffolding"),
        ("partial", "Partial diffusion"),
        ("symmetric", "Symmetric oligomer"),
    ]
    SYMMETRY_CHOICES = [
        ("cyclic", "Cyclic (Cn)"),
        ("dihedral", "Dihedral (Dn)"),
    ]

    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "spellcheck": "false",
        }),
    )
    mode = forms.ChoiceField(
        choices=MODE_CHOICES,
        initial="unconditional",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_mode"}),
        help_text="Select the RFdiffusion inference mode.",
    )
    num_designs = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=1000,
        initial=10,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Number of designs to generate.",
    )
    timesteps = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=1000,
        initial=50,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Number of diffusion timesteps (default: 50).",
    )

    # Unconditional fields
    length_min = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=1000,
        initial=100,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Minimum backbone length.",
    )
    length_max = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=1000,
        initial=200,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Maximum backbone length.",
    )

    # Binder design fields
    target_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdb"}),
        help_text="Upload the target protein structure in PDB format.",
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
        initial=70,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Minimum binder length.",
    )
    binder_length_max = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=500,
        initial=100,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Maximum binder length.",
    )
    hotspot_residues = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. A30,A33,A34",
        }),
        help_text="Target hotspot residues (e.g. A30,A33,A34). Leave blank for no hotspot bias.",
    )

    # Motif scaffolding / Partial diffusion fields
    input_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdb"}),
        help_text="Upload the input PDB structure.",
    )
    contigs = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. 10-40/A163-181/10-40",
        }),
        help_text="RFdiffusion contig string specifying fixed and designable regions.",
    )

    # Partial diffusion field
    partial_T = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=1000,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Number of noising steps for partial diffusion (must be less than timesteps).",
    )

    # Symmetric oligomer fields
    symmetry_type = forms.ChoiceField(
        required=False,
        choices=SYMMETRY_CHOICES,
        initial="cyclic",
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Symmetry type for oligomer design.",
    )
    symmetry_order = forms.IntegerField(
        required=False,
        min_value=2,
        max_value=24,
        initial=3,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Order of symmetry (e.g. 3 for C3 or D3).",
    )
    subunit_length = forms.IntegerField(
        required=False,
        min_value=10,
        max_value=500,
        initial=100,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
        help_text="Length of each subunit in residues.",
    )

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")

        if mode == "unconditional":
            if not cleaned.get("length_min"):
                self.add_error("length_min", "Required for unconditional generation.")
            if not cleaned.get("length_max"):
                self.add_error("length_max", "Required for unconditional generation.")
            if (cleaned.get("length_min") and cleaned.get("length_max")
                    and cleaned["length_min"] > cleaned["length_max"]):
                self.add_error("length_max", "Max length must be >= min length.")

        elif mode == "binder":
            if not cleaned.get("target_pdb"):
                self.add_error("target_pdb", "Required for binder design.")
            if not cleaned.get("target_chain"):
                self.add_error("target_chain", "Required for binder design.")
            if not cleaned.get("binder_length_min"):
                self.add_error("binder_length_min", "Required for binder design.")
            if not cleaned.get("binder_length_max"):
                self.add_error("binder_length_max", "Required for binder design.")
            if (cleaned.get("binder_length_min") and cleaned.get("binder_length_max")
                    and cleaned["binder_length_min"] > cleaned["binder_length_max"]):
                self.add_error("binder_length_max", "Max length must be >= min length.")

        elif mode in ("motif", "partial"):
            if not cleaned.get("input_pdb"):
                self.add_error("input_pdb", f"Required for {mode} mode.")
            if not cleaned.get("contigs"):
                self.add_error("contigs", f"Required for {mode} mode.")
            if mode == "partial" and not cleaned.get("partial_T"):
                self.add_error("partial_T", "Required for partial diffusion.")

        elif mode == "symmetric":
            if not cleaned.get("symmetry_type"):
                self.add_error("symmetry_type", "Required for symmetric oligomer.")
            if not cleaned.get("symmetry_order"):
                self.add_error("symmetry_order", "Required for symmetric oligomer.")
            if not cleaned.get("subunit_length"):
                self.add_error("subunit_length", "Required for symmetric oligomer.")

        return cleaned


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

    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "spellcheck": "false",
        }),
    )
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

    # Unconditional fields
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

    # Protein binder fields
    target_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdb,.cif"}),
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
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. E64,E88",
        }),
        help_text="Target hotspot residues. Leave blank for no hotspot bias.",
    )
    is_non_loopy = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="Generate non-loopy (structured) binders.",
    )

    # Small molecule binder fields
    sm_target_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdb,.cif"}),
        help_text="Upload the target structure with ligand (PDB or CIF).",
    )
    sm_ligand_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. HAX,OAA",
        }),
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

    # Nucleic acid binder fields
    na_target_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdb,.cif"}),
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

    # Enzyme design fields
    enzyme_target_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdb,.cif"}),
        help_text="Upload the target structure with substrate (PDB or CIF).",
    )
    enzyme_ligand_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. SUB",
        }),
        help_text="Substrate/ligand residue name from the PDB file.",
    )
    enzyme_catalytic_residues = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. A244,A274,A320",
        }),
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

    # Motif scaffolding fields
    motif_input_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdb,.cif"}),
        help_text="Upload the input structure containing the motif (PDB or CIF).",
    )
    motif_contig = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. A40-60,70,A120-170",
        }),
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

    # Partial diffusion fields
    partial_input_pdb = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".pdb,.cif"}),
        help_text="Upload the input structure (PDB or CIF).",
    )
    partial_contig = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. A1-100",
        }),
        help_text="Contig string specifying regions for partial diffusion.",
    )
    partial_t = forms.FloatField(
        required=False,
        min_value=0.1,
        max_value=100.0,
        initial=10.0,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.5"}),
        help_text="Noise level in angstroms (recommended 5-15).",
    )

    # Symmetric design fields
    sym_contig = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. 100-100",
        }),
        help_text="Contig string for each symmetric subunit.",
    )
    sym_type = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. C3, D2",
        }),
        help_text="Symmetry type (e.g. C3, C6, D2).",
    )

    # JSON upload field
    input_json = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".json,.yaml,.yml"}),
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
            if (cleaned.get("length_min") and cleaned.get("length_max")
                    and cleaned["length_min"] > cleaned["length_max"]):
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
            if (cleaned.get("binder_length_min") and cleaned.get("binder_length_max")
                    and cleaned["binder_length_min"] > cleaned["binder_length_max"]):
                self.add_error("binder_length_max", "Max length must be >= min length.")

        elif mode == "small_molecule_binder":
            if not cleaned.get("sm_target_pdb"):
                self.add_error("sm_target_pdb", "Required for small molecule binder design.")
            if not cleaned.get("sm_ligand_name"):
                self.add_error("sm_ligand_name", "Required for small molecule binder design.")
            if (cleaned.get("sm_binder_length_min") and cleaned.get("sm_binder_length_max")
                    and cleaned["sm_binder_length_min"] > cleaned["sm_binder_length_max"]):
                self.add_error("sm_binder_length_max", "Max length must be >= min length.")

        elif mode == "nucleic_acid_binder":
            if not cleaned.get("na_target_pdb"):
                self.add_error("na_target_pdb", "Required for nucleic acid binder design.")
            if (cleaned.get("na_binder_length_min") and cleaned.get("na_binder_length_max")
                    and cleaned["na_binder_length_min"] > cleaned["na_binder_length_max"]):
                self.add_error("na_binder_length_max", "Max length must be >= min length.")

        elif mode == "enzyme":
            if not cleaned.get("enzyme_target_pdb"):
                self.add_error("enzyme_target_pdb", "Required for enzyme design.")
            if not cleaned.get("enzyme_ligand_name"):
                self.add_error("enzyme_ligand_name", "Required for enzyme design.")
            if not cleaned.get("enzyme_catalytic_residues"):
                self.add_error("enzyme_catalytic_residues", "Required for enzyme design.")
            if (cleaned.get("enzyme_scaffold_length_min") and cleaned.get("enzyme_scaffold_length_max")
                    and cleaned["enzyme_scaffold_length_min"] > cleaned["enzyme_scaffold_length_max"]):
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


class BoltzGenSubmitForm(forms.Form):
    PROTOCOL_CHOICES = [
        ("protein-anything", "Protein binder (any target)"),
        ("peptide-anything", "Peptide binder (any target)"),
        ("protein-small_molecule", "Protein binder (small molecule target)"),
        ("nanobody-anything", "Nanobody (any target)"),
        ("yaml_upload", "Upload YAML specification"),
    ]

    name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "spellcheck": "false",
        }),
    )
    protocol = forms.ChoiceField(
        choices=PROTOCOL_CHOICES,
        initial="protein-anything",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_protocol"}),
        help_text="Select the BoltzGen design protocol.",
    )
    target_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            "class": "form-control",
            "accept": ".pdb,.cif,.mmcif",
        }),
        help_text="Upload the target structure (PDB or CIF format).",
    )
    target_chains = forms.CharField(
        required=False,
        initial="A",
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "A",
            "autocomplete": "off",
            "spellcheck": "false",
        }),
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
        widget=forms.ClearableFileInput(attrs={
            "class": "form-control",
            "accept": ".yaml,.yml",
        }),
        help_text="Upload a complete BoltzGen YAML design specification.",
    )

    def clean(self):
        cleaned = super().clean()
        protocol = cleaned.get("protocol")

        if protocol == "yaml_upload":
            if not cleaned.get("yaml_file"):
                self.add_error("yaml_file", "Required for YAML upload mode.")
        else:
            if not cleaned.get("target_file"):
                self.add_error("target_file", "Required for protocol-based design.")

            if protocol in ("protein-anything", "protein-small_molecule"):
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
