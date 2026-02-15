from __future__ import annotations

from jobs.forms import LigandMPNNSubmitForm
from model_types.base import BaseModelType, InputPayload


class LigandMPNNModelType(BaseModelType):
    key = "ligand_mpnn"
    name = "LigandMPNN"
    category = "Inverse Folding"
    template_name = "jobs/submit_ligand_mpnn.html"
    form_class = LigandMPNNSubmitForm
    help_text = "Design amino acid sequences with ligand-aware inverse folding using LigandMPNN."

    def validate(self, cleaned_data: dict) -> None:
        pass

    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        pdb_file = cleaned_data.get("pdb_file")
        files: dict[str, bytes] = {}
        if pdb_file:
            files["input.pdb"] = pdb_file.read()

        params: dict = {
            "model_variant": "ligand_mpnn",
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
        """Return results.zip as primary download, falling back to per-file listing."""
        outdir = job.workdir / "output"
        primary, aux = [], []
        if outdir.exists() and outdir.is_dir():
            zipfile = outdir / "results.zip"
            if zipfile.is_file():
                primary.append({"name": "results.zip", "size": zipfile.stat().st_size})
                for p in sorted(outdir.rglob("*")):
                    if not p.is_file() or p.name == "results.zip":
                        continue
                    rel = p.relative_to(outdir)
                    aux.append({"name": str(rel), "size": p.stat().st_size})
            else:
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
