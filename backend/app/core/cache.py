"""
TTL cache in-process para lecturas caras (e.g. /codes/stats, /platforms).

Diseñado para **una sola instancia uvicorn** (`--workers 1`). NO usar con
múltiples workers (cada proceso tendría su propio cache y el cliente
recibiría respuestas inconsistentes según qué worker despache). Esta
limitación ya está documentada en `docs/07-DEPLOY.md` §5 (single-instance).

Decisiones de diseño (basadas en feedback del thinker pre-implementación):

1) **Sin `threading.Lock` en endpoints `def`.**
   FastAPI ejecuta handlers `def` (sync) en el threadpool de Starlette
   (cap ~40 threads). Un lock tradicional bloquearía esos hilos — si la
   BD se enlentece, todas las requests `def` se quedan esperando, incluso
   las que no usan el cache. En su lugar usamos "stale-while-revalidate"
   con flag `_pending`: si el cache está expirado y otro thread ya está
   refetcheando, devolvemos el valor viejo inmediatamente y el resto
   se va rápido. Limitación documentada: best-effort NO garantiza
   single-flight estricto bajo concurrencia extrema (§8.3 de 08-CACHING).

2) **Version-keyed invalidation.**
   Cada namespace tiene un `_versions[ns]` entero que se incluye en la
   key. Bumpear la versión invalida el cache **al instante sin recorrer
   keys**. Las keys viejas quedan en el dict hasta el eviction
   oportunista (ver `_CACHE_HARD_CAP`).

3) **TTL configurable por namespace.**

4) **Cap superior + eviction oportunista con headroom 75%.**
   `_CACHE_HARD_CAP` (8192 entries, ~8MB) protege contra crecimiento
   ilimitado en procesos de larga duración. Cuando se excede, primero
   purgamos las entradas cuyo TTL venció; si todavía excede, bajamos a
   `_CACHE_HARD_CAP * 3/4` (75%) tirando las más viejas por timestamp.
   El 75% de headroom amortigua el siguiente cache-miss sin entrar en
   oscilación de borde (post-compute `len ≈ 0.75*cap + 1 < cap`).
   Trade-off conocido: bajo carga sostenida el sort+delete corre bajo
   el `_lock` global — follow-up sería mover el batch fuera del lock
   (ver docs/08-CACHING §8).

5) **No ETag con hash del body.**
   El thinker explicó que un ETag para `/codes` paginado es incorrecto
   (las mutaciones `is_delivered` no cambian `row_count` ni
   `max(received_at)`). Solo usamos `Cache-Control: private, max-age=N`
   + invalidación por versión + ETag derivado de la versión del
   namespace (para 304 conditional GET).
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, TypeVar

T = TypeVar("T")

# ── Namespaces públicos ────────────────────────────────────────────────────
# Usar SIEMPRE estas constantes — un namespace mal escrito significa que
# la invalidación desde el handler de mutación no afecta al cache del
# handler de lectura, y el cache queda stale hasta el TTL.
NS_PLATFORMS = "platforms"
NS_EMAIL_ACCOUNTS = "email_accounts"
NS_CODES_STATS = "codes_stats"

# Cap superior para proteger el proceso contra crecimiento ilimitado del
# dict. Cada entry ~1KB; 8192 entries = ~8MB.
_CACHE_HARD_CAP = 8192

# Headroom post-eviction: dejar 75% del cap (3/4) para amortiguar el
# siguiente cache-miss sin entrar en oscilación de borde. Sin esto, la
# secuencia miss → eviction `len-cap` → compute+1 deja len == cap+1 y el
# próximo miss vuelve a pagar el sort+delete.
_HEADROOM_RATIO_NUM = 3
_HEADROOM_RATIO_DEN = 4

# Estado del módulo. `_cache[full_key] = (expires_at_monotonic, value)`.
# El read se evalúa sin lock (dict.get es atómico bajo GIL). El write
# toma el lock sólo para evitar race en la estructura.
_cache: dict[str, tuple[float, Any]] = {}
_versions: dict[str, int] = {}
_pending: dict[str, bool] = {}  # ns:refetch-in-flight flag (best-effort)
_lock = threading.Lock()


def _now() -> float:
    return time.monotonic()


def bump_version(namespace: str) -> None:
    """Invalida todas las entradas del namespace. Llamar en POST/PUT/DELETE.

    Es seguro llamarlo desde CUALQUIER router sobre el mismo namespace:
    el admin endpoint que muta una plataforma invalida tanto su propio
    cache privado (admin) como el cache público (`/public/platforms`),
    porque ambos usan `NS_PLATFORMS`.

    Validación: el namespace NO puede contener ':' (reservado como
    separador de keys compuestas en `_make_key`). Si alguien pasa
    `"platforms:active"`, levantamos ValueError para evitar confusión
    con `_make_key(NS_PLATFORMS, "active")` que internamente sigue
    leyendo `_versions["platforms"]`.
    """
    if ":" in namespace:
        raise ValueError(
            f"Namespace no puede contener ':' (separador reservado): "
            f"{namespace!r}. Usá el namespace base (e.g. NS_PLATFORMS) "
            f"y pasá los sufijos como argumentos a get_or_compute."
        )
    with _lock:
        _versions[namespace] = _versions.get(namespace, 0) + 1


def current_version(namespace: str) -> int:
    return _versions.get(namespace, 0)


def _make_key(namespace: str, *parts: Any) -> str:
    version = current_version(namespace)
    suffix = ":".join(str(p) for p in parts)
    return f"{namespace}:v{version}:{suffix}" if suffix else f"{namespace}:v{version}"


def _evict_expired_locked() -> int:
    """Pasa de limpieza: borra entries cuyo TTL venció (`exp < now`).
    Caller debe tener lock.

    No es una eviction estricta LRU (no trackeamos accesos), pero
    garantiza que un proceso de larga duración no se vaya a OOM.
    Devuelve la cantidad de entries purgadas (útil para logging).

    NB: usamos `exp < now` (estricta) en vez de `<=` para no purgar
    entries recién guardadas que expiren en el mismo tick de
    `time.monotonic()`. Documentado en 08-CACHING §8.
    """
    now = _now()
    expired = [k for k, (exp, _) in _cache.items() if exp < now]
    for k in expired:
        del _cache[k]
    return len(expired)


def get_or_compute(
    namespace: str,
    ttl_seconds: float,
    compute_fn: Callable[[], T],
    key_parts: tuple[Any, ...] = (),
) -> T:
    """
    Devuelve el valor cacheado si está vivo; si no, llama `compute_fn()` y
    guarda el resultado por `ttl_seconds`.

    `key_parts` es una tupla (no `*args`) para que el call site pueda
    pasarla como keyword (`key_parts=("active",)`) sin necesidad de
    mantener todas las args posicionales. Esto evita el SyntaxError de
    mezcla posicional/keyword en llamadas que usen namespace + ttl +
    compute + key.

    Stale-while-revalidate (sin lock pesado en el read):
    - Si existe y no venció → return cached (lock-free).
    - Si venció y NO hay refetch en flight → marca `_pending[ns]=True`,
      ejecuta `compute_fn()`, cachea, desmarca, return fresh.
    - Si venció y SÍ hay refetch en flight → return el valor viejo
      vigente (si existe) y nos vamos rápido.

    Caveat: el flag `_pending` es best-effort. Bajo concurrencia extrema,
    dos requests pueden leer `_pending[ns]==False` antes de que cualquiera
    lo setee, y ambos ejecutan `compute_fn()`. Benign (mismo valor),
    pero gasta un SELECT extra. Trade-off documentado en 08-CACHING §8.3.

    Eviction: cuando `len(_cache) > _CACHE_HARD_CAP` durante este
    `get_or_compute`, purgamos entradas vencidas, y si aún excede
    aplicamos el fallback con headroom 75% (ver `_HEADROOM_RATIO_*`).
    """
    if ttl_seconds <= 0:
        # TTL = 0 = cache deshabilitado. Útil para tests o para apagar
        # temporalmente sin tocar las llamadas.
        return compute_fn()

    if ":" in namespace:
        raise ValueError(
            f"Namespace no puede contener ':' (separador reservado): {namespace!r}"
        )

    key = _make_key(namespace, *key_parts)
    now = _now()

    # Camino rápido (lock-free). Si está vivo, lo devolvemos tal cual.
    entry = _cache.get(key)
    if entry is not None and entry[0] > now:
        return entry[1]

    # ¿Hay un refetch en flight? Si sí, devolvemos el valor viejo.
    if _pending.get(namespace):
        if entry is not None:
            return entry[1]
        # No hay valor viejo y alguien está refetcheando: ejecutar compute.
        value = compute_fn()
        with _lock:
            _cache[key] = (now + ttl_seconds, value)
        return value

    # Tomamos el flag de pending bajo lock + eviction oportunista.
    with _lock:
        # Re-chequeo locked: por si alguien escribió mientras esperábamos.
        current = _cache.get(key)
        if current is not None and current[0] > now:
            return current[1]
        _pending[namespace] = True
        # Eviction oportunista cuando se pasa el cap.
        if len(_cache) > _CACHE_HARD_CAP:
            purged = _evict_expired_locked()
            if purged == 0 and len(_cache) > _CACHE_HARD_CAP:
                # Sin entries vencidas para purgar y aún en cap: tirar las
                # más viejas por timestamp hasta dejar 75% del cap.
                # Esto amortigua el siguiente miss sin entrar en
                # oscilación de borde: post-compute len queda
                # claramente < cap. Determinista y testeable.
                headroom_target = (
                    _CACHE_HARD_CAP * _HEADROOM_RATIO_NUM // _HEADROOM_RATIO_DEN
                )
                if len(_cache) > headroom_target:
                    to_drop = len(_cache) - headroom_target
                    oldest = sorted(
                        _cache.items(), key=lambda kv: kv[1][0]
                    )[:to_drop]
                    for k, _ in oldest:
                        del _cache[k]

    try:
        value = compute_fn()
    except Exception:
        with _lock:
            _pending[namespace] = False
        raise
    with _lock:
        _pending[namespace] = False
        _cache[key] = (now + ttl_seconds, value)

    return value


def clear_all() -> None:
    """Útil para tests: limpia cache + versiones."""
    with _lock:
        _cache.clear()
        _versions.clear()
        _pending.clear()


def stats_snapshot() -> dict[str, Any]:
    """Snapshot del estado para debugging / banner."""
    with _lock:
        return {
            "entries": len(_cache),
            "versions": dict(_versions),
            "pending": [k for k, v in _pending.items() if v],
        }
