from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from fold_webapp.schemas import Entity


class PredictionModel(ABC):
    """Model integration contract.

    Future models (ESMFold, OpenFold, etc.) should implement this interface.
    """

    @property
    @abstractmethod
    def key(self) -> str:
        """Stable identifier for the model (used for routing/selection)."""

    @abstractmethod
    def prepare_input(self, *, job_name: str, model_seed: int, entities: list[Entity]) -> dict[str, Any]:
        """Convert UI entities to model-specific input JSON."""

    @abstractmethod
    def get_run_command(self, *, input_path: Path, output_dir: Path) -> list[str]:
        """Return argv for starting the model run."""

    @abstractmethod
    def find_primary_structure_file(self, *, job_dir: Path) -> Path | None:
        """Find the main structure file for visualization, if present."""


