"""Configuración desde variables de entorno (y .env en desarrollo)."""
import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()  # no pisa variables ya definidas en el entorno


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "sqlite:///./portfolio.db")
    # Muchos hostings entregan "postgres://..." o "postgresql://...";
    # SQLAlchemy necesita indicar el driver (psycopg 3).
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@dataclass(frozen=True)
class Settings:
    app_username: str
    app_password_hash: str
    jwt_secret: str
    access_token_minutes: int
    cors_origins: list[str]


@lru_cache
def get_settings() -> Settings:
    missing = [
        name
        for name in ("APP_USERNAME", "APP_PASSWORD_HASH", "JWT_SECRET")
        if not os.environ.get(name)
    ]
    if missing:
        raise RuntimeError(
            "Faltan variables de entorno: " + ", ".join(missing)
            + ". Revisá .env.example."
        )
    secret = os.environ["JWT_SECRET"]
    if len(secret) < 32:
        raise RuntimeError("JWT_SECRET debe tener al menos 32 caracteres.")
    password_hash = os.environ["APP_PASSWORD_HASH"]
    if not password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        raise RuntimeError(
            "APP_PASSWORD_HASH no parece un hash bcrypt (debe empezar con $2b$). "
            "Si lo pegaste con comillas, quitalas: en el panel del hosting el valor "
            "se toma tal cual. Generalo con: python -m app.scripts.hash_password"
        )
    origins = [
        o.strip()
        for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
        if o.strip()
    ]
    return Settings(
        app_username=os.environ["APP_USERNAME"],
        app_password_hash=password_hash,
        jwt_secret=secret,
        access_token_minutes=int(os.environ.get("ACCESS_TOKEN_MINUTES", "1440")),
        cors_origins=origins,
    )
