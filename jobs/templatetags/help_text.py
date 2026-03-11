from __future__ import annotations

from django import template
from django.utils.html import conditional_escape, format_html, mark_safe


register = template.Library()


def _escape_with_breaks(text: str, autoescape: bool) -> str:
    escaped = conditional_escape(text) if autoescape else text
    return escaped.replace("\n", "<br>")


def _render_inline_code(text: str, autoescape: bool) -> str:
    if text.count("`") % 2:
        return _escape_with_breaks(text, autoescape)

    parts = text.split("`")
    rendered: list[str] = []
    for index, part in enumerate(parts):
        if index % 2:
            rendered.append(str(format_html("<code>{}</code>", part)))
        else:
            rendered.append(_escape_with_breaks(part, autoescape))
    return "".join(rendered)


@register.filter(needs_autoescape=True)
def render_help_text(value, autoescape=True):
    """Render newline-separated help text with markdown-like inline code spans."""
    if value in (None, ""):
        return ""

    text = str(value)
    return mark_safe(_render_inline_code(text, autoescape))


@register.filter(needs_autoescape=True)
def render_help_text_with_note(value, autoescape=True):
    """Render help text with NOTE-prefixed lines as a separate admonition block."""
    if value in (None, ""):
        return ""

    lines = str(value).splitlines()
    note_lines: list[str] = []
    body_lines: list[str] = []

    for line in lines:
        if line.startswith("NOTE:"):
            note_lines.append(line[len("NOTE:"):].strip())
        else:
            body_lines.append(line)

    rendered: list[str] = []

    body_text = "\n".join(line for line in body_lines if line != "").strip()
    if body_text:
        rendered.append(
            str(
                format_html(
                    '<p class="ui-help-text">{}</p>',
                    mark_safe(_render_inline_code(body_text, autoescape)),
                )
            )
        )

    if note_lines:
        note_text = "\n".join(note_lines).strip()
        rendered.append(
            str(
                format_html(
                    '<div class="ui-note" role="note"><div class="ui-note-icon" aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="10"/><path stroke-linecap="round" stroke-linejoin="round" d="M12 16h.01M12 8v4"/></svg></div><div class="ui-note-content"><div class="ui-note-label">Note</div><div class="ui-note-body">{}</div></div></div>',
                    mark_safe(_render_inline_code(note_text, autoescape)),
                )
            )
        )

    return mark_safe("".join(rendered))
