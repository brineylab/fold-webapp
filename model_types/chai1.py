from __future__ import annotations

from jobs.forms import Chai1SubmitForm
from model_types.base import BaseModelType, InputPayload


class Chai1ModelType(BaseModelType):
    key = "chai1"
    name = "Chai-1"
    category = "Structure Prediction"
    template_name = "jobs/submit_chai1.html"
    form_class = Chai1SubmitForm
    help_text = (
        "Predict biomolecular structure with Chai-1. Supports proteins, "
        "nucleic acids, small molecules, and multimeric complexes."
    )

    def validate(self, cleaned_data: dict) -> None:
        # Form enforces sequences-or-file. Add domain-specific cross-field
        # checks here as needed (e.g., restraints CSV column validation,
        # FASTA format checks).
        pass

    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        sequences = (cleaned_data.get("sequences") or "").strip()
        params = {
            "use_msa_server": bool(cleaned_data.get("use_msa_server")),
            "num_diffn_samples": cleaned_data.get("num_diffn_samples"),
            "seed": cleaned_data.get("seed"),
        }
        params = {k: v for k, v in params.items() if v not in (None, "", False)}

        files: dict[str, bytes] = {}

        # FASTA file replaces textarea sequences
        fasta_file = cleaned_data.get("fasta_file")
        if fasta_file:
            sequences = fasta_file.read().decode("utf-8", errors="replace")

        # Restraints file (optional, stored with predictable name)
        restraints_file = cleaned_data.get("restraints_file")
        if restraints_file:
            files["restraints.csv"] = restraints_file.read()
            params["has_restraints"] = True

        return {
            "sequences": sequences,
            "params": params,
            "files": files,
        }

    def resolve_runner_key(self, cleaned_data: dict) -> str:
        return "chai-1"

    def get_output_context(self, job) -> dict:
        """Chai-1 classifies structure files (.pdb, .cif) as primary results."""
        outdir = job.workdir / "output"
        primary, aux = [], []
        if outdir.exists() and outdir.is_dir():
            for p in sorted(outdir.iterdir()):
                if not p.is_file():
                    continue
                entry = {"name": p.name, "size": p.stat().st_size}
                if p.suffix in (".pdb", ".cif", ".mmcif"):
                    primary.append(entry)
                else:
                    aux.append(entry)
        return {
            "files": primary + aux,
            "primary_files": primary,
            "aux_files": aux,
        }
