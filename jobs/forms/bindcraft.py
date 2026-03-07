from __future__ import annotations

from django import forms

from jobs.forms.shared import name_field


class BindCraftSubmitForm(forms.Form):
    name = name_field()
    pdb_file = forms.FileField(
        required=True,
        help_text="Upload the target protein structure in PDB format.",
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdb"}
        ),
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
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "e.g. 56,78,102",
            }
        ),
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
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".json"}
        ),
    )
    advanced_file = forms.FileField(
        required=False,
        help_text="Optional: upload a custom advanced settings JSON. Uses BindCraft defaults if omitted.",
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".json"}
        ),
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
