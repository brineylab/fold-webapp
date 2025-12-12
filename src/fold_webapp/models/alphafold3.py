from __future__ import annotations

from pathlib import Path
from typing import Any

from fold_webapp.config import get_settings
from fold_webapp.models.base import PredictionModel
from fold_webapp.schemas import Entity, EntityType


class AlphaFold3Model(PredictionModel):
    key = "alphafold3"

    def prepare_input(self, *, job_name: str, model_seed: int, entities: list[Entity]) -> dict[str, Any]:
        seqs: list[dict[str, Any]] = []
        for ent in entities:
            ids = [chr(ord(ent.id) + i) for i in range(ent.copies)]
            if ent.type == EntityType.protein:
                seqs.append({"protein": {"id": ids, "sequence": ent.seq.strip()}})
            elif ent.type == EntityType.dna:
                seqs.append({"dna": {"id": ids, "sequence": ent.seq.strip()}})
            elif ent.type == EntityType.rna:
                seqs.append({"rna": {"id": ids, "sequence": ent.seq.strip()}})
            else:  # pragma: no cover
                raise ValueError(f"Unsupported entity type: {ent.type}")

        return {
            "name": job_name,
            "dialect": "alphafold3",
            "version": 1,
            "modelSeeds": [model_seed],
            "sequences": seqs,
        }

    def get_run_command(self, *, input_path: Path, output_dir: Path) -> list[str]:
        settings = get_settings()
        return [settings.af3_run_cmd, str(input_path), str(output_dir)]

    def find_primary_structure_file(self, *, job_dir: Path) -> Path | None:
        matches = sorted(job_dir.glob("**/*model.cif"))
        return matches[0] if matches else None


