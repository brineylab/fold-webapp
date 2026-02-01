from __future__ import annotations

from jobs.forms import Boltz2SubmitForm
from model_types.base import BaseModelType, InputPayload


class Boltz2ModelType(BaseModelType):
    key = "boltz2"
    name = "Boltz-2"
    template_name = "jobs/submit_boltz2.html"
    form_class = Boltz2SubmitForm
    help_text = "Predict biomolecular structure and binding affinity with Boltz-2."
    _runner_key = "boltz-2"

    def validate(self, cleaned_data: dict) -> None:
        # Form enforces that sequences is required and non-empty.
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
        return {
            "sequences": sequences,
            "params": params,
            "files": {},
        }

    def resolve_runner_key(self, cleaned_data: dict) -> str:
        return "boltz-2"
