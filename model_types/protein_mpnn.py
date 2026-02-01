from __future__ import annotations

from jobs.forms import ProteinMPNNSubmitForm
from model_types.base import BaseModelType, InputPayload


class ProteinMPNNModelType(BaseModelType):
    key = "protein_mpnn"
    name = "ProteinMPNN"
    category = "Inverse Folding"
    template_name = "jobs/submit_protein_mpnn.html"
    form_class = ProteinMPNNSubmitForm
    help_text = "Design amino acid sequences for a given protein backbone using ProteinMPNN."

    def validate(self, cleaned_data: dict) -> None:
        pass

    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        pdb_file = cleaned_data.get("pdb_file")
        files: dict[str, bytes] = {}
        if pdb_file:
            files["input.pdb"] = pdb_file.read()

        params: dict = {
            "model_variant": "protein_mpnn",
            "noise_level": cleaned_data.get("noise_level"),
            "temperature": cleaned_data.get("temperature"),
            "num_sequences": cleaned_data.get("num_sequences"),
            "chains_to_design": cleaned_data.get("chains_to_design"),
            "fixed_residues": cleaned_data.get("fixed_residues"),
            "seed": cleaned_data.get("seed"),
        }
        params = {k: v for k, v in params.items() if v not in (None, "")}

        return {
            "sequences": "",
            "params": params,
            "files": files,
        }

    def resolve_runner_key(self, cleaned_data: dict) -> str:
        return "ligandmpnn"

    def get_output_context(self, job) -> dict:
        """Classify output files: FASTA in seqs/ = primary, everything else = auxiliary."""
        outdir = job.workdir / "output"
        primary, aux = [], []
        if outdir.exists() and outdir.is_dir():
            for p in sorted(outdir.rglob("*")):
                if not p.is_file():
                    continue
                rel = p.relative_to(outdir)
                entry = {"name": str(rel), "size": p.stat().st_size}
                if rel.parts[0] == "seqs" and p.suffix in (".fa", ".fasta"):
                    primary.append(entry)
                else:
                    aux.append(entry)
        return {
            "files": primary + aux,
            "primary_files": primary,
            "aux_files": aux,
        }
