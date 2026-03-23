# app/schemas/room_type.py

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional

class TipoSalaBase(BaseModel):
    nome: str = Field(..., min_length=3, max_length=100, examples=["Laboratório"])

class TipoSalaCreate(TipoSalaBase):
    pass

class TipoSalaUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=3, max_length=100)

class TipoSalaOut(TipoSalaBase):
    id: int

    model_config = ConfigDict(from_attributes=True)