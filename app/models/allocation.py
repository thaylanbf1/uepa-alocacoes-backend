from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.try_database import Base

class Alocacao(Base):
    __tablename__ = "alocacao"

    id = Column(Integer, primary_key=True)
    fk_usuario = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    fk_sala = Column(Integer, ForeignKey("salas.id"), nullable=False)
    tipo = Column(String(50), nullable=False)
    dia_horario_inicio = Column(DateTime, nullable=False)
    dia_horario_saida = Column(DateTime, nullable=False)
    uso = Column(String(255))
    justificativa = Column(String(255))
    oficio = Column(String(255))
    recurrency = Column(String, nullable=True)