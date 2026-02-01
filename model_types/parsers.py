"""Shared parsing utilities for batch and config file uploads."""
from __future__ import annotations

import json
import zipfile
from io import BytesIO

from django.core.exceptions import ValidationError


# --- Constants ---

MAX_FASTA_ENTRIES = 100
MAX_ZIP_TOTAL_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_ZIP_ENTRIES = 100

DEFAULT_ZIP_ALLOWED_EXTENSIONS = frozenset({
    ".pdb", ".cif", ".mmcif", ".fasta", ".fa", ".json", ".txt", ".csv",
})


# --- FASTA parsing ---


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


# --- ZIP parsing ---


def parse_zip_entries(
    upload,
    *,
    allowed_extensions: frozenset[str] | None = None,
    max_total_bytes: int = MAX_ZIP_TOTAL_BYTES,
) -> dict[str, bytes]:
    """Extract files from a ZIP upload into a ``{filename: bytes}`` dict.

    Parameters
    ----------
    upload
        A Django ``UploadedFile`` (or any file-like with ``.read()``).
    allowed_extensions
        Set of lowercase extensions (including dot) to accept.
        Files with other extensions are silently skipped.
        Defaults to :data:`DEFAULT_ZIP_ALLOWED_EXTENSIONS`.
    max_total_bytes
        Maximum total uncompressed size of all accepted files.

    Raises :class:`~django.core.exceptions.ValidationError` on invalid
    ZIP, path traversal attempts, or size limit violations.
    """
    if allowed_extensions is None:
        allowed_extensions = DEFAULT_ZIP_ALLOWED_EXTENSIONS

    raw = upload.read()
    buf = BytesIO(raw)

    if not zipfile.is_zipfile(buf):
        raise ValidationError("Uploaded file is not a valid ZIP archive.")
    buf.seek(0)

    files: dict[str, bytes] = {}
    total_bytes = 0

    with zipfile.ZipFile(buf, "r") as zf:
        entries = [i for i in zf.infolist() if not i.is_dir()]

        if len(entries) > MAX_ZIP_ENTRIES:
            raise ValidationError(
                f"ZIP contains too many files ({len(entries)}). "
                f"Maximum is {MAX_ZIP_ENTRIES}."
            )

        for info in entries:
            # Security: reject entries with path traversal
            name = info.filename
            if ".." in name or name.startswith("/"):
                raise ValidationError(
                    f"ZIP entry has unsafe path: {name!r}"
                )

            # Use only the basename to flatten nested structures
            basename = name.rsplit("/", 1)[-1]
            if not basename:
                continue

            # Check extension
            dot_pos = basename.rfind(".")
            ext = basename[dot_pos:].lower() if dot_pos >= 0 else ""
            if ext not in allowed_extensions:
                continue

            content = zf.read(name)
            total_bytes += len(content)
            if total_bytes > max_total_bytes:
                raise ValidationError(
                    f"ZIP contents exceed size limit "
                    f"({max_total_bytes // (1024 * 1024)} MB)."
                )

            # De-duplicate: if two files have same basename, rename
            final_name = basename
            counter = 1
            while final_name in files:
                stem, dot_ext = (
                    (basename[:dot_pos], basename[dot_pos:])
                    if dot_pos >= 0
                    else (basename, "")
                )
                final_name = f"{stem}_{counter}{dot_ext}"
                counter += 1

            files[final_name] = content

    if not files:
        raise ValidationError(
            "ZIP contains no files with allowed extensions "
            f"({', '.join(sorted(allowed_extensions))})."
        )
    return files


# --- JSON config parsing ---


def parse_json_config(upload) -> dict:
    """Parse a JSON config file upload into a dict.

    Parameters
    ----------
    upload
        A Django ``UploadedFile`` (or any file-like with ``.read()``).

    Raises :class:`~django.core.exceptions.ValidationError` if the file
    is not valid JSON or doesn't decode to a dict.
    """
    try:
        raw = upload.read()
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValidationError(f"Invalid JSON config file: {e}") from e
    if not isinstance(data, dict):
        raise ValidationError(
            "Config file must contain a JSON object (not a list or scalar)."
        )
    return data
