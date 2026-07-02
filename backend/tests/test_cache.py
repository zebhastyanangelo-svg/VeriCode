#!/usr/bin/env python3
"""Unit tests para `app.core.cache` — TTL cache in-process con SWR sin lock.

Cubre las 5 áreas críticas del módulo:

1. **Anotación por namespace (version-keyed invalidation)** —
   `bump_version` incrementa el contador del namespace; `get_or_compute`
   con la misma key después del bump crea una key nueva con la versión
   bumpeada, descartando el valor anterior al instante sin recorrer
   keys (memory queda hasta el eviction oportunista).

2. **`bump_version()` increments y tolerancia** — múltiples bumps acumulan
   correctamente; sin bumps, `current_version == 0`.

3. **SWR (stale-while-revalidate) sin lock** — pre-poblar `_pending[ns]=True`
   con entry expirado en cache: el handler devuelve el valor viejo sin
   ejecutar `compute_fn`. Diferencia con `compute_fn` corriendo: ver el
   contador de calls.

4. **`_CACHE_HARD_CAP` eviction oportunista** — reuce `_CACHE_HARD_CAP`
   a un valor chico con `monkeypatch`, poblar entries hasta exceder el
   cap, verificar que entradas vencidas se purgan.

5. **`ValueError` en namespace con ":"** — tanto `bump_version` como
   `get_or_compute` deben raise si el namespace contiene ":" (reservado
   como separador de keys compuestas). Verifica el footgun documentado.

Cobertura adicional:
- `get_or_compute` reutiliza mismo value mientras TTL alive
- `get_or_compute` con `ttl_seconds=0` siempre recomputa
- `current_version` default 0
- `clear_all` resetea todo
- `key_parts` produce keys separadas (no colisionan entre si)
- Cross-router namespace sharing: bump en NS_PLATFORMS invalida tanto
  admin como público (`key_parts=("active",)`)

Standalone runner (sin pytest). Cada test se asegura de empezar con
`clear_all()` para aislar estado entre tests.

Run:
    cd backend
    python tests/test_cache.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def _reset_state() -> None:
    """Limpia cache + versions + pending. Llamar al inicio de cada test."""
    from app.core import cache
    cache.clear_all()


# ──────────────────────────────────────────────────────────────────────────
# 1) Anotación por namespace (version-keyed invalidation)
# ──────────────────────────────────────────────────────────────────────────
def test_version_keyed_invalidation_displaces_previous_value() -> None:
    """get_or_compute tras bump crea nueva key con versión incrementada;
    el viejo valor queda en el dict pero NO es alcanzable por
    get_or_compute (que ya construye key con v{N+1})."""
    _reset_state()
    from app.core import cache

    calls = []

    def compute_v1():
        calls.append("v1")
        return "value-at-version-0"

    def compute_v2():
        calls.append("v2")
        return "value-at-version-1"

    # Versión 0: cachea "value-at-version-0"
    v0 = cache.get_or_compute("test_ns", ttl_seconds=60, compute_fn=compute_v1)
    assert v0 == "value-at-version-0", f"v0 esperado 'value-at-version-0', obtuve {v0!r}"
    assert calls == ["v1"], f"compute_v1 debió correr 1 vez, calls={calls}"
    assert cache.current_version("test_ns") == 0

    # Bump invalida lógicamente (próxima GET construye key con v1)
    cache.bump_version("test_ns")
    assert cache.current_version("test_ns") == 1

    # Segunda llamada: nuevo compute_fn corre porque la key cambió
    v1 = cache.get_or_compute("test_ns", ttl_seconds=60, compute_fn=compute_v2)
    assert v1 == "value-at-version-1", f"v1 esperado 'value-at-version-1', obtuve {v1!r}"
    assert calls == ["v1", "v2"], (
        f"Ambas versiones debieron computarse exactamente una vez: {calls}"
    )

    # El dict ahora tiene 2 keys: v0 y v1 (memory hasta eviction oportunista)
    snap = cache.stats_snapshot()
    assert snap["entries"] >= 2, (
        f"Esperaba ≥2 entries (v0 + v1), obtuve {snap['entries']}: {snap}"
    )


def test_bump_version_accumulates() -> None:
    """Bumps consecutivos incrementan monotonamente."""
    _reset_state()
    from app.core import cache

    assert cache.current_version("test_ns") == 0
    for i in range(1, 6):
        cache.bump_version("test_ns")
        assert cache.current_version("test_ns") == i, (
            f"Tras {i} bumps, current_version debió ser {i}, "
            f"obtuve {cache.current_version('test_ns')}"
        )


def test_current_version_default_zero() -> None:
    """current_version(ns) sobre namespace nunca bumpeada → 0."""
    _reset_state()
    from app.core import cache

    assert cache.current_version("never_bumped") == 0


# ──────────────────────────────────────────────────────────────────────────
# 2) SWR sin lock
# ──────────────────────────────────────────────────────────────────────────
def test_swr_returns_stale_when_pending_in_flight() -> None:
    """Si `_pending[ns]=True` Y existe entry en cache (aún si está expirado),
    `get_or_compute` devuelve el valor cacheado sin ejecutar `compute_fn`.

    Esto es lo que permite que un request "no espere" mientras otro
    thread refetchea — el path lock-free devuelve stale inmediatamente.

    NB: cuando se llama `get_or_compute("ns", ttl_seconds=60, compute_fn=fn)`
    con `key_parts=()`, `_make_key` produce `"ns:v{version}"` SIN suffix
    (la logica de `_make_key` usa `f"{ns}:v{ver}:{suffix}" if suffix else
    base` — empty suffix corta los dos puntos finales). Por eso pre-poblo
    con `"swr_ns:v0"` y no con `"swr_ns:v0:test"`.
    """
    _reset_state()
    from app.core import cache as c

    # Pre-poblar directo el cache con un entry "viejo-pero-aceptable"
    # (simulamos expires_at en el pasado vía key manual).
    c._cache["swr_ns:v0"] = (c._now() - 10, "stale-value")
    c._pending["swr_ns"] = True

    compute_calls = []
    def compute_fn():
        compute_calls.append(1)
        return "fresh-value"

    result = c.get_or_compute("swr_ns", ttl_seconds=60, compute_fn=compute_fn)

    assert result == "stale-value", (
        f"SWR debió devolver stale-value, obtuve {result!r}"
    )
    assert compute_calls == [], (
        f"compute_fn NO debió correr (refetch en flight), corrió {len(compute_calls)} veces"
    )

    # Cleanup: get_or_compute short-circuiteó antes del try/finally,
    # así que _pending quedó True. Restaurar manualmente.
    c._pending["swr_ns"] = False


def test_swr_pending_with_no_prior_value_falls_through() -> None:
    """Si pending=True pero NO hay entry previo, get_or_compute ejecuta
    compute_fn (cold start + concurrencia: no hay nada viejo para servir).
    """
    _reset_state()
    from app.core import cache as c

    c._pending["swr_ns2"] = True

    def compute_fn():
        return "fresh-from-cold"

    result = c.get_or_compute(
        "swr_ns2", ttl_seconds=60, compute_fn=compute_fn,
    )
    assert result == "fresh-from-cold", (
        f"Sin viejo, compute_fn debió correr, obtuve {result!r}"
    )
    c._pending["swr_ns2"] = False


# ──────────────────────────────────────────────────────────────────────────
# 3) Hard cap eviction
# ──────────────────────────────────────────────────────────────────────────
def test_hard_cap_evicts_expired_opportunistically() -> None:
    """Cuando `len(_cache) > _CACHE_HARD_CAP` durante un get_or_compute,
    las entries vencidas se purgan.

    Test con cap chico (3) via monkeypatch para hacerlo factible sin
    poblar 8192 entries reales.
    """
    _reset_state()
    from app.core import cache as c
    import app.core.cache as cache_mod

    # Reducir el cap a 3 para el test.
    original_cap = cache_mod._CACHE_HARD_CAP
    cache_mod._CACHE_HARD_CAP = 3
    try:
        # Poblar 4 entries, todas ellas en el pasado (expiradas).
        past = c._now() - 100
        c._cache["ns1:v0:a"] = (past, "expired-a")
        c._cache["ns1:v0:b"] = (past, "expired-b")
        c._cache["ns1:v0:c"] = (past, "expired-c")
        c._cache["ns1:v0:d"] = (past, "expired-d")  # ésto dispara el cap (4 > 3)

        assert len(c._cache) == 4

        # Cualquier get_or_compute debe disparar eviction.
        c.get_or_compute(
            "ns1", ttl_seconds=60, compute_fn=lambda: "fresh-new",
        )

        # Las 4 vencidas debieron purgarse; sólo queda la nueva entry.
        assert len(c._cache) == 1, (
            f"Esperaba 1 entry post-eviction (la nueva), obtuve {len(c._cache)}: "
            f"{list(c._cache.keys())}"
        )
        # La nueva key es ns1:v{version}:<sin part> (key_parts vacío)
        only_key = list(c._cache.keys())[0]
        assert only_key.startswith("ns1:v"), f"Key inesperada: {only_key}"
    finally:
        cache_mod._CACHE_HARD_CAP = original_cap


def test_hard_cap_constant_is_positive() -> None:
    """`_CACHE_HARD_CAP` debe ser un int positivo (sanity check).

    Cambio accidental a 0/negativo desactivaría la protección de memory
    growth (que el code-reviewer detectó como bug crítico).
    """
    from app.core import cache

    assert isinstance(cache._CACHE_HARD_CAP, int), (
        f"_CACHE_HARD_CAP debe ser int, es {type(cache._CACHE_HARD_CAP)}"
    )
    assert cache._CACHE_HARD_CAP > 0, (
        f"_CACHE_HARD_CAP debe ser > 0 (protección memory), "
        f"vale {cache._CACHE_HARD_CAP}"
    )
    # Y debe estar en el rango razonable para una app chica.
    assert 100 <= cache._CACHE_HARD_CAP <= 100_000, (
        f"_CACHE_HARD_CAP fuera de rango razonable: {cache._CACHE_HARD_CAP}"
    )


def test_hard_cap_fallback_evicts_oldest_when_no_expired() -> None:
    """Cuando el cap se excede Y NO hay expired entries, el fallback
    sort-delete por timestamp debe eliminar las entries más viejas
    HASTA DEJAR 75% del cap (HEADROOM_RATIO 3/4).

    Antes del fix (con `len - cap`), esto causaba oscilación de borde:
    post-fallback + post-compute quedaba en cap+1 y el próximo miss
    repetía el eviction indefinidamente. Con 75% headroom, post-compute
    queda en `0.75*cap + 1`, dando margen real para el próximo ciclo.

    Setup: cap=8, 9 entries FUTURAS. Headroom = 6. 
       - Fallback borra `9 - 6 = 3` entries (las más viejas: a, b, c).
       - Compute agrega 1 nueva entry.
       - Final: `9 - 3 + 1 = 7` entries (d, e, f, g, h, i, + fresh).
    """
    _reset_state()
    from app.core import cache as c
    import app.core.cache as cache_mod

    original_cap = cache_mod._CACHE_HARD_CAP
    cache_mod._CACHE_HARD_CAP = 8  # múltiplo de 4 para headroom limpio
    try:
        # 9 entries FUTURAS (no expiradas). headroom = 8 * 0.75 = 6.
        future_t = c._now() + 3600
        c._cache["nsfb:v0:a"] = (future_t, "a-oldest")      # va
        c._cache["nsfb:v0:b"] = (future_t + 1, "b")         # va
        c._cache["nsfb:v0:c"] = (future_t + 2, "c")         # va
        c._cache["nsfb:v0:d"] = (future_t + 3, "d")         # queda
        c._cache["nsfb:v0:e"] = (future_t + 4, "e")
        c._cache["nsfb:v0:f"] = (future_t + 5, "f")
        c._cache["nsfb:v0:g"] = (future_t + 6, "g")
        c._cache["nsfb:v0:h"] = (future_t + 7, "h")
        c._cache["nsfb:v0:i"] = (future_t + 8, "i-newest")  # queda

        assert len(c._cache) == 9, "setup mal armado"

        c.get_or_compute("nsfb", ttl_seconds=60, compute_fn=lambda: "fresh-new")

        # Post-eviction (3 deletes) + post-compute (+1) = 9 - 3 + 1 = 7.
        assert len(c._cache) == 7, (
            f"Esperaba 7 entries (post-fallback + post-compute), obtuve {len(c._cache)}: "
            f"{list(c._cache.keys())}"
        )
        # Deben haber evictado las MÁS VIEJAS por timestamp (a, b, c).
        for k_should_evict in ("nsfb:v0:a", "nsfb:v0:b", "nsfb:v0:c"):
            assert k_should_evict not in c._cache, (
                f"{k_should_evict} (vieja por timestamp) debió evictarse, sigue: "
                f"{list(c._cache.keys())}"
            )
        # Las MÁS NUEVAS (d..i) deben sobrevivir.
        for k_should_survive in ("nsfb:v0:d", "nsfb:v0:e", "nsfb:v0:f",
                                  "nsfb:v0:g", "nsfb:v0:h", "nsfb:v0:i"):
            assert k_should_survive in c._cache, (
                f"{k_should_survive} debió sobrevivir: {list(c._cache.keys())}"
            )
        # Y se agregó la nueva entry del compute (key sin suffix).
        assert "nsfb:v0" in c._cache, (
            f"Nueva entry del compute debió insertarse: {list(c._cache.keys())}"
        )

        # El headroom post-eviction debe estar claramente debajo del cap.
        # `cap=8, headroom=6`, post-compute = 7 → 7 < cap=8. Sin oscilación.
        assert len(c._cache) < cache_mod._CACHE_HARD_CAP, (
            f"Post-eviction+compute debe estar < cap (sin oscilación): "
            f"len={len(c._cache)}, cap={cache_mod._CACHE_HARD_CAP}"
        )
    finally:
        cache_mod._CACHE_HARD_CAP = original_cap


# ──────────────────────────────────────────────────────────────────────────
# 4) ValueError en namespace con ":"
# ──────────────────────────────────────────────────────────────────────────
def test_bump_version_rejects_colon_in_namespace() -> None:
    """bump_version('ns:with:colons') → ValueError.

    El namespace NO puede contener ':' porque es el separador de keys
    compuestas (`ns:v{N}:suffix`) — usarlo generaría confusión con
    `_make_key(NS, "suffix")` que internamente lee `_versions[NS]`.
    """
    _reset_state()
    from app.core import cache

    try:
        cache.bump_version("foo:bar:baz")
    except ValueError as e:
        assert ":" in str(e), f"Mensaje de error debe mencionar ':', obtuve: {e}"
        return
    raise AssertionError("bump_version('foo:bar:baz') debió raise ValueError")


def test_get_or_compute_rejects_colon_in_namespace() -> None:
    """get_or_compute con namespace que contiene ':' → ValueError."""
    _reset_state()
    from app.core import cache

    try:
        cache.get_or_compute(
            "ns:with:colon",
            ttl_seconds=10,
            compute_fn=lambda: "x",
        )
    except ValueError as e:
        assert ":" in str(e), f"Mensaje de error debe mencionar ':', obtuve: {e}"
        return
    raise AssertionError(
        "get_or_compute con namespace 'ns:with:colon' debió raise ValueError"
    )


# ──────────────────────────────────────────────────────────────────────────
# 5) get_or_compute: hits, TTL, batching y key_parts
# ──────────────────────────────────────────────────────────────────────────
def test_compute_fn_called_only_once_within_ttl() -> None:
    """Dentro del TTL, compute_fn se llama UNA sola vez aunque se hagan
    varios get_or_compute. Si esto rompiera, cada request estaría
    pegándole a la BD (derrota completa del cache).
    """
    _reset_state()
    from app.core import cache

    calls = []
    def compute():
        calls.append(1)
        return 42

    for _ in range(10):
        result = cache.get_or_compute(
            "hits", ttl_seconds=60, compute_fn=compute,
        )
        assert result == 42

    assert len(calls) == 1, (
        f"compute_fn debió correr 1 sola vez en 10 calls dentro del TTL, "
        f"corrió {len(calls)} veces"
    )


def test_compute_fn_recalled_after_ttl_expires() -> None:
    """Tras dormir más que el TTL, compute_fn corre de nuevo."""
    _reset_state()
    from app.core import cache

    calls = []
    def compute():
        calls.append(1)
        return len(calls)

    r1 = cache.get_or_compute("ttl_test", ttl_seconds=0.05, compute_fn=compute)
    assert r1 == 1

    time.sleep(0.10)

    r2 = cache.get_or_compute("ttl_test", ttl_seconds=0.05, compute_fn=compute)
    assert r2 == 2, (
        f"Tras TTL expiry (0.05s + sleep 0.10s), compute debió correr de nuevo, "
        f"r2={r2}"
    )


def test_ttl_zero_disables_cache() -> None:
    """ttl_seconds=0 (o negativo) → siempre recomputa, nunca cachea.

    Útil para apagado de emergencia sin tocar las llamadas.
    """
    _reset_state()
    from app.core import cache

    calls = []
    def compute():
        calls.append(1)
        return "always-fresh"

    for _ in range(3):
        result = cache.get_or_compute(
            "no_cache", ttl_seconds=0, compute_fn=compute,
        )
        assert result == "always-fresh"

    assert len(calls) == 3, (
        f"Con ttl=0, compute_fn debió correr 3 veces (siempre), corrió {len(calls)}"
    )


def test_key_parts_produces_separate_cache_slots() -> None:
    """key_parts=("active",) vs key_parts=("all",) sobre el mismo
    namespace → keys separadas, valores independientes.

    Esta es la base del patrón público/admin: NS_EMAIL_ACCOUNTS
    con key_parts=() vs key_parts=("active",) cachean distintos
    resultados.
    """
    _reset_state()
    from app.core import cache

    active_calls = []
    all_calls = []

    def compute_active():
        active_calls.append(1)
        return ["active@x.com"]

    def compute_all():
        all_calls.append(1)
        return ["all1@x.com", "all2@x.com"]

    # Caching de "active"
    r_active = cache.get_or_compute(
        "ns_split", ttl_seconds=60, compute_fn=compute_active,
        key_parts=("active",),
    )
    assert r_active == ["active@x.com"]

    # Caching de "all" (debe crear slot separado)
    r_all = cache.get_or_compute(
        "ns_split", ttl_seconds=60, compute_fn=compute_all,
        key_parts=("all",),
    )
    assert r_all == ["all1@x.com", "all2@x.com"]

    # Re-hit de ambos: sin re-compute
    assert cache.get_or_compute(
        "ns_split", ttl_seconds=60, compute_fn=compute_active,
        key_parts=("active",),
    ) == ["active@x.com"]
    assert cache.get_or_compute(
        "ns_split", ttl_seconds=60, compute_fn=compute_all,
        key_parts=("all",),
    ) == ["all1@x.com", "all2@x.com"]

    assert len(active_calls) == 1, (
        f"compute_active debió correr 1 vez, corrió {len(active_calls)}"
    )
    assert len(all_calls) == 1, (
        f"compute_all debió correr 1 vez, corrió {len(all_calls)}"
    )


def test_cross_router_namespace_sharing_invalidation() -> None:
    """Caso de uso real: bump en NS_PLATFORMS invalida tanto el cache
    del admin endpoint (key_parts=()) como el cache público
    (key_parts=("active",)). Ambos usan la MISMA versión lógica.
    """
    _reset_state()
    from app.core import cache
    from app.core.cache import NS_PLATFORMS

    # Caching de las dos variantes
    cache.get_or_compute(
        NS_PLATFORMS, ttl_seconds=60, compute_fn=lambda: "admin-list",
    )
    cache.get_or_compute(
        NS_PLATFORMS, ttl_seconds=60, compute_fn=lambda: "public-list",
        key_parts=("active",),
    )
    assert cache.current_version(NS_PLATFORMS) == 0

    # Bump desde "otro handler" (admin mutó una plataforma)
    cache.bump_version(NS_PLATFORMS)
    assert cache.current_version(NS_PLATFORMS) == 1

    # Ambas keys anteriores son inalcanzables (las nuevas son con v1)
    after_calls = []
    cache.get_or_compute(
        NS_PLATFORMS, ttl_seconds=60,
        compute_fn=lambda: after_calls.append("admin") or "admin-v1",
    )
    cache.get_or_compute(
        NS_PLATFORMS, ttl_seconds=60,
        compute_fn=lambda: after_calls.append("public") or "public-v1",
        key_parts=("active",),
    )
    assert after_calls == ["admin", "public"], (
        f"Tras bump, ambos endpoints debieron recomputar: {after_calls}"
    )


# ──────────────────────────────────────────────────────────────────────────
# 6) clear_all reset
# ──────────────────────────────────────────────────────────────────────────
def test_clear_all_resets_state() -> None:
    """Después de clear_all, _cache vacío, _versions en 0, _pending limpio."""
    _reset_state()
    from app.core import cache

    cache.get_or_compute("x", ttl_seconds=60, compute_fn=lambda: "v")
    cache.bump_version("y")
    assert cache.stats_snapshot()["entries"] >= 1

    cache.clear_all()
    snap = cache.stats_snapshot()
    assert snap["entries"] == 0, f"Después de clear: {snap}"
    assert snap["versions"] == {}, f"Versions no limpias: {snap}"
    assert snap["pending"] == [], f"Pending no limpio: {snap}"


# ──────────────────────────────────────────────────────────────────────────
# Standalone runner
# ──────────────────────────────────────────────────────────────────────────
def main() -> int:
    tests = sorted(
        [(name, fn) for name, fn in globals().items() if name.startswith("test_")]
    )
    passed = failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"  ✓ {name}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {name}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {name}: [{type(e).__name__}] {e}")
            failed += 1
    print(f"\n{'=' * 50}")
    print(f"Result: {passed}/{passed + failed}")
    if failed:
        print("FAIL — regresión en cache strategy. Investigar.")
        return 1
    print("PASS — cache strategy validada.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
