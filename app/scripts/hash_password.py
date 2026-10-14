"""Genera el hash bcrypt para APP_PASSWORD_HASH.

Uso:  python -m app.scripts.hash_password
"""
import getpass

import bcrypt


def main() -> None:
    pw = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
    if len(pw) < 12:
        raise SystemExit("Muy corta: usá al menos 12 caracteres.")
    if len(pw.encode()) > 72:
        raise SystemExit("bcrypt admite hasta 72 bytes.")
    if pw != getpass.getpass("Repetí la contraseña: "):
        raise SystemExit("Las contraseñas no coinciden.")
    print(bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode())


if __name__ == "__main__":
    main()
