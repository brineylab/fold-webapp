from __future__ import annotations

from django import template
from django.utils.html import conditional_escape, format_html, mark_safe


register = template.Library()


def _escape_with_breaks(text: str, autoescape: bool) -> str:
    escaped = conditional_escape(text) if autoescape else text
    return escaped.replace("\n", "<br>")


@register.filter(needs_autoescape=True)
def render_help_text(value, autoescape=True):
    """Render newline-separated help text with markdown-like inline code spans."""
    if value in (None, ""):
        return ""

    text = str(value)
    if text.count("`") % 2:
        return mark_safe(_escape_with_breaks(text, autoescape))

    parts = text.split("`")
    rendered: list[str] = []
    for index, part in enumerate(parts):
        if index % 2:
            rendered.append(str(format_html("<code>{}</code>", part)))
        else:
            rendered.append(_escape_with_breaks(part, autoescape))
    return mark_safe("".join(rendered))
