from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.try_database import get_db
from app.models import Usuario
from app.services.security import verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
	user = db.query(Usuario).filter(Usuario.email == form_data.username, Usuario.deleted_at.is_(None)).first()
	if not user or not verify_password(form_data.password, user.senha):
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
	access_token = create_access_token(subject=user.email, user_id=user.id, role=int(user.tipo_usuario or 1))
	return {"access_token": access_token, "token_type": "bearer"}

