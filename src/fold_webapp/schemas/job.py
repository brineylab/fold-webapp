from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints


class EntityType(str, Enum):
    protein = "Protein"
    dna = "DNA"
    rna = "RNA"


EntityId = Annotated[str, StringConstraints(min_length=1, max_length=8)]
EntitySequence = Annotated[str, StringConstraints(strip_whitespace=True, min_length=0)]


class Entity(BaseModel):
    type: EntityType
    id: EntityId
    name: str = Field(min_length=1)
    seq: EntitySequence = ""
    copies: int = Field(default=1, ge=1, le=50)


class JobCreateRequest(BaseModel):
    job_name: str = Field(min_length=1)
    model_seed: int = Field(default=1, ge=1, le=100)
    entities: list[Entity] = Field(default_factory=list)


