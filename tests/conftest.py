"""Variables de entorno de prueba: se fijan ANTES de importar la app."""
import os

import bcrypt

TEST_USERNAME = "tester"
TEST_PASSWORD = "clave-de-prueba-123"

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["APP_USERNAME"] = TEST_USERNAME
os.environ["APP_PASSWORD_HASH"] = bcrypt.hashpw(
    TEST_PASSWORD.encode(), bcrypt.gensalt(rounds=4)
).decode()
os.environ["JWT_SECRET"] = "x" * 48
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
