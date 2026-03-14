from __future__ import annotations

from django import forms

from jobs.forms.shared import TailwindFormMixin, name_field


class OpenFold3SubmitForm(TailwindFormMixin, forms.Form):
    name = name_field()
    sequences = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 12,
                "placeholder": ">A|protein\nMKTAYI...\n>B|rna\nACGU...\n",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
        help_text=(
            "Enter one or more FASTA-formatted sequences. "
            "Multiple sequences will be modeled as a single multimeric complex.\n"
            "NOTE: OpenFold3 requires that sequence headers be formatted as "
            "`>chain_id|entity_type`, where `entity_type` can be one of: "
            "`protein`, `dna`, `rna`, `smiles`, or `ccd`."
        ),
    )
    fasta_file = forms.FileField(
        required=False,
        help_text=(
            "Upload a FASTA file. When provided, the Sequences field is ignored. "
            "Multiple sequences in the file will be modeled as a single multimeric complex."
        ),
    )
    json_file = forms.FileField(
        required=False,
        help_text=(
            "Upload an OpenFold3 JSON query file. Overrides FASTA inputs. "
            "See OpenFold3 documentation for the required JSON format."
        ),
    )
    use_msa_server = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Generate MSAs via the ColabFold mmseqs2 server (requires network access).",
        widget=forms.CheckboxInput(
            attrs={"data-toggle-disabled-target": "#id_msa_server_url"}
        ),
    )
    msa_server_url = forms.URLField(
        required=False,
        widget=forms.URLInput(
            attrs={"placeholder": "api.colabfold.com", "class": "mt-2"}
        ),
    )
    use_templates = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Use template-based predictions.",
    )
    num_diffusion_samples = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=25,
        initial=5,
        help_text="Number of diffusion samples to generate (default: 5).",
    )
    num_model_seeds = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=10,
        initial=1,
        help_text="Number of model seeds to run (default: 1).",
    )
    output_format = forms.ChoiceField(
        required=False,
        choices=[("cif", "mmCIF"), ("pdb", "PDB")],
        initial="cif",
        help_text="Output structure format.",
    )
    seed = forms.IntegerField(
        required=False,
        min_value=0,
        help_text="Random seed for reproducibility.",
    )

    def clean(self):
        cleaned = super().clean()
        has_sequences = bool((cleaned.get("sequences") or "").strip())
        has_fasta = bool(cleaned.get("fasta_file"))
        has_json = bool(cleaned.get("json_file"))
        if not has_sequences and not has_fasta and not has_json:
            raise forms.ValidationError(
                "Provide sequences, a FASTA file, or a JSON query file."
            )
        return cleaned
