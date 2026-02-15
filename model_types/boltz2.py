from __future__ import annotations

from jobs.forms import Boltz2SubmitForm
from model_types.base import BaseModelType, InputPayload


class Boltz2ModelType(BaseModelType):
    key = "boltz2"
    name = "Boltz-2"
    category = "Structure Prediction"
    template_name = "jobs/submit_boltz2.html"
    form_class = Boltz2SubmitForm
    help_text = "Predict biomolecular structure and binding affinity with Boltz-2. Supports proteins, nucleic acids, small molecules, and multimeric complexes."
    _runner_key = "boltz-2"

    def validate(self, cleaned_data: dict) -> None:
        # Form enforces that either sequences or input_file is provided.
        # Add domain-specific cross-field checks here as needed, e.g.
        # multi-chain complex validation, ligand SMILES checks, etc.
        pass

    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        sequences = (cleaned_data.get("sequences") or "").strip()
        params = {
            "use_msa_server": bool(cleaned_data.get("use_msa_server")),
            "use_potentials": bool(cleaned_data.get("use_potentials")),
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
