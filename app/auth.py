"""Login de usuario único (credenciales en variables de entorno) con JWT."""
import hmac
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from app.config import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60
_failures: dict[str, list[float]] = {}  # limitador simple, en memoria


class LoginIn(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=200)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # segundos


class MeOut(BaseModel):
    username: str


def _recent_failures(key: str) -> list[float]:
    now = time.time()
    recent = [t for t in _failures.get(key, []) if now - t < WINDOW_SECONDS]
    _failures[key] = recent
    return recent


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, request: Request):
    s = get_settings()
    key = request.client.host if request.client else "unknown"

    if len(_recent_failures(key)) >= MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Probá de nuevo en unos minutos.",
        )

    # Se verifican siempre ambas cosas, para no revelar cuál falló.
    user_ok = hmac.compare_digest(data.username.encode(), s.app_username.encode())
    try:
        pass_ok = bcrypt.checkpw(data.password.encode(), s.app_password_hash.encode())
    except ValueError:
        pass_ok = False

    if not (user_ok and pass_ok):
        _failures.setdefault(key, []).append(time.time())
        raise _unauthorized("Usuario o contraseña incorrectos")

    _failures.pop(key, None)
    expires = timedelta(minutes=s.access_token_minutes)
    token = jwt.encode(
        {"sub": s.app_username, "exp": datetime.now(timezone.utc) + expires},
        s.jwt_secret,
        algorithm=ALGORITHM,
    )
    return TokenOut(access_token=token, expires_in=int(expires.total_seconds()))


def require_auth(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    if creds is None:
        raise _unauthorized("No autenticado")
    s = get_settings()
    try:
        payload = jwt.decode(
            creds.credentials, s.jwt_secret, algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        raise _unauthorized("Token inválido o vencido")
    if payload.get("sub") != s.app_username:
        raise _unauthorized("Token inválido")
    return payload["sub"]


@router.get("/me", response_model=MeOut)
def me(username: str = Depends(require_auth)):
    return MeOut(username=username)
