"""
Dependencies reutilizables para routers protegidos.

- `client_ip(request)`: resuelve la IP del cliente respetando `trusted_proxies`
  de la configuración. Si el socket del request NO está en la lista de proxies
  confiables, cualquier header X-Forwarded-For / X-Real-IP / CF-Connecting-IP
  se IGNORA → cierra el hueco de rate-limit bypassable.

- `require_no_password_change`: dependency que rechaza con 403 cualquier
  request cuya auth JWT siga perteneciendo a un usuario con
  `must_change_password=True` en BD. Defense-in-depth: aunque el frontend
  bloquee UI, una JWT robada NO puede alcanzar endpoints sensibles hasta
  que el usuario cambie la contraseña.

  Exentos (no se les aplica):
    - /auth/me                    → el frontend necesita leer el flag
    - /auth/change-password       → requerido para limpiar el flag
    - /auth/setup                 → bootstrap inicial
    - /public/*                   → no requieren JWT por diseño
    - WebSocket /codes/ws         → valida aparte en su handler

- `validate_websocket_auth`: helper para validación completa del WS
  (token + must_change_password). Devuelve (payload_dict_or_none, error_dict).
  El handler WS decide si aceptar o cerrar con el error.
"""
from __future__ import annotations

import asyncio
from ipaddress import IPv4Network, IPv6Network, ip_address
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.auth import security, verify_token
from app.config import settings
from app.db.database import get_db
from app.models import User
from sqlalchemy.orm import Session


# --------------------------------------------------------------------------
# Trusted proxies / IP de cliente
# --------------------------------------------------------------------------
def _parse_trusted_proxies(raw: str) -> tuple[set[str], list, bool]:
    """Devuelve (set_ips, lista_networks, trust_all).

    Formatos aceptados en `settings.trusted_proxies`:
    - "" → (set(), [], False)            → deshabilitado (default dev)
    - "*" → (set(), [], True)            → confiar en cualquier header
    - "127.0.0.1,10.0.0.5"               → exact-IP match
    - "10.0.0.0/8,172.16.0.0/12"         → CIDR networks
    """
    raw = (raw or "").strip()
    if not raw:
        return set(), [], False
    if raw == "*":
        return set(), [], True
    ips: set[str] = set()
    nets: list = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        if "/" in token:
            try:
                nets.append(IPv4Network(token, strict=False))
            except ValueError:
                try:
                    nets.append(IPv6Network(token, strict=False))
                except ValueError:
                    # Silencioso: tokens inválidos se ignoran (defensive: no
                    # romper el arranque por una CIDR mal escrita).
                    continue
        else:
            ips.add(token)
    return ips, nets, False


_TRUSTED_IPS, _TRUSTED_NETS, _TRUST_ALL = _parse_trusted_proxies(settings.trusted_proxies)


def _ip_is_trusted(ip_str: str) -> bool:
    """Devuelve True si `ip_str` representa un proxy confiable."""
    if _TRUST_ALL:
        return True
    if ip_str in _TRUSTED_IPS:
        return True
    try:
        ip = ip_address(ip_str)
    except ValueError:
        return False
    return any(ip in n for n in _TRUSTED_NETS)


def client_ip(request: Request) -> str:
    """Devuelve la IP efectiva del cliente.

    Lógica:
      1. Si `request.client.host` está en la lista de proxies confiables
         → leer el header configurado en `real_ip_header` (default X-Forwarded-For)
            y devolver la primera IP (cliente original).
      2. En caso contrario → devuelve `request.client.host`,
         IGNORANDO cualquier header que el cliente haya puesto.

    Esto previene que un atacante en dev (sin proxy) inyecte
    `X-Forwarded-For: 1.2.3.4` para evadir el rate-limit.
    """
    socket_ip = request.client.host if request.client else "unknown"
    if not _ip_is_trusted(socket_ip):
        return socket_ip
    header_name = settings.real_ip_header
    forwarded = request.headers.get(header_name)
    if not forwarded:
        return socket_ip
    # X-Forwarded-For es una lista "client, proxy1, proxy2"; otros headers
    # pueden venir solos. Tomamos la primera IP parseable.
    for candidate in forwarded.split(","):
        candidate = candidate.strip()
        try:
            # validate: descartar strings que no son IPs (algunos proxies
            # meten hostname en este header).
            ip_address(candidate)
            return candidate
        except ValueError:
            continue
    # Si ninguna IP parseó, caer al socket (defensive fallback).
    return socket_ip


# --------------------------------------------------------------------------
# Enforce: must_change_password = False para endpoints sensibles
# --------------------------------------------------------------------------
async def require_no_password_change(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """Devuelve el payload JWT SOLO si el user autenticado tiene
    `must_change_password=False` en BD. En otro caso devuelve 403.

    Pensado para aplicar via `dependencies=[Depends(require_no_password_change)]`
    en routers protegidos (codes, email-accounts, platforms).
    NO debe usarse en routers que proveen el cambio (/auth/change-password)
    ni en /auth/me (necesario para leer el flag).
    """
    payload = verify_token(credentials.credentials)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    def _query():
        return (
            db.query(User)
            .filter(User.username == payload.get("sub"))
            .first()
        )
    user = await asyncio.to_thread(_query)
    if user is None or user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Cambio de contraseña obligatorio antes de usar el panel. "
                "Visitá /auth/change-password."
            ),
        )
    return payload


# --------------------------------------------------------------------------
# Validación compuesta para WebSocket
# --------------------------------------------------------------------------
async def validate_websocket_auth(
    token: Optional[str],
    db: Session,
) -> tuple[Optional[dict], Optional[dict]]:
    """Valida un WS handshake.

    Devuelve (payload, None) si todo OK,
    o (None, {"detail": ..., "code": 4401|4403}) si hay error.
    El caller decide si hacer accept() antes de cerrar (para mandar el
    mensaje JSON explicativo) o rechazar en el handshake.
    """
    if not token:
        return None, {"detail": "Token requerido", "code": 4401}
    payload = verify_token(token)
    if payload is None:
        return None, {"detail": "Token inválido o expirado", "code": 4401}
    def _query():
        return (
            db.query(User)
            .filter(User.username == payload.get("sub"))
            .first()
        )
    user = await asyncio.to_thread(_query)
    if user is None or user.must_change_password:
        return None, {
            "detail": "Cambio de contraseña obligatorio. Llamá /auth/change-password.",
            "code": 4403,  # 4403 = forbidden (custom range, no choca con HTTP)
        }
    return payload, None
