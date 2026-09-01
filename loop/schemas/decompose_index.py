from pydantic import BaseModel, Field
from typing import List, Optional


class DecomposeStep(BaseModel):
    id: str
    file: str
    title: str
    next_phase: str
    status: str
    depends_on: List[str] = Field(default_factory=list)


class DecomposeIndex(BaseModel):
    schema: str = Field(alias="schema")
    plan_id: str
    steps: List[DecomposeStep]
