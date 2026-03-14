from __future__ import annotations

from django.core.exceptions import ValidationError

from jobs.forms import Boltz2SubmitForm
from model_types.base import BaseModelType, InputPayload
from model_types.parsers import parse_fasta_batch


_BOLTZ_FASTA_ENTITY_TYPES = {"protein", "dna", "rna", "ccd", "smiles"}


class Boltz2ModelType(BaseModelType):
    key = "boltz2"
    name = "Boltz-2"
    category = "Structure Prediction"
    template_name = "jobs/submit_boltz2.html"
    form_class = Boltz2SubmitForm
    help_text = "Predict biomolecular structure and binding affinity with Boltz-2. Supports proteins, nucleic acids, small molecules, and multimeric complexes."
    _runner_key = "boltz-2"

    def validate(self, cleaned_data: dict) -> None:
        if cleaned_data.get("input_file"):
            return

        sequences = (cleaned_data.get("sequences") or "").strip()
        if not sequences:
            return

        entries = parse_fasta_batch(sequences)
        for entry in entries:
            header = entry["header"]
            parts = [part.strip() for part in header.split("|")]
            if len(parts) < 2 or len(parts) > 3:
                raise ValidationError(
                    "Boltz-2 FASTA headers must look like '>A|protein' or "
                    "'>A|protein|msa_id'."
                )

            chain_id, entity_type = parts[:2]
            if not chain_id or not entity_type:
                raise ValidationError(
                    "Boltz-2 FASTA headers must include both a chain ID and "
                    "an entity type."
                )

            entity_type = entity_type.lower()
            if entity_type not in _BOLTZ_FASTA_ENTITY_TYPES:
                valid = ", ".join(sorted(_BOLTZ_FASTA_ENTITY_TYPES))
                raise ValidationError(
                    f"Invalid Boltz-2 entity type {parts[1]!r}. "
                    f"Use one of: {valid}."
                )

            if len(parts) == 3 and parts[2] and entity_type != "protein":
                raise ValidationError(
                    "Boltz-2 MSA IDs are only allowed for protein entries."
                )

    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        sequences = (cleaned_data.get("sequences") or "").strip()
        params = {
            "use_msa_server": bool(cleaned_data.get("use_msa_server")),
            "msa_server_url": cleaned_data.get("msa_server_url") or "",
            "use_potentials": bool(cleaned_data.get("use_potentials")),
            "no_kernels": bool(cleaned_data.get("no_kernels")),
            "output_format": cleaned_data.get("output_format"),
            "recycling_steps": cleaned_data.get("recycling_steps"),
            "sampling_steps": cleaned_data.get("sampling_steps"),
            "diffusion_samples": cleaned_data.get("diffusion_samples"),
        }
        params = {k: v for k, v in params.items() if v not in (None, "", False)}

        files: dict[str, bytes] = {}
        input_file = cleaned_data.get("input_file")
        if input_file:
            files[input_file.name] = input_file.read()
            params["input_filename"] = input_file.name
            sequences = ""  # file replaces textarea input

        return {
            "sequences": sequences,
            "params": params,
            "files": files,
        }

    def resolve_runner_key(self, cleaned_data: dict) -> str:
        return "boltz-2"

    def get_output_context(self, job) -> dict:
        """Boltz-2 classifies structure files as primary results."""
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
