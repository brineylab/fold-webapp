from django.contrib.auth.forms import AuthenticationForm


class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update({
            "autocomplete": "username",
            "spellcheck": "false",
        })
        self.fields["password"].widget.attrs.update({
            "autocomplete": "current-password",
        })
