import jwt
import pytest
from fastapi.testclient import TestClient

from app import auth
from app.config import get_settings
from app.main import app
from tests.conftest import TEST_PASSWORD, TEST_USERNAME

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_throttle():
    auth._failures.clear()


def _login(password=TEST_PASSWORD, username=TEST_USERNAME):
    return client.post("/auth/login", json={"username": username, "password": password})


def test_endpoints_protegidos_sin_token():
    for path in ("/positions", "/transactions", "/portfolio/summary",
                 "/portfolio/history", "/auth/me"):
        assert client.get(path).status_code == 401, path


def test_health_es_publico():
    assert client.get("/health").status_code == 200


def test_login_correcto_y_acceso():
    r = _login()
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json() == {"username": TEST_USERNAME}


def test_login_incorrecto():
    assert _login(password="otra-clave").status_code == 401
    assert _login(username="otro").status_code == 401


def test_token_invalido_o_vencido():
    s = get_settings()
    bad = {"Authorization": "Bearer basura"}
    assert client.get("/auth/me", headers=bad).status_code == 401

    expired = jwt.encode({"sub": s.app_username, "exp": 1}, s.jwt_secret, algorithm="HS256")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401

    forged = jwt.encode({"sub": s.app_username, "exp": 9999999999}, "otra" * 12, algorithm="HS256")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_limite_de_intentos_fallidos():
    for _ in range(auth.MAX_FAILURES):
        assert _login(password="mal").status_code == 401
    assert _login(password="mal").status_code == 429
    # Bloqueado incluso con la contraseña correcta.
    assert _login().status_code == 429


def test_cors_permite_solo_el_origen_configurado():
    ok = client.options(
        "/positions",
        headers={"Origin": "http://localhost:3000",
                 "Access-Control-Request-Method": "GET",
                 "Access-Control-Request-Headers": "authorization"},
    )
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    bad = client.options(
        "/positions",
        headers={"Origin": "http://evil.example",
                 "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in bad.headers
