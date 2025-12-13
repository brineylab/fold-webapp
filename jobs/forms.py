from __future__ import annotations

from django import forms

from runners import all_runners


class JobForm(forms.Form):
    runner = forms.ChoiceField(choices=[])
    sequences = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 12, "placeholder": ">seq1\nMKTAYI...\n"}),
        help_text="Paste FASTA sequences (or plain sequence text).",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["runner"].choices = [(r.key, r.name) for r in all_runners()]


