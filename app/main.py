from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from app.config import get_settings
from app.try_database import Base, engine
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, users, rooms, reservations, calendar, google, room_types

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine, checkfirst=True)
    yield

settings = get_settings()
app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
origins = [
    "http://localhost:3000",  
    "http://localhost:5173",  
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="https?://.*",  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key=settings.JWT_SECRET)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(rooms.router)
app.include_router(room_types.router)
app.include_router(reservations.router)
app.include_router(calendar.router)
app.include_router(google.router)

@app.get("/health")
def health():
	return {"status": "ok"}


