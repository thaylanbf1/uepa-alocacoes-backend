from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.try_database import Base

class Sala(Base):
    __tablename__ = "salas"

    id = Column(Integer, primary_key=True)
    sala_ativada = Column(Boolean, default=True)
    codigo_sala = Column(Integer, unique=True)
    fk_tipo_sala = Column(Integer, ForeignKey("tipos_sala.id"))
    ativada = Column(Boolean, default=True)
    limite_usuarios = Column(Integer, default=0)
    descricao_sala = Column(String(255))
    imagem = Column(String(255))

    tipo_sala_rel = relationship("TipoSala", lazy="joined")

    @property
    def tipo_sala(self):
        return self.tipo_sala_rel.nome if self.tipo_sala_rel else None
