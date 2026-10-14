from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import auth
from app.config import get_settings
from app.routers import history, positions, transactions

settings = get_settings()  # falla al arrancar si falta configuración

app = FastAPI(title="Portfolio Tracker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


app.include_router(auth.router)

protected = [Depends(auth.require_auth)]
app.include_router(transactions.router, dependencies=protected)
app.include_router(positions.router, dependencies=protected)
app.include_router(history.router, dependencies=protected)
