from typing import Optional
from datetime import datetime
from dateutil import parser 
from dateutil.rrule import rrulestr
from sqlalchemy import and_, or_

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.try_database import get_db
from app.models import Sala, Alocacao, Usuario
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.rbac import require_role, ROLE_ADMIN
from app.services.datetime_utils import APP_TIMEZONE_NAME, ensure_utc, from_storage_datetime, to_storage_datetime
# Importa a função corrigida get_event_by_id
from app.services.google_calendar import list_events, create_event, update_event, delete_event, get_event_by_id

router = APIRouter(prefix="/reservations", tags=["reservations"])
PLATFORM_EVENT_SOURCE = "alocacoes"


def _is_platform_event(event: dict) -> bool:
    priv = (event.get("extendedProperties") or {}).get("private") or {}
    if priv.get("platform_source") == PLATFORM_EVENT_SOURCE:
        return True
    return bool(priv.get("fk_sala") and priv.get("fk_usuario"))


def _build_local_event(reservation: Alocacao, start_dt: datetime, end_dt: datetime, instance_id: Optional[str] = None) -> dict:
    event_dict = {
        "id": instance_id or str(reservation.id),
        "summary": reservation.uso or "Reservado",
        "description": reservation.justificativa or "",
        "recurrence": [reservation.recurrency] if reservation.recurrency and instance_id is None else None,
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": APP_TIMEZONE_NAME,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": APP_TIMEZONE_NAME,
        },
        "extendedProperties": {
            "private": {
                "fk_sala": str(reservation.fk_sala),
                "fk_usuario": str(reservation.fk_usuario),
                "tipo": str(reservation.tipo or ""),
                "uso": str(reservation.uso or ""),
                "oficio": str(reservation.oficio or ""),
                "platform_source": PLATFORM_EVENT_SOURCE,
                "local_reservation_id": str(reservation.id),
            }
        }
    }

    if instance_id is not None:
        event_dict["recurringEventId"] = str(reservation.id)

    return event_dict


def _expand_local_reservation(reservation: Alocacao, range_start: datetime, range_end: datetime) -> list[dict]:
    start_dt = from_storage_datetime(reservation.dia_horario_inicio)
    end_dt = from_storage_datetime(reservation.dia_horario_saida)

    if not reservation.recurrency:
        if end_dt < range_start or start_dt > range_end:
            return []
        return [_build_local_event(reservation, start_dt, end_dt)]

    try:
        recurrence = rrulestr(reservation.recurrency, dtstart=start_dt)
    except Exception as exc:
        print(f"Erro ao expandir recorrência local {reservation.id}: {exc}")
        if end_dt < range_start or start_dt > range_end:
            return []
        return [_build_local_event(reservation, start_dt, end_dt)]

    duration = end_dt - start_dt
    events = []

    for occurrence_start in recurrence.between(range_start, range_end, inc=True):
        occurrence_end = occurrence_start + duration
        instance_id = f"{reservation.id}:{occurrence_start.isoformat()}"
        events.append(_build_local_event(reservation, occurrence_start, occurrence_end, instance_id))

    return events


def _conflicts_google(db: Session, user_id: int, sala_id: int, start_dt: datetime, end_dt: datetime) -> bool:
    """Verifica conflitos consultando o Google Calendar (apenas para admins/criação)."""
    start_dt = ensure_utc(start_dt)
    end_dt = ensure_utc(end_dt)

    items = list_events(db=db, user_id=user_id, time_min_utc=start_dt, time_max_utc=end_dt)
    if items is None:
        return False
    
    for ev in items:
        priv = (ev.get("extendedProperties") or {}).get("private") or {}
        if str(priv.get("fk_sala")) == str(sala_id):
            return True
    return False


@router.get("/")
def list_reservations(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_role(1)), 
    room_id: Optional[int] = Query(None),
    user_id: Optional[int] = Query(None),
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
):
    if not date_from or not date_to:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_from and date_to are required")

    date_from_utc = ensure_utc(date_from)
    date_to_utc = ensure_utc(date_to)
    date_from_local = to_storage_datetime(date_from)
    date_to_local = to_storage_datetime(date_to)

    use_google = (current_user.tipo_usuario == 3)
    google_items = None

    if use_google:
        try:
            google_items = list_events(db=db, user_id=current_user.id, time_min_utc=date_from_utc, time_max_utc=date_to_utc)
        except Exception:
            google_items = None

    if google_items is not None:
        result = []
        for ev in google_items:
            if not _is_platform_event(ev):
                continue
            priv = (ev.get("extendedProperties") or {}).get("private") or {}
            if room_id is not None and str(priv.get("fk_sala")) != str(room_id):
                continue
            if user_id is not None and str(priv.get("fk_usuario")) != str(user_id):
                continue
            result.append(ev)
        return {"items": result}

    filters = []
    
    if room_id:
        filters.append(Alocacao.fk_sala == room_id)
    if user_id:
        filters.append(Alocacao.fk_usuario == user_id)

    filters.append(
        or_(
            and_(
                Alocacao.recurrency.is_(None),
                Alocacao.dia_horario_saida >= date_from_local,
                Alocacao.dia_horario_inicio <= date_to_local,
            ),
            and_(
                Alocacao.recurrency.is_not(None),
                Alocacao.dia_horario_inicio <= date_to_local,
            ),
        )
    )

    try:
        reservas_db = db.query(Alocacao).filter(and_(*filters)).all()
    except Exception as e:
        print(f"Erro ao ler banco local: {e}")
        return {"items": []}

    range_start = from_storage_datetime(date_from_local)
    range_end = from_storage_datetime(date_to_local)

    formatted_items = []
    for res in reservas_db:
        formatted_items.extend(_expand_local_reservation(res, range_start, range_end))

    formatted_items.sort(key=lambda event: event["start"]["dateTime"])

    return {"items": formatted_items}


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_reservation(payload: ReservationCreate, db: Session = Depends(get_db), current: Usuario = Depends(require_role(1))):
    if payload.dia_horario_saida <= payload.dia_horario_inicio:
        raise HTTPException(status_code=400, detail="A data de saída deve ser posterior à data de início.")
    
    room = db.query(Sala).filter(Sala.id == payload.fk_sala).first()
    if not room:
        raise HTTPException(status_code=404, detail="Sala não encontrada.")

    # Only admins can define status other than PENDING for now
    if current.tipo_usuario < ROLE_ADMIN:
        payload.status = "PENDING"
    elif not payload.status:
        payload.status = "APPROVED"

    start_dt = ensure_utc(payload.dia_horario_inicio)
    end_dt = ensure_utc(payload.dia_horario_saida)

    # Verifica conflitos apenas se estiver aprovando ou for admin criando direto
    if payload.status == "APPROVED":
        if _conflicts_google(db, current.id, payload.fk_sala, start_dt, end_dt):
            raise HTTPException(status_code=409, detail="Já existe uma reserva conflitante neste horário (Google Calendar).")
    
    # Se for aprovado, cria no Google Calendar
    google_events_ids = []
    if payload.status == "APPROVED":
        extended_props = {
            "fk_sala": str(payload.fk_sala),
            "fk_usuario": str(payload.fk_usuario),
            "tipo": payload.tipo,
            "uso": payload.uso or "",
            "oficio": payload.oficio or "",
            "platform_source": PLATFORM_EVENT_SOURCE,
            "status": "APPROVED",
        }
        
        if payload.recurrency:
            extended_props["recurrency"] = payload.recurrency
            
        # Fetch the applicant user to get their email for the attendee list
        applicant = db.query(Usuario).filter(Usuario.id == payload.fk_usuario).first()
        attendees = [applicant.email] if applicant and applicant.email else []

        events_list = create_event(
            db=db,
            user_id=current.id,
            summary=f"[{payload.tipo}] {payload.uso or f'Reserva Sala {room.codigo_sala or room.id}'}",
            description=payload.justificativa,
            start_dt_utc=start_dt,
            end_dt_utc=end_dt,
            location=room.descricao_sala,
            extended_private=extended_props,
            recurrence_rule=payload.recurrency,
            attendees=attendees
        )

        if not events_list:
             # Se falhar no google mas for admin, avisamos, mas talvez salvemos local? 
             # O comportamento original era falhar. Vamos manter.
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Erro ao criar evento no Google. Verifique as credenciais.")

        if isinstance(events_list, dict):
            events_list = [events_list]
        
        google_events_ids = [evt.get("id") for evt in events_list]

    try:
        # No nosso modelo local, as datas já vêm do payload se não veio do Google (PENDING case)
        dt_inicio = to_storage_datetime(payload.dia_horario_inicio)
        dt_saida = to_storage_datetime(payload.dia_horario_saida)

        nova_alocacao = Alocacao(
            fk_usuario=payload.fk_usuario,
            fk_sala=payload.fk_sala,
            tipo=payload.tipo,
            uso=payload.uso,
            justificativa=payload.justificativa,
            oficio=payload.oficio,
            dia_horario_inicio=dt_inicio,
            dia_horario_saida=dt_saida,
            recurrency=payload.recurrency,
            status=payload.status
        )
        db.add(nova_alocacao)
        db.commit()
        db.refresh(nova_alocacao)

    except Exception as e:
        db.rollback()
        print(f"CRITICAL DATABASE ERROR: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Falha ao salvar no Banco Local: {str(e)}"
        )

    return _build_local_event(nova_alocacao, payload.dia_horario_inicio, payload.dia_horario_saida)


@router.put("/{reservation_id}/approve", status_code=status.HTTP_200_OK)
def approve_reservation(reservation_id: int, db: Session = Depends(get_db), current=Depends(require_role(ROLE_ADMIN))):
    alocacao = db.query(Alocacao).filter(Alocacao.id == reservation_id).first()
    if not alocacao:
        raise HTTPException(status_code=404, detail="Reserva não encontrada.")

    if alocacao.status == "APPROVED":
        return {"message": "Reserva já está aprovada."}

    # Ao aprovar, criamos no Google Calendar
    room = db.query(Sala).filter(Sala.id == alocacao.fk_sala).first()
    start_dt = ensure_utc(from_storage_datetime(alocacao.dia_horario_inicio))
    end_dt = ensure_utc(from_storage_datetime(alocacao.dia_horario_saida))

    if _conflicts_google(db, current.id, alocacao.fk_sala, start_dt, end_dt):
        raise HTTPException(status_code=409, detail="Conflito detectado no Google Calendar ao tentar aprovar.")

    extended_props = {
        "fk_sala": str(alocacao.fk_sala),
        "fk_usuario": str(alocacao.fk_usuario),
        "tipo": alocacao.tipo,
        "uso": alocacao.uso or "",
        "oficio": alocacao.oficio or "",
        "platform_source": PLATFORM_EVENT_SOURCE,
        "local_reservation_id": str(alocacao.id),
        "status": "APPROVED",
    }
    
    # Fetch applicant for attendees
    applicant = db.query(Usuario).filter(Usuario.id == alocacao.fk_usuario).first()
    attendees = [applicant.email] if applicant and applicant.email else []

    events_list = create_event(
        db=db,
        user_id=current.id,
        summary=f"[{alocacao.tipo}] {alocacao.uso or f'Reserva Sala {room.codigo_sala or room.id}'}",
        description=alocacao.justificativa,
        start_dt_utc=start_dt,
        end_dt_utc=end_dt,
        location=room.descricao_sala,
        extended_private=extended_props,
        recurrence_rule=alocacao.recurrency,
        attendees=attendees
    )

    if not events_list:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Erro ao criar no Google ao aprovar.")

    try:
        alocacao.status = "APPROVED"
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar status local: {e}")

    return {"message": "Reserva aprovada e sincronizada com sucesso."}


@router.put("/{reservation_id}/reject", status_code=status.HTTP_200_OK)
def reject_reservation(reservation_id: int, db: Session = Depends(get_db), current=Depends(require_role(ROLE_ADMIN))):
    alocacao = db.query(Alocacao).filter(Alocacao.id == reservation_id).first()
    if not alocacao:
        raise HTTPException(status_code=404, detail="Reserva não encontrada.")

    try:
        alocacao.status = "REJECTED"
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao rejeitar: {e}")

    return {"message": "Reserva rejeitada."}


@router.put("/{reservation_id}")
def update_reservation(reservation_id: str, payload: ReservationUpdate, db: Session = Depends(get_db), current=Depends(require_role(ROLE_ADMIN))):
    old_google_event = get_event_by_id(db=db, user_id=current.id, event_id=reservation_id)
    alocacao_local = None

    if old_google_event:
        try:
            priv = (old_google_event.get("extendedProperties") or {}).get("private") or {}
            old_fk_sala = priv.get("fk_sala")
            old_start_str = old_google_event['start'].get('dateTime') or old_google_event['start'].get('date')

            if old_fk_sala and old_start_str:
                old_start_dt = to_storage_datetime(parser.parse(old_start_str))
                
                alocacao_local = db.query(Alocacao).filter(
                    Alocacao.fk_sala == old_fk_sala,
                    Alocacao.dia_horario_inicio == old_start_dt
                ).first()
        except Exception as e:
            print(f"Erro ao tentar localizar registro local para atualização: {e}")

    data = payload.model_dump(exclude_unset=True)
    patch = {}
    
    if "dia_horario_inicio" in data or "dia_horario_saida" in data or "fk_sala" in data or "uso" in data or "justificativa" in data:
        if data.get("dia_horario_inicio") and data.get("dia_horario_saida"):
            if data["dia_horario_saida"] <= data["dia_horario_inicio"]:
                raise HTTPException(status_code=400, detail="A data de saída deve ser posterior à data de início.")
        
        if "dia_horario_inicio" in data or "dia_horario_saida" in data:
            start_dt = data.get("dia_horario_inicio")
            end_dt = data.get("dia_horario_saida")
            
            if start_dt:
                patch["start"] = {"dateTime": ensure_utc(start_dt).isoformat(), "timeZone": "UTC"}
            
            if end_dt:
                patch["end"] = {"dateTime": ensure_utc(end_dt).isoformat(), "timeZone": "UTC"}

    if "uso" in data or "justificativa" in data:
        if "uso" in data:
            patch["summary"] = data["uso"]
        if "justificativa" in data:
            patch["description"] = data["justificativa"] or ""
            
    if "fk_sala" in data or "fk_usuario" in data or "tipo" in data or "uso" in data:
        priv = {}
        if "fk_sala" in data:
            priv["fk_sala"] = str(data["fk_sala"])
        if "fk_usuario" in data:
            priv["fk_usuario"] = str(data["fk_usuario"])
        if "tipo" in data:
            priv["tipo"] = str(data["tipo"])
        if "uso" in data:
            priv["uso"] = str(data["uso"])
        if "oficio" in data:
            priv["oficio"] = str(data["oficio"] or "")
        priv["platform_source"] = PLATFORM_EVENT_SOURCE
        
        if priv:
            patch["extendedProperties"] = {"private": priv}
            
    updated_evt = update_event(db=db, user_id=current.id, event_id=reservation_id, patch=patch)
    if updated_evt is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Erro ao atualizar no Google ou credenciais inválidas.")

    if alocacao_local:
        try:
            if payload.fk_sala:
                alocacao_local.fk_sala = payload.fk_sala
            if payload.fk_usuario:
                alocacao_local.fk_usuario = payload.fk_usuario
            if payload.tipo:
                alocacao_local.tipo = payload.tipo
            if payload.uso:
                alocacao_local.uso = payload.uso
            if payload.justificativa:
                alocacao_local.justificativa = payload.justificativa
            if payload.oficio:
                alocacao_local.oficio = payload.oficio
            
            if payload.dia_horario_inicio:
                alocacao_local.dia_horario_inicio = to_storage_datetime(payload.dia_horario_inicio)

            if payload.dia_horario_saida:
                alocacao_local.dia_horario_saida = to_storage_datetime(payload.dia_horario_saida)
            
            if payload.recurrency:
                alocacao_local.recurrency = payload.recurrency

            db.commit()
            print(f"Reserva local {alocacao_local.id} atualizada com sucesso.")
        
        except Exception as e:
            db.rollback()
            print(f"Erro ao atualizar banco local: {e}")
    else:
        print("Aviso: Reserva atualizada no Google, mas registro local correspondente não foi encontrado para atualização.")

    return updated_evt


@router.delete("/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_reservation(
    reservation_id: str, 
    delete_series: bool = Query(False),
    db: Session = Depends(get_db), 
    current=Depends(require_role(ROLE_ADMIN))
):
    # Se for deletar a série toda, precisamos identificar o evento pai se este for uma instância
    # No Google Calendar, instâncias tem 'recurringEventId'.
    # A API do Google delete aceita eventId. Se deletarmos o pai, deleta todos.
    # Se deletarmos a instância, deleta só ela.
    # Mas se o reservation_id for já uma instância e o usuario quiser deletar a serie,
    # precisamos achar o recurringEventId.

    google_event = get_event_by_id(db=db, user_id=current.id, event_id=reservation_id)
    
    target_id = reservation_id
    is_instance = False
    
    if google_event:
        if delete_series and google_event.get("recurringEventId"):
             target_id = google_event.get("recurringEventId")
             print(f"Redirecionando exclusão para a série (pai): {target_id}")
        elif delete_series and google_event.get("recurrence"):
             # Já é o pai
             pass
        else:
             # Exclusão simples (ou apenas esta ocorrência)
             pass

    # Deletar no Google
    # Se for deletar a série, usamos o target_id (que é o pai).
    # Se for deletar só a ocorrência, usamos o reservation_id original.
    
    id_to_delete = target_id if delete_series else reservation_id
    
    ok = delete_event(db=db, user_id=current.id, event_id=id_to_delete)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Erro ao excluir evento no Google ou credenciais inválidas.")

    # Sincronizar localmente
    # Se deletamos a série (target_id != reservation_id ou delete_series=True), 
    # precisamos deletar todas as alocações locais que tenham recurrency ou vínculo.
    # No nosso modelo local simples, não temos recurringEventId armazenado.
    # A sincronização 'perfeita' depende de termos o ID do google armazenado em cada linha.
    # Como não temos, fazemos uma limpeza 'best effort' baseada em dados.
    
    try:
        if google_event:
             priv = (google_event.get("extendedProperties") or {}).get("private") or {}
             fk_sala = priv.get("fk_sala")
             g_start = google_event['start'].get('dateTime') or google_event['start'].get('date')
             
             if delete_series:
                 # Se deletamos a série, tentamos achar eventos similares (mesma sala, mesmo usuario, mesma regra de recorrencia, etc)
                 # Isso é frágil sem o ID do google no banco.
                 # Por enquanto, vamos deletar a ocorrência específica que bate com o horário
                 # E se possível, logar que a consistência local de séries recorrentes é limitada.
                 print("Aviso: Exclusão de série no banco local pode ser incompleta sem ID de evento armazenado.")
             
             if fk_sala and g_start:
                dt_inicio_local = to_storage_datetime(parser.parse(g_start))
                
                # Tenta achar a alocação específica deste horário
                alocacao_local = db.query(Alocacao).filter(
                    Alocacao.fk_sala == fk_sala,
                    Alocacao.dia_horario_inicio == dt_inicio_local
                ).first()
                
                if alocacao_local:
                    db.delete(alocacao_local)
                    db.commit()
    except Exception as e:
        print(f"Erro na sincronização local de delete: {e}")
        db.rollback()

    return
