from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import auth
from app.db import Base, get_db
from app.main import app
from app.services import prices
from tests.conftest import TEST_PASSWORD, TEST_USERNAME


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    def override():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override
    monkeypatch.setattr(prices, "get_price", lambda t: Decimal("700"))
    auth._failures.clear()
    c = TestClient(app)
    token = c.post(
        "/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    ).json()["access_token"]
    c.headers["Authorization"] = f"Bearer {token}"
    yield c
    app.dependency_overrides.clear()


BUY1 = {"ticker": "msft", "type": "BUY", "date": "2025-09-26",
        "quantity": "0.036566", "price": "508.94", "fee": "1.39"}
BUY2 = {"ticker": "MSFT", "type": "BUY", "date": "2025-10-09",
        "quantity": "0.094106", "price": "719.72", "fee": "2.35"}


def test_flujo_completo(client):
    assert client.post("/transactions", json=BUY1).status_code == 201
    assert client.post("/transactions", json=BUY2).status_code == 201

    pos = client.get("/positions").json()
    assert len(pos) == 1
    assert pos[0]["ticker"] == "MSFT"
    assert Decimal(pos[0]["quantity"]) == Decimal("0.130672")
    assert Decimal(pos[0]["total_cost"]) == Decimal("90.08")
    assert Decimal(pos[0]["avg_cost"]) == Decimal("689.3586")
    assert Decimal(pos[0]["market_value"]) == Decimal("91.47")

    summary = client.get("/portfolio/summary").json()
    assert Decimal(summary["unrealized_pnl"]) == Decimal("1.39")


def test_rechaza_venta_excesiva(client):
    client.post("/transactions", json=BUY1)
    sell = {**BUY1, "type": "SELL", "quantity": "5", "fee": "0"}
    assert client.post("/transactions", json=sell).status_code == 422


def test_no_permite_borrar_compra_si_invalida_una_venta(client):
    tx_id = client.post("/transactions", json=BUY1).json()["id"]
    sell = {**BUY1, "type": "SELL", "quantity": "0.01", "fee": "0", "date": "2025-10-01"}
    assert client.post("/transactions", json=sell).status_code == 201
    assert client.delete(f"/transactions/{tx_id}").status_code == 422


def test_validaciones_de_entrada(client):
    assert client.post("/transactions", json={**BUY1, "quantity": "0"}).status_code == 422
    assert client.post("/transactions", json={**BUY1, "date": "2999-01-01"}).status_code == 422


def test_endpoint_historial(client, monkeypatch):
    client.post("/transactions", json=BUY1)
    client.post("/transactions", json=BUY2)
    monkeypatch.setattr(
        prices, "get_history",
        lambda t, s, e: {__import__("datetime").date(2025, 10, 9): Decimal("700")},
    )
    r = client.get("/portfolio/history", params={"date_to": "2025-10-10"})
    assert r.status_code == 200
    pts = r.json()
    assert pts[0]["date"] == "2025-09-26"
    assert pts[-1]["date"] == "2025-10-10"
    assert Decimal(pts[-1]["market_value"]) == Decimal("91.47")


def test_historial_vacio_y_rango_invalido(client):
    assert client.get("/portfolio/history").json() == []
    client.post("/transactions", json=BUY1)
    r = client.get("/portfolio/history", params={"date_from": "2025-12-01", "date_to": "2025-11-01"})
    assert r.status_code == 422


def test_filtros_de_listado(client):
    client.post("/transactions", json=BUY1)
    client.post("/transactions", json=BUY2)
    client.post("/transactions", json={**BUY1, "ticker": "AAPL", "date": "2025-10-01"})

    assert len(client.get("/transactions").json()) == 3
    assert len(client.get("/transactions", params={"ticker": "msft"}).json()) == 2
    r = client.get("/transactions", params={"date_from": "2025-10-01", "date_to": "2025-10-05"})
    assert [t["ticker"] for t in r.json()] == ["AAPL"]
    # Orden cronológico
    fechas = [t["date"] for t in client.get("/transactions").json()]
    assert fechas == sorted(fechas)


def test_filtro_con_fecha_invalida_se_rechaza(client):
    assert client.get("/transactions", params={"date_from": "basura"}).status_code == 422


def test_editar_borrar_y_404(client):
    tx_id = client.post("/transactions", json=BUY1).json()["id"]
    upd = {k: v for k, v in BUY1.items() if k != "ticker"} | {"fee": "2.00"}
    assert client.put(f"/transactions/{tx_id}", json=upd).json()["fee"] == "2.00"
    assert client.put("/transactions/999", json=upd).status_code == 404
    assert client.delete(f"/transactions/{tx_id}").status_code == 204
    assert client.delete(f"/transactions/{tx_id}").status_code == 404


def test_posiciones_cerradas_y_404(client):
    client.post("/transactions", json=BUY1)
    sell = {**BUY1, "type": "SELL", "fee": "0", "price": "600", "date": "2025-10-01"}
    assert client.post("/transactions", json=sell).status_code == 201
    assert client.get("/positions").json() == []                       # cerradas ocultas
    closed = client.get("/positions", params={"include_closed": "true"}).json()
    assert Decimal(closed[0]["quantity"]) == 0
    assert Decimal(closed[0]["realized_pnl"]) > 0
    assert client.get("/positions/NOPE").status_code == 404
