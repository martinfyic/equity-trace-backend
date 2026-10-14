import bcrypt
import pytest

from app.config import database_url, get_settings

GOOD_HASH = bcrypt.hashpw(b"clave-de-prueba-123", bcrypt.gensalt(rounds=4)).decode()


@pytest.fixture(autouse=True)
def fresh_settings(monkeypatch):
    """Cada test arranca con una configuración válida y sin caché."""
    monkeypatch.setenv("APP_USERNAME", "admin")
    monkeypatch.setenv("APP_PASSWORD_HASH", GOOD_HASH)
    monkeypatch.setenv("JWT_SECRET", "x" * 48)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_configuracion_valida():
    s = get_settings()
    assert s.app_username == "admin"
    assert s.app_password_hash == GOOD_HASH


def test_hash_con_comillas_da_un_error_claro(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH", f"'{GOOD_HASH}'")
    with pytest.raises(RuntimeError, match="quitalas"):
        get_settings()


def test_texto_que_no_es_un_hash(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD_HASH", "mi-contraseña")
    with pytest.raises(RuntimeError, match="no parece un hash bcrypt"):
        get_settings()


@pytest.mark.parametrize("name", ["APP_USERNAME", "APP_PASSWORD_HASH", "JWT_SECRET"])
def test_falta_una_variable_obligatoria(monkeypatch, name):
    monkeypatch.delenv(name)
    with pytest.raises(RuntimeError, match=name):
        get_settings()


def test_jwt_secret_corto(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "corto")
    with pytest.raises(RuntimeError, match="32 caracteres"):
        get_settings()


def test_url_de_neon_se_adapta_al_driver(monkeypatch):
    neon = "postgresql://u:p@ep-x.us-east-2.aws.neon.tech/db?sslmode=require&channel_binding=require"
    monkeypatch.setenv("DATABASE_URL", neon)
    assert database_url().startswith("postgresql+psycopg://u:p@ep-x.")
    assert database_url().endswith("?sslmode=require&channel_binding=require")
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h/db")
    assert database_url() == "postgresql+psycopg://u:p@h/db"
