from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypedDict

from django import forms


class InputPayload(TypedDict):
    """Typed contract between normalize_inputs() and the service layer.

    Every ModelType.normalize_inputs() must return a dict matching this shape.
    """

    sequences: str
    """FASTA text. Empty string for models that don't use FASTA input."""

    params: dict
    """Model-specific parameters, stored in Job.params."""

    files: dict[str, bytes]
    """Filename -> content for uploaded files to write to the job workdir."""


class BaseModelType(ABC):
    key: str = ""
    name: str = ""
    template_name: str = ""
    form_class: type[forms.Form] = forms.Form
    help_text: str = ""

    def get_form(self, *args, **kwargs) -> forms.Form:
        return self.form_class(*args, **kwargs)

    @abstractmethod
    def validate(self, cleaned_data: dict) -> None:
        """Model-specific validation beyond what the form enforces.

        Raise ``ValidationError`` on failure.  Do **not** duplicate form-level
        required-field checks here -- the form already handles those.  Use this
        for cross-field constraints and domain-specific rules only (e.g.
        "multi-chain complexes require at least two sequences").
        """
        ...

    @abstractmethod
    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        """Convert form *cleaned_data* into a typed :class:`InputPayload`.

        Must return a dict with ``sequences``, ``params``, and ``files`` keys.
        """
        ...

    @abstractmethod
    def resolve_runner_key(self, cleaned_data: dict) -> str:
        """Return the runner key to use for this submission."""
        ...

    def prepare_workdir(self, job, input_payload: InputPayload) -> None:
        """Write input files to job.workdir.

        Default implementation:
        - Creates input/ and output/ subdirectories
        - Writes sequences.fasta if sequences is non-empty
        - Writes all files from input_payload["files"] into input/

        Override for models that need custom workdir layouts
        (e.g., nested directories, config files, specific filenames).
        """
        workdir = job.workdir
        (workdir / "input").mkdir(parents=True, exist_ok=True)
        (workdir / "output").mkdir(parents=True, exist_ok=True)
        sequences = input_payload.get("sequences", "")
        if sequences:
            (workdir / "input" / "sequences.fasta").write_text(
                sequences, encoding="utf-8"
            )
        for filename, content in input_payload.get("files", {}).items():
            (workdir / "input" / filename).write_bytes(content)

    def parse_batch(self, upload) -> list[dict]:
        """Parse a batch upload into a list of per-item input dicts.

        Default raises ``NotImplementedError`` -- only implement in model
        types that support batch submission.  Each dict in the returned list
        is a partial ``cleaned_data`` override that will be merged with the
        base form data before calling :meth:`normalize_inputs`.
        """
        raise NotImplementedError(
            f"{self.name} does not support batch uploads."
        )

    def parse_config(self, upload) -> dict:
        """Parse an advanced config file into a dict to merge into params.

        Default raises ``NotImplementedError`` -- only implement in model
        types that support config file uploads.  The returned dict is merged
        into the form's ``cleaned_data`` before calling
        :meth:`normalize_inputs`.
        """
        raise NotImplementedError(
            f"{self.name} does not support config file uploads."
        )

    def get_output_context(self, job) -> dict:
        """Return template context for rendering job outputs on the detail page.

        Returns a dict with:
          - files: list of all output file dicts (name, size)
          - primary_files: list of "main result" file dicts
          - aux_files: list of auxiliary/log file dicts

        Override to customize grouping, add labels, or flag specific
        files for inline preview.
        """
        outdir = job.workdir / "output"
        files = []
        if outdir.exists() and outdir.is_dir():
            for p in sorted(outdir.iterdir()):
                if p.is_file():
                    files.append({"name": p.name, "size": p.stat().st_size})
        return {"files": files, "primary_files": [], "aux_files": []}
