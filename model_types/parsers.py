"""Shared parsing utilities for model input validation."""
from __future__ import annotations

from django.core.exceptions import ValidationError


MAX_FASTA_ENTRIES = 100


def parse_fasta_batch(text: str) -> list[dict]:
    """Parse multi-FASTA text into a list of ``{header, sequence}`` dicts.

    Each entry corresponds to one ``>header`` line followed by one or more
    sequence lines.  Blank lines and leading/trailing whitespace are stripped.

    Raises :class:`~django.core.exceptions.ValidationError` if the text is
    not valid FASTA or exceeds ``MAX_FASTA_ENTRIES``.
    """
    text = text.strip()
    if not text:
        raise ValidationError("FASTA text is empty.")
    if not text.startswith(">"):
        raise ValidationError("FASTA text must start with a '>' header line.")

    entries: list[dict] = []
    current_header: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            # Save previous entry
            if current_header is not None:
                seq = "".join(current_lines)
                if not seq:
                    raise ValidationError(
                        f"Empty sequence for header: {current_header}"
                    )
                entries.append({"header": current_header, "sequence": seq})
            current_header = line[1:].strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Save final entry
    if current_header is not None:
        seq = "".join(current_lines)
        if not seq:
            raise ValidationError(
                f"Empty sequence for header: {current_header}"
            )
        entries.append({"header": current_header, "sequence": seq})

    if not entries:
        raise ValidationError("No FASTA entries found.")
    if len(entries) > MAX_FASTA_ENTRIES:
        raise ValidationError(
            f"Too many FASTA entries ({len(entries)}). "
            f"Maximum is {MAX_FASTA_ENTRIES}."
        )
    return entries
