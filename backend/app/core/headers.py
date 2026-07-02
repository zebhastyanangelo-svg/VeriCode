"""
Cache-Control + ETag helpers para endpoints HTTP.

Decisión de diseño: NO usamos `ETag` con hash del body. Usamos `ETag` con
la versión lógica del namespace (derivada de `core.cache.current_version`).
Eso permite que el navegador haga conditional GETs (`If-None-Match`) y
ahorre el body completo, mientras que un POST/PUT/DELETE simplemente
bumpea la versión → ETag nuevo → 200 (no 304).
"""
from __future__ import annotations

from fastapi import Response

from app.core import cache as _cache


def cache_control_headers(
    response: Response,
    *,
    max_age_seconds: int,
    private: bool = True,
) -> None:
    """Setea `Cache-Control` en la response in-place."""
    scope = "private" if private else "public"
    response.headers["Cache-Control"] = f"{scope}, max-age={max_age_seconds}"


def etag_for_namespace(namespace: str) -> str:
    """Genera un ETag estable basado en la versión del namespace del cache.

    Validación: el namespace NO puede contener `:` porque es nuestro
    separador de keys compuestas (`ns:vN:suffix`). Pasarlo con `:`
    generaría keys ambiguas al cruzar con `bump_version(ns_completa)`.
    """
    if ":" in namespace:
        raise ValueError(
            f"Namespace no puede contener ':' (separador reservado): {namespace!r}"
        )
    version = _cache.current_version(namespace)
    return f'W/"{namespace}.v{version}"'


def etag_headers(response: Response, namespace: str) -> str:
    """Setea `ETag` header + devuelve el valor para que el handler pueda
    compararlo con `If-None-Match` del request.

    IMPORTANTE: el handler DEBE copiar los headers al Response 304 que
    devuelva (no basta con haberlos seteado antes sobre `response`,
    porque FastAPI usa el Response del `return` para enviar al cliente).
    """
    etag = etag_for_namespace(namespace)
    response.headers["ETag"] = etag
    return etag
