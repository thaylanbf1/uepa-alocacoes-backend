from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ReservationBase(BaseModel):
	fk_usuario: int
	fk_sala: int
	tipo: str = Field(..., min_length=1, max_length=50)
	dia_horario_inicio: datetime
	dia_horario_saida: datetime
	uso: Optional[str] = None
	justificativa: Optional[str] = None
	oficio: Optional[str] = None
	recurrency: Optional[str] = None


class ReservationCreate(ReservationBase):
	pass


class ReservationUpdate(BaseModel):
	fk_usuario: Optional[int] = None
	fk_sala: Optional[int] = None
	tipo: Optional[str] = Field(None, min_length=1, max_length=50)
	dia_horario_inicio: Optional[datetime] = None
	dia_horario_saida: Optional[datetime] = None
	uso: Optional[str] = None
	justificativa: Optional[str] = None
	oficio: Optional[str] = None
	recurrency: Optional[str] = None



