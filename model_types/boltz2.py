from __future__ import annotations

from jobs.forms import Boltz2SubmitForm
from model_types.base import BaseModelType, InputPayload
from model_types.parsers import parse_fasta_batch, parse_json_config


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

    def parse_batch(self, upload) -> list[dict]:
        """Parse a multi-FASTA upload into per-sequence input overrides.

        Returns a list of dicts, each with ``sequences`` and ``name`` keys.
        These are merged with the base form cleaned_data before calling
        :meth:`normalize_inputs` for each batch item.
        """
        text = upload.read().decode("utf-8")
        entries = parse_fasta_batch(text)
        return [
            {
                "sequences": f">{entry['header']}\n{entry['sequence']}",
                "name": entry["header"][:100],
            }
            for entry in entries
        ]

    def parse_config(self, upload) -> dict:
        """Parse a JSON config file into param overrides.

        Accepted keys: ``recycling_steps``, ``sampling_steps``,
        ``diffusion_samples``, ``use_msa_server``, ``use_potentials``,
        ``output_format``.
        """
        data = parse_json_config(upload)
        allowed_keys = {
            "recycling_steps",
            "sampling_steps",
            "diffusion_samples",
            "use_msa_server",
            "use_potentials",
            "output_format",
        }
        return {k: v for k, v in data.items() if k in allowed_keys}

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
