import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db

security = HTTPBearer()


# --------------------------------------------------------------------------
# Passwords (usuarios - login)
# --------------------------------------------------------------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")


# ----------------------------------------------------------------------------
# Bcrypt dummy hash para timing-equalization
# ----------------------------------------------------------------------------
# Precomputamos UNA sola vez al importar el módulo un hash bcrypt de un
# password dummy. Cuando /auth/token recibe un username desconocido,
# invocamos `verify_password(password, DUMMY_BCRYPT_HASH)` igual que si
# el usuario existiera. Esto fuerza al servidor a correr bcrypt.checkpw
# en ambos casos → elimina el timing oracle que permitiría a un atacante
# enumerar usernames válidos midiendo latencia.
#
# Único uso: dentro de /auth/token, y siempre descartando el resultado.
# Nunca se compara contra nada real.
DUMMY_BCRYPT_HASH: str = get_password_hash("!dummy-timing-equalizer!")


def reset_password_dependencies() -> None:
    """Para tests: regenerar el dummy hash si fuera necesario (hoy no tiene
    estado mutable, pero dejamos el hook por simetría con rate_limit)."""
    global DUMMY_BCRYPT_HASH
    DUMMY_BCRYPT_HASH = get_password_hash("!dummy-timing-equalizer!")


# --------------------------------------------------------------------------
# JWT
# --------------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.access_token_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )
    return payload


# --------------------------------------------------------------------------
# Cifrado de passwords IMAP (Fernet)
# --------------------------------------------------------------------------
_cipher: Optional[Fernet] = None


def _get_cipher() -> Optional[Fernet]:
    """Inicializa Fernet perezosamente. Devuelve None si la clave es inválida
    (modo dev: hace fallback a texto plano; en producción se debe detectar y
    abortar el arranque)."""
    global _cipher
    if _cipher is None:
        key = (settings.fernet_key or "").encode()
        try:
            _cipher = Fernet(key)
        except (ValueError, TypeError) as e:
            print(f"⚠️ FERNET_KEY inválida ({e}). Las contraseñas IMAP no se cifrarán.")
            _cipher = None
    return _cipher


def validate_fernet_key(strict: bool = False) -> bool:
    """Verifica que la clave Fernet sea válida. Si `strict=True` (producción),
    lanza RuntimeError para detener el arranque."""
    try:
        Fernet((settings.fernet_key or "").encode())
        return True
    except Exception as e:
        if strict:
            raise RuntimeError(
                f"FERNET_KEY inválida o ausente. Generá una nueva con:\n"
                f"  python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
                f"Detalle: {e}"
            )
        print(f"⚠️  FERNET_KEY no válida ({e}). Modo dev: fallback a texto plano.")
        return False


def encrypt_password(plain: str) -> str:
    """Cifra una contraseña IMAP con Fernet. Si no hay clave válida, escribe
    el valor tal cual (modo dev únicamente)."""
    cipher = _get_cipher()
    if cipher is None or not plain:
        return plain
    return cipher.encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted: Optional[str]) -> str:
    """Descifra una contraseña IMAP. Si el valor no está en formato Fernet
    (legacy en texto plano), lo devuelve tal cual con una advertencia."""
    if not encrypted:
        return ""
    cipher = _get_cipher()
    if cipher is None:
        return encrypted
    try:
        return cipher.decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        # Legacy: passwords guardados en texto plano antes de este fix.
        return encrypted
