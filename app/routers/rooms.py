from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.try_database import get_db
from app.models import Sala, TipoSala  
from app.schemas.room import RoomCreate, RoomOut, RoomUpdate
from app.services.rbac import require_role, ROLE_ADMIN
from app.config import get_settings

router = APIRouter(prefix="/rooms", tags=["rooms"])
settings = get_settings()

@router.get("/", response_model=List[RoomOut])
def list_rooms(db: Session = Depends(get_db), _u=Depends(require_role(1))):
    return db.query(Sala).all()


@router.post("/", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
def create_room(payload: RoomCreate, db: Session = Depends(get_db), current=Depends(require_role(ROLE_ADMIN))):
    
    data = payload.model_dump(exclude_unset=True)
    tipo_sala_nome = data.pop("tipo_sala", None) 
    fk_tipo_sala_id = None

    if tipo_sala_nome:
        if settings.ROOM_TYPES and tipo_sala_nome not in settings.ROOM_TYPES:
            raise HTTPException(status_code=400, detail="tipo_sala inválido (config)")

        tipo_sala_obj = db.query(TipoSala).filter(TipoSala.nome == tipo_sala_nome).first()
        
        if not tipo_sala_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"O tipo_sala '{tipo_sala_nome}' não foi encontrado. Crie-o primeiro."
            )
        
        fk_tipo_sala_id = tipo_sala_obj.id

    room = Sala(**data, fk_tipo_sala=fk_tipo_sala_id)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


@router.put("/{room_id}", response_model=RoomOut)
def update_room(room_id: int, payload: RoomUpdate, db: Session = Depends(get_db), current=Depends(require_role(ROLE_ADMIN))):
    room = db.query(Sala).filter(Sala.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    data = payload.model_dump(exclude_unset=True)

    if "tipo_sala" in data:
        tipo_sala_nome = data.pop("tipo_sala") 
        
        if tipo_sala_nome:
            if settings.ROOM_TYPES and tipo_sala_nome not in settings.ROOM_TYPES:
                raise HTTPException(status_code=400, detail="tipo_sala inválido (config)")
            
            tipo_sala_obj = db.query(TipoSala).filter(TipoSala.nome == tipo_sala_nome).first()
            if not tipo_sala_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, 
                    detail=f"O tipo_sala '{tipo_sala_nome}' não foi encontrado."
                )
            
            setattr(room, 'fk_tipo_sala', tipo_sala_obj.id)
        else:
            setattr(room, 'fk_tipo_sala', None)

    for k, v in data.items():
        setattr(room, k, v)
        
    db.commit()
    db.refresh(room)
    return room


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_room(room_id: int, db: Session = Depends(get_db), current=Depends(require_role(ROLE_ADMIN))):
    room = db.query(Sala).filter(Sala.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    db.delete(room)
    db.commit()
    return