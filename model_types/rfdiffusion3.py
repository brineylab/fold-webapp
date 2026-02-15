from __future__ import annotations

import json

from django.core.exceptions import ValidationError

from jobs.forms import RFdiffusion3SubmitForm
from model_types.base import BaseModelType, InputPayload


class RFdiffusion3ModelType(BaseModelType):
    key = "rfdiffusion3"
    name = "RFdiffusion3"
    category = "Protein Design"
    template_name = "jobs/submit_rfdiffusion3.html"
    form_class = RFdiffusion3SubmitForm
    help_text = (
        "All-atom protein design using RFdiffusion3. Supports protein binder design, "
        "small molecule binder design, nucleic acid binder design, enzyme design, "
        "motif scaffolding, partial diffusion, symmetric design, and unconditional generation."
    )

    def validate(self, cleaned_data: dict) -> None:
        mode = cleaned_data.get("mode")
        if mode == "partial":
            partial_t = cleaned_data.get("partial_t")
            if partial_t is not None and partial_t <= 0:
                raise ValidationError("partial_t must be positive.")

    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        mode = cleaned_data.get("mode", "unconditional")
        files: dict[str, bytes] = {}
        params: dict = {
            "mode": mode,
            "num_designs": cleaned_data.get("num_designs") or 8,
            "n_batches": cleaned_data.get("n_batches") or 1,
            "timesteps": cleaned_data.get("timesteps") or 200,
            "step_scale": cleaned_data.get("step_scale") or 1.5,
        }

        input_spec: dict = {}

        if mode == "unconditional":
            length_min = cleaned_data.get("length_min", 50)
            length_max = cleaned_data.get("length_max", 200)
            input_spec = {
                "design": {
                    "contig": f"{length_min}-{length_max}",
                    "length": f"{length_min}-{length_max}",
                },
            }

        elif mode == "protein_binder":
            target_pdb = cleaned_data.get("target_pdb")
            if target_pdb:
                files["target.pdb"] = target_pdb.read()
            target_chain = cleaned_data.get("target_chain", "A")
            binder_min = cleaned_data.get("binder_length_min", 40)
            binder_max = cleaned_data.get("binder_length_max", 120)
            design = {
                "input": "target.pdb",
                "contig": f"{target_chain}1-1000,/0,{binder_min}-{binder_max}",
                "is_non_loopy": cleaned_data.get("is_non_loopy", True),
            }
            hotspot = (cleaned_data.get("hotspot_residues") or "").strip()
            if hotspot:
                # Parse hotspot string like "E64,E88" into select_hotspots dict
                residues = [r.strip() for r in hotspot.split(",") if r.strip()]
                design["select_hotspots"] = {"residues": residues}
                design["infer_ori_strategy"] = "hotspots"
            input_spec = {"design": design}

        elif mode == "small_molecule_binder":
            sm_target_pdb = cleaned_data.get("sm_target_pdb")
            if sm_target_pdb:
                files["target.pdb"] = sm_target_pdb.read()
            sm_ligand = (cleaned_data.get("sm_ligand_name") or "").strip()
            sm_min = cleaned_data.get("sm_binder_length_min", 50)
            sm_max = cleaned_data.get("sm_binder_length_max", 150)
            input_spec = {
                "design": {
                    "input": "target.pdb",
                    "ligand": sm_ligand,
                    "contig": f"A1-1000,/0,{sm_min}-{sm_max}",
                    "length": f"{sm_min}-{sm_max}",
                },
            }

        elif mode == "nucleic_acid_binder":
            na_target_pdb = cleaned_data.get("na_target_pdb")
            if na_target_pdb:
                files["target.pdb"] = na_target_pdb.read()
            na_chain = cleaned_data.get("na_target_chain", "B")
            na_min = cleaned_data.get("na_binder_length_min", 50)
            na_max = cleaned_data.get("na_binder_length_max", 150)
            input_spec = {
                "design": {
                    "input": "target.pdb",
                    "contig": f"{na_chain}1-1000,/0,{na_min}-{na_max}",
                    "length": f"{na_min}-{na_max}",
                },
            }

        elif mode == "enzyme":
            enzyme_pdb = cleaned_data.get("enzyme_target_pdb")
            if enzyme_pdb:
                files["target.pdb"] = enzyme_pdb.read()
            ligand = (cleaned_data.get("enzyme_ligand_name") or "").strip()
            catalytic = (cleaned_data.get("enzyme_catalytic_residues") or "").strip()
            enz_min = cleaned_data.get("enzyme_scaffold_length_min", 100)
            enz_max = cleaned_data.get("enzyme_scaffold_length_max", 300)
            design: dict = {
                "input": "target.pdb",
                "ligand": ligand,
                "contig": f"A1-1000,/0,{enz_min}-{enz_max}",
                "length": f"{enz_min}-{enz_max}",
            }
            if catalytic:
                residues = [r.strip() for r in catalytic.split(",") if r.strip()]
                design["select_fixed_atoms"] = {"residues": residues}
            input_spec = {"design": design}

        elif mode == "motif":
            motif_pdb = cleaned_data.get("motif_input_pdb")
            if motif_pdb:
                files["input.pdb"] = motif_pdb.read()
            contig = (cleaned_data.get("motif_contig") or "").strip()
            design = {
                "input": "input.pdb",
                "contig": contig,
            }
            motif_min = cleaned_data.get("motif_length_min")
            motif_max = cleaned_data.get("motif_length_max")
            if motif_min and motif_max:
                design["length"] = f"{motif_min}-{motif_max}"
            input_spec = {"design": design}

        elif mode == "partial":
            partial_pdb = cleaned_data.get("partial_input_pdb")
            if partial_pdb:
                files["input.pdb"] = partial_pdb.read()
            contig = (cleaned_data.get("partial_contig") or "").strip()
            partial_t = cleaned_data.get("partial_t", 10.0)
            input_spec = {
                "design": {
                    "input": "input.pdb",
                    "contig": contig,
                    "partial_t": partial_t,
                },
            }

        elif mode == "symmetric":
            sym_contig = (cleaned_data.get("sym_contig") or "").strip()
            sym_type = (cleaned_data.get("sym_type") or "").strip()
            input_spec = {
                "design": {
                    "contig": sym_contig,
                    "symmetry": {"type": sym_type},
                },
            }
            params["symmetric"] = True

        elif mode == "json_upload":
            input_json = cleaned_data.get("input_json")
            if input_json:
                raw = input_json.read()
                files["input_spec.json"] = raw
                # Try to parse as JSON to store in params
                try:
                    input_spec = json.loads(raw)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # YAML or invalid JSON - store raw and let rfd3 handle it
                    input_spec = {}

        params["input_spec"] = input_spec

        return {
            "sequences": "",
            "params": params,
            "files": files,
        }

    def resolve_runner_key(self, cleaned_data: dict) -> str:
        return "rfdiffusion3"

    def prepare_workdir(self, job, input_payload: InputPayload) -> None:
        """Write input files and generate input_spec.json."""
        super().prepare_workdir(job, input_payload)

        params = input_payload.get("params", {})
        mode = params.get("mode", "")

        # For json_upload mode, the raw file is already written by super()
        # For all other modes, write the generated input spec
        if mode != "json_upload":
            input_spec = params.get("input_spec", {})
            if input_spec:
                spec_path = job.workdir / "input" / "input_spec.json"
                spec_path.write_text(json.dumps(input_spec, indent=2))

    def get_output_context(self, job) -> dict:
        """Classify CIF/PDB files as primary, trajectory and metadata as auxiliary."""
        outdir = job.workdir / "output"
        primary, aux = [], []
        if outdir.exists() and outdir.is_dir():
            for p in sorted(outdir.rglob("*")):
                if not p.is_file():
                    continue
                rel = p.relative_to(outdir)
                entry = {"name": str(rel), "size": p.stat().st_size}
                if p.suffix in (".pdb", ".cif") and "traj" not in str(rel):
                    primary.append(entry)
                else:
                    aux.append(entry)
        return {
            "files": primary + aux,
            "primary_files": primary,
            "aux_files": aux,
        }
