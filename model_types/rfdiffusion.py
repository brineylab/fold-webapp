from __future__ import annotations

from django.core.exceptions import ValidationError

from jobs.forms import RFdiffusionSubmitForm
from model_types.base import BaseModelType, InputPayload


class RFdiffusionModelType(BaseModelType):
    key = "rfdiffusion"
    name = "RFdiffusion"
    category = "Protein Design"
    template_name = "jobs/submit_rfdiffusion.html"
    form_class = RFdiffusionSubmitForm
    help_text = "Generate protein backbones using RFdiffusion. Supports unconditional generation, binder design, motif scaffolding, partial diffusion, and symmetric oligomers."

    def validate(self, cleaned_data: dict) -> None:
        mode = cleaned_data.get("mode")
        if mode == "partial":
            partial_T = cleaned_data.get("partial_T")
            timesteps = cleaned_data.get("timesteps") or 50
            if partial_T and partial_T >= timesteps:
                raise ValidationError(
                    f"partial_T ({partial_T}) must be less than timesteps ({timesteps})."
                )

    def normalize_inputs(self, cleaned_data: dict) -> InputPayload:
        mode = cleaned_data.get("mode", "unconditional")
        files: dict[str, bytes] = {}
        params: dict = {
            "mode": mode,
            "num_designs": cleaned_data.get("num_designs") or 10,
            "timesteps": cleaned_data.get("timesteps") or 50,
        }

        if mode == "unconditional":
            length_min = cleaned_data.get("length_min", 100)
            length_max = cleaned_data.get("length_max", 200)
            params["contigs"] = f"[{length_min}-{length_max}]"

        elif mode == "binder":
            target_pdb = cleaned_data.get("target_pdb")
            if target_pdb:
                files["target.pdb"] = target_pdb.read()
            target_chain = cleaned_data.get("target_chain", "A")
            binder_min = cleaned_data.get("binder_length_min", 70)
            binder_max = cleaned_data.get("binder_length_max", 100)
            # RFdiffusion contig: target chain (use large number, clipped to actual length)
            # then binder range
            params["contigs"] = f"[{target_chain}1-1000/0 {binder_min}-{binder_max}]"
            hotspot = (cleaned_data.get("hotspot_residues") or "").strip()
            if hotspot:
                params["hotspot_residues"] = hotspot

        elif mode in ("motif", "partial"):
            input_pdb = cleaned_data.get("input_pdb")
            if input_pdb:
                files["input.pdb"] = input_pdb.read()
            contigs = (cleaned_data.get("contigs") or "").strip()
            # Auto-wrap in brackets if user forgot
            if contigs and not contigs.startswith("["):
                contigs = f"[{contigs}]"
            params["contigs"] = contigs
            if mode == "partial":
                params["partial_T"] = cleaned_data.get("partial_T")

        elif mode == "symmetric":
            symmetry_type = cleaned_data.get("symmetry_type", "cyclic")
            symmetry_order = cleaned_data.get("symmetry_order", 3)
            subunit_length = cleaned_data.get("subunit_length", 100)
            params["symmetry_type"] = symmetry_type
            params["symmetry_order"] = symmetry_order
            params["contigs"] = f"[{subunit_length}-{subunit_length}]"

        return {
            "sequences": "",
            "params": params,
            "files": files,
        }

    def resolve_runner_key(self, cleaned_data: dict) -> str:
        return "rfdiffusion"

    def get_output_context(self, job) -> dict:
        """Classify root PDB files as primary, traj/ contents as auxiliary."""
        outdir = job.workdir / "output"
        primary, aux = [], []
        if outdir.exists() and outdir.is_dir():
            for p in sorted(outdir.rglob("*")):
                if not p.is_file():
                    continue
                rel = p.relative_to(outdir)
                entry = {"name": str(rel), "size": p.stat().st_size}
                # Trajectory files and non-PDB files are auxiliary
                if str(rel).startswith("traj/") or p.suffix != ".pdb":
                    aux.append(entry)
                else:
                    primary.append(entry)
        return {
            "files": primary + aux,
            "primary_files": primary,
            "aux_files": aux,
        }
