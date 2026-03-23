from pydantic import BaseModel, ConfigDict
from typing import Optional


class RoomBase(BaseModel):
	codigo_sala: Optional[int] = None
	tipo_sala: Optional[str] = None
	ativada: Optional[bool] = True
	limite_usuarios: Optional[int] = 0
	descricao_sala: Optional[str] = None
	imagem: Optional[str] = None


class RoomCreate(RoomBase):
	pass


class RoomUpdate(RoomBase):
	sala_ativada: Optional[bool] = None


class RoomOut(RoomBase):
	id: int
	sala_ativada: bool

	model_config = ConfigDict(from_attributes=True)


