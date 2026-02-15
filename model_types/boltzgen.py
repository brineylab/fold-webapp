from __future__ import annotations

import yaml

from jobs.forms import BoltzGenSubmitForm
from model_types.base import BaseModelType, InputPayload


class BoltzGenModelType(BaseModelType):
    key = "boltzgen"
    name = "BoltzGen"
    category = "Protein Design"
    template_name = "jobs/submit_boltzgen.html"
    form_class = BoltzGenSubmitForm
    help_text = (
        "Design novel protein and peptide binders using BoltzGen. "
        "Supports protein binders, peptide binders, small molecule binders, "
        "and nanobody design."
    )

    def validate(self, cleaned_data: dict) -> None:
        pass  # Form handles validation

    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        protocol = cleaned_data.get("protocol", "protein-anything")
        files: dict[str, bytes] = {}
        params: dict = {"protocol": protocol}

        if protocol == "yaml_upload":
            yaml_file = cleaned_data.get("yaml_file")
            if yaml_file:
                files["design.yaml"] = yaml_file.read()
        else:
            target_file = cleaned_data.get("target_file")
            if target_file:
                ext = target_file.name.rsplit(".", 1)[-1] if "." in target_file.name else "pdb"
                filename = f"target.{ext}"
                files[filename] = target_file.read()
                params["target_filename"] = filename

            params["target_chains"] = cleaned_data.get("target_chains", "A")
            params["num_designs"] = cleaned_data.get("num_designs") or 100
            params["budget"] = cleaned_data.get("budget") or 10
            params["alpha"] = cleaned_data.get("alpha") if cleaned_data.get("alpha") is not None else 0.001

            if protocol in ("protein-anything", "protein-small_molecule"):
                params["length_min"] = cleaned_data.get("binder_length_min") or 80
                params["length_max"] = cleaned_data.get("binder_length_max") or 150
            elif protocol == "peptide-anything":
                params["length_min"] = cleaned_data.get("peptide_length_min") or 8
                params["length_max"] = cleaned_data.get("peptide_length_max") or 20

        return {
            "sequences": "",
            "params": params,
            "files": files,
        }

    def resolve_runner_key(self, cleaned_data: dict) -> str:
        return "boltzgen"

    def prepare_workdir(self, job, input_payload: InputPayload) -> None:
        """Write input files and generate design YAML for protocol modes."""
        super().prepare_workdir(job, input_payload)

        params = input_payload.get("params", {})
        protocol = params.get("protocol", "protein-anything")

        # For yaml_upload, the uploaded YAML is already written by the base class
        if protocol == "yaml_upload":
            return

        # Build the design YAML specification from params
        target_filename = params.get("target_filename", "target.pdb")
        target_chains = [c.strip() for c in params.get("target_chains", "A").split(",")]

        design_spec: dict = {
            "protocol": protocol,
            "target": {
                "structure": f"/work/input/{target_filename}",
                "chains": target_chains,
            },
        }

        # Add length range for protocols that use it
        length_min = params.get("length_min")
        length_max = params.get("length_max")
        if length_min is not None and length_max is not None:
            design_spec["binder"] = {
                "length_min": length_min,
                "length_max": length_max,
            }

        design_spec["num_designs"] = params.get("num_designs", 100)
        design_spec["budget"] = params.get("budget", 10)
        design_spec["alpha"] = params.get("alpha", 0.001)

        design_path = job.workdir / "input" / "design.yaml"
        design_path.write_text(yaml.dump(design_spec, default_flow_style=False))

    def get_output_context(self, job) -> dict:
        """Classify CIF/PDB files as primary, everything else as auxiliary."""
        outdir = job.workdir / "output"
        primary, aux = [], []
        if outdir.exists() and outdir.is_dir():
            for p in sorted(outdir.rglob("*")):
                if not p.is_file():
                    continue
                rel = p.relative_to(outdir)
                entry = {"name": str(rel), "size": p.stat().st_size}
                if p.suffix in (".cif", ".pdb"):
                    primary.append(entry)
                else:
                    aux.append(entry)
        return {
            "files": primary + aux,
            "primary_files": primary,
            "aux_files": aux,
        }
