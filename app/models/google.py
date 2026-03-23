from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.try_database import Base


class GoogleCredential(Base):
	__tablename__ = "google_credentials"
	id = Column(Integer, primary_key=True, index=True)
	user_id = Column(Integer, index=True, unique=True)
	access_token = Column(String(2048))
	refresh_token = Column(String(2048))
	client_id = Column(String(255))
	client_secret = Column(String(255))
	scopes = Column(String(1024))
	expiry = Column(DateTime(timezone=True), nullable=True)
	updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


