from __future__ import annotations

import json

from jobs.forms import BindCraftSubmitForm
from model_types.base import BaseModelType, InputPayload


class BindCraftModelType(BaseModelType):
    key = "bindcraft"
    name = "BindCraft"
    category = "Protein Design"
    template_name = "jobs/submit_bindcraft.html"
    form_class = BindCraftSubmitForm
    help_text = "Design novel protein binders against a target structure using BindCraft (AlphaFold2 + MPNN + PyRosetta)."

    def validate(self, cleaned_data: dict) -> None:
        pass  # Form handles validation

    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        pdb_file = cleaned_data.get("pdb_file")
        files: dict[str, bytes] = {}
        if pdb_file:
            files["target.pdb"] = pdb_file.read()

        filters_file = cleaned_data.get("filters_file")
        if filters_file:
            files["filters.json"] = filters_file.read()
        advanced_file = cleaned_data.get("advanced_file")
        if advanced_file:
            files["advanced.json"] = advanced_file.read()

        params: dict = {
            "target_chain": cleaned_data.get("target_chain", "A"),
            "hotspot_residues": cleaned_data.get("hotspot_residues", ""),
            "length_min": cleaned_data.get("length_min"),
            "length_max": cleaned_data.get("length_max"),
            "number_of_final_designs": cleaned_data.get("number_of_final_designs"),
            "has_custom_filters": bool(filters_file),
            "has_custom_advanced": bool(advanced_file),
        }
        params = {k: v for k, v in params.items() if v not in (None, "", False)}

        return {
            "sequences": "",
            "params": params,
            "files": files,
        }

    def resolve_runner_key(self, cleaned_data: dict) -> str:
        return "bindcraft"

    def prepare_workdir(self, job, input_payload: InputPayload) -> None:
        """Custom workdir: write PDB + generate target settings JSON."""
        super().prepare_workdir(job, input_payload)

        params = input_payload.get("params", {})
        target_settings = {
            "design_path": "/work/output",
            "binder_name": f"binder_{job.id}",
            "starting_pdb": "/work/input/target.pdb",
            "chains": params.get("target_chain", "A"),
            "target_hotspot_residues": params.get("hotspot_residues", ""),
            "lengths": [
                params.get("length_min", 65),
                params.get("length_max", 150),
            ],
            "number_of_final_designs": params.get("number_of_final_designs", 10),
        }
        settings_path = job.workdir / "input" / "target_settings.json"
        settings_path.write_text(json.dumps(target_settings, indent=2))

    def get_output_context(self, job) -> dict:
        """Classify PDB files as primary, everything else as auxiliary."""
        outdir = job.workdir / "output"
        primary, aux = [], []
        if outdir.exists() and outdir.is_dir():
            for p in sorted(outdir.rglob("*")):
                if not p.is_file():
                    continue
                rel = p.relative_to(outdir)
                entry = {"name": str(rel), "size": p.stat().st_size}
                if p.suffix in (".pdb", ".cif"):
                    primary.append(entry)
                else:
                    aux.append(entry)
        return {
            "files": primary + aux,
            "primary_files": primary,
            "aux_files": aux,
        }
