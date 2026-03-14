from __future__ import annotations

import json

from django.core.exceptions import ValidationError

from jobs.forms import OpenFold3SubmitForm
from jobs.fs import write_text
from model_types.base import BaseModelType, InputPayload
from model_types.parsers import parse_fasta_batch


_OF3_ENTITY_TYPES = {"protein", "rna", "dna", "smiles", "ccd"}


def _fasta_to_openfold3_json(entries: list[dict], job_name: str) -> dict:
    """Convert parsed FASTA entries to OpenFold3 JSON query format.

    Each entry has ``header`` (e.g. ``"A|protein"``) and ``sequence``.
    Maps entity types to OpenFold3 molecule types:
      protein/rna/dna -> same
      smiles/ccd      -> ligand
    """
    chains: list[dict] = []
    for entry in entries:
        parts = entry["header"].split("|")
        chain_id = parts[0].strip()
        entity_type = parts[1].strip().lower()
        sequence = entry["sequence"]

        if entity_type in ("protein", "rna", "dna"):
            chains.append({
                "molecule_type": entity_type,
                "chain_ids": [chain_id],
                "sequence": sequence,
            })
        elif entity_type == "smiles":
            chains.append({
                "molecule_type": "ligand",
                "chain_ids": [chain_id],
                "smiles": sequence,
            })
        elif entity_type == "ccd":
            chains.append({
                "molecule_type": "ligand",
                "chain_ids": [chain_id],
                "ccd_codes": [sequence],
            })

    return {"queries": {job_name: {"chains": chains}}}


class OpenFold3ModelType(BaseModelType):
    key = "openfold3"
    name = "OpenFold3"
    category = "Structure Prediction"
    template_name = "jobs/submit_openfold3.html"
    form_class = OpenFold3SubmitForm
    help_text = (
        "Predict biomolecular structure with OpenFold3. Supports proteins, "
        "nucleic acids, small molecules, and multimeric complexes."
    )
    _runner_key = "openfold3"

    def validate(self, cleaned_data: dict) -> None:
        if cleaned_data.get("json_file"):
            return

        sequences = (cleaned_data.get("sequences") or "").strip()
        if not sequences:
            return

        entries = parse_fasta_batch(sequences)
        for entry in entries:
            header = entry["header"]
            parts = [part.strip() for part in header.split("|")]
            if len(parts) != 2:
                raise ValidationError(
                    "OpenFold3 FASTA headers must look like '>A|protein'."
                )

            chain_id, entity_type = parts
            if not chain_id or not entity_type:
                raise ValidationError(
                    "OpenFold3 FASTA headers must include both a chain ID and "
                    "an entity type."
                )

            entity_type = entity_type.lower()
            if entity_type not in _OF3_ENTITY_TYPES:
                valid = ", ".join(sorted(_OF3_ENTITY_TYPES))
                raise ValidationError(
                    f"Invalid OpenFold3 entity type {parts[1]!r}. "
                    f"Use one of: {valid}."
                )

    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        sequences = (cleaned_data.get("sequences") or "").strip()
        params: dict = {
            "use_msa_server": bool(cleaned_data.get("use_msa_server")),
            "use_templates": bool(cleaned_data.get("use_templates")),
            "num_diffusion_samples": cleaned_data.get("num_diffusion_samples"),
            "num_model_seeds": cleaned_data.get("num_model_seeds"),
            "output_format": cleaned_data.get("output_format"),
            "seed": cleaned_data.get("seed"),
        }
        # Keep truthy params and explicit False for boolean flags
        params = {
            k: v for k, v in params.items()
            if v is not None and v != ""
        }

        files: dict[str, bytes] = {}

        # Priority: json_file > fasta_file > textarea
        json_file = cleaned_data.get("json_file")
        fasta_file = cleaned_data.get("fasta_file")

        if json_file:
            files["query.json"] = json_file.read()
            params["input_mode"] = "json"
            sequences = ""
        elif fasta_file:
            sequences = fasta_file.read().decode("utf-8", errors="replace")
            params["input_mode"] = "fasta"
        else:
            params["input_mode"] = "fasta"

        return {
            "sequences": sequences,
            "params": params,
            "files": files,
        }

    def resolve_runner_key(self, cleaned_data: dict) -> str:
        return "openfold3"

    def prepare_workdir(self, job, input_payload: InputPayload) -> None:
        super().prepare_workdir(job, input_payload)

        params = input_payload.get("params", {})
        input_mode = params.get("input_mode", "fasta")

        if input_mode == "fasta":
            sequences = input_payload.get("sequences", "")
            if sequences:
                entries = parse_fasta_batch(sequences)
                job_name = job.name if hasattr(job, "name") and job.name else "query"
                query = _fasta_to_openfold3_json(entries, job_name)
                write_text(
                    job.workdir / "input" / "query.json",
                    json.dumps(query, indent=2),
                )

    def get_output_context(self, job) -> dict:
        """OpenFold3 outputs may be nested under query_id/seed_N/."""
        outdir = job.workdir / "output"
        primary, aux = [], []
        if outdir.exists() and outdir.is_dir():
            for p in sorted(
                (candidate for candidate in outdir.rglob("*") if candidate.is_file()),
                key=lambda candidate: candidate.relative_to(outdir).as_posix(),
            ):
                rel_name = p.relative_to(outdir).as_posix()
                entry = {"name": rel_name, "size": p.stat().st_size}
                if p.suffix in (".pdb", ".cif", ".mmcif"):
                    primary.append(entry)
                else:
                    aux.append(entry)
        return {
            "files": primary + aux,
            "primary_files": primary,
            "aux_files": aux,
        }
