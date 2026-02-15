from __future__ import annotations

from model_types.base import InputPayload
from model_types.bindcraft import BindCraftModelType
from model_types.boltz2 import Boltz2ModelType
from model_types.boltzgen import BoltzGenModelType
from model_types.rfdiffusion import RFdiffusionModelType
from model_types.rfdiffusion3 import RFdiffusion3ModelType
from model_types.chai1 import Chai1ModelType
from model_types.ligand_mpnn import LigandMPNNModelType
from model_types.protein_mpnn import ProteinMPNNModelType
from model_types.registry import (
    get_model_type,
    get_model_types_by_category,
    get_submittable_model_types,
    register_model_type,
)


register_model_type(Boltz2ModelType())
register_model_type(Chai1ModelType())
register_model_type(ProteinMPNNModelType())
register_model_type(LigandMPNNModelType())
register_model_type(BindCraftModelType())
register_model_type(RFdiffusionModelType())
register_model_type(RFdiffusion3ModelType())
register_model_type(BoltzGenModelType())

__all__ = [
    "InputPayload",
    "get_model_type",
    "get_model_types_by_category",
    "get_submittable_model_types",
    "register_model_type",
]
