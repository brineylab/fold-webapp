from __future__ import annotations

from django import forms

from runners import all_runners


class JobForm(forms.Form):
    name = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                # "placeholder": "e.g., My first AF run",
                # "placeholder": "optional job name",
            }
        ),
        # help_text="Optional name for this run.",
    )
    runner = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    sequences = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 12,
                "placeholder": ">seq1\nMKTAYI...\n",
            }
        ),
        help_text="Paste one or more FASTA-formatted sequences.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["runner"].choices = [(r.key, r.name) for r in all_runners()]
