# 08 · Caching y rendimiento

Este documento describe la estrategia de caching de VeriCode, las
decisiones que la motivan y los trade-offs que conocidamente deja.

## TL;DR

| Capa | Qué cachea | TTL | Invalidación |
|------|------------|-----|--------------|
| Backend in-process | `GET /codes/stats` | 30 s | bump en `mark_delivered` / `mark_read` |
| Backend in-process | `GET /platforms` (admin + público) | 60 s | bump en POST/PUT/DELETE de `/platforms` |
| Backend in-process | `GET /email-accounts` (admin + público, sólo activas) | 30 s | bump en POST/PUT/DELETE de `/email-accounts` |
| HTTP `Cache-Control` | Todos los GET anteriores | 5–60 s | ETag derivado de `cache_version[ns]` |
| HTTP `ETag` | Mismos endpoints | — | Bumpea junto al namespace |
| Middleware | `GZipMiddleware` para bodies JSON ≥ 500 B | — | — |
| Frontend (TODO) | `useQuery` con stale-while-revalidate | 5–30 s | `setQueryData` en `new_code` del WS |

> **Nota importante:** el frontend React Query **no se migró en esta
> primera versión** (queda como follow-up). El backend ya tiene los
> hooks listos: cada `Cache-Control` + `ETag` + `bump_version` hace que
> el browser sirva desde su propio cache cuando el namespace no cambió.

## 1. ¿Por qué NO usamos Redis?

- **Costo $0 ya conseguido** en Render free tier con `--workers 1`
  (ver `07-DEPLOY.md`). El rate-limit (que es la mayor razón para un
  store compartido) ya está documentado como limitación de instancia
  única.
- **Single-instance es por diseño.** Toda la estrategia aquí asume
  uvicorn con un solo proceso. Si en el futuro se escala a
  `--workers > 1`, hay que migrar `app/core/cache.py` a un store
  externo (Redis, Memcached, o un Postgres dedicado con `UNIQUE`s).
- **Latencia.** Un dict in-process se mide en nanosegundos. Redis añade
  un roundtrip de red que para caches de 30s probablemente no compensa.

## 2. ¿Por qué no cacheamos `GET /codes` paginado?

- Mutaciones como `mark_delivered=True` no cambian `row_count` ni
  `max(received_at)` → un ETag ingenieril sería incorrecto (304 cuando
  en realidad hubo cambios).
- Postgres resuelve `LIMIT 50 OFFSET 0` con índices en < 5 ms. Cachear
  agrega complejidad sin ganancia perceptible.
- `Cache-Control: no-store` por defecto (no se setea nada) deja que el
  navegador haga el conditional GET con `If-None-Match` solo cuando el
  handler lo decide — en este caso, no.

El WebSocket `/codes/ws` es la fuente de verdad para códigos nuevos: el
cliente hace **optimistic update** con `setQueryData` al recibir
`{ type: "new_code", data: {...} }` y el servidor sólo confirma
después. Esto evita refetch storms cuando 30 pestañas tienen el
dashboard abierto y entra un código nuevo.

## 3. Decisiones de diseño (y sus costos)

### 3.1 Stale-while-revalidate sin lock

`app/core/cache.py:get_or_compute()` evita `threading.Lock` en el
camino rápido. Razón: FastAPI ejecuta handlers `def` (sync) en el
threadpool de Starlette (cap ~40). Un lock tradicional podía starvar
ese threadpool si la BD se enlentecía. En su lugar usamos un flag
`_pending[namespace]` y devolvemos el valor viejo cuando hay un
refetch en vuelo.

Trade-off: hasta que el refetch termina, dos requests pueden recibir
el mismo valor "viejo-vencido". Aceptable porque el TTL es corto y
los handlers son read-only (no side-effects al refrescar).

### 3.2 Version-keyed invalidation

Cada namespace tiene `_versions[ns]` (entero). Las keys de cache se
construyen como `ns:v{N}:{...}`. Bumpear la versión invalida TODO el
namespace instantáneamente sin recorrer keys ni fugar memoria por
entradas huérfanas (la nueva key tiene `v{N+1}`, el próximo GET
re-crea).

### 3.3 Namespaces compartidos admin↔público

`NS_PLATFORMS` y `NS_EMAIL_ACCOUNTS` son compartidos entre los routers
admin (que requieren auth) y `/public/*` (sin auth). Esto significa
que cuando el admin muta una plataforma, **ambos** caches se invalidan
al toque. Si en el futuro los routers divergen (e.g. distintos campos
proyectados), conviene un namespace por combinación.

### 3.4 Lo que SÍ invalida vs lo que NO invalida `codes_stats`

| Evento | Invalida stats | Razón |
|--------|----------------|-------|
| `PUT /codes/{id}/deliver` | ✓ | decrementa `undelivered` |
| `PUT /codes/{id}/read` | ✓ | decrementa `unread` |
| IMAP poll crea código | NO | el WS entrega el código al cliente; stats se reconcilian dentro del TTL |
| `POST /email-accounts/{id}/poll` | NO | mismo motivo |

Decisión consciente: las counters pueden quedar stale hasta 30s
después de un código nuevo. Aceptable porque el dashboard ya tiene el
código vía WS en < 500 ms.

## 4. Configuración recomendada por entorno

| Entorno | `Cache-Control` | Notas |
|---------|-----------------|-------|
| `development` | igual que prod | el operador ve los headers en DevTools |
| `production` | igual que dev | el cache funciona igual; la diferencia es operativa |

Variable de entorno relevante: ninguna. El cache es in-process y se
gestiona por versiones (no configurable vía env).

## 5. Banner al arranque

`_print_startup_banner()` ahora incluye:

```text
  Cache backend:
    • stats: TTL 30s · invalidación explícita en mark_*
    • platforms: TTL 60s · admin+público compartido
    • email-accounts: TTL 30s · admin+público compartido
    • entries: 0 · versions: {stats:0, platforms:0, email_accounts:0}
```

## 6. Métricas a mirar

- **p95 GET /codes/stats** debería caer a < 5 ms después del primer hit.
- **p95 GET /platforms** debería caer a < 2 ms (es un SELECT trivial).
- **p99 latencia al mutar + GET subsiguiente** debería seguir bajo
  (< 50 ms): el `bump_version` es una sola escritura en un dict.
- **Tamaño de respuesta vs bytes transferidos:** activar Network →
  Img/JS en DevTools. Las listas de códigos deberían venir con
  `Content-Encoding: gzip` y 60–70% menos bytes que sin compresión.

## 7. Testing

- `tests/test_cache.py` (TODO): tests unitarios del TTL + bump + SWR.
- E2E existente: agrega asserts para `Cache-Control` y `ETag` headers
  en respuestas cacheadas.

## 8. Limitaciones conocidas

1. **Single-instance.** Si se escala a `--workers > 1`,
   `docs/07-DEPLOY.md` §5 lo deja explícito y la estrategia deja de
   funcionar: cada worker tendría su propio cache y el cliente podría
   recibir datos inconsistentes según qué worker despache.
2. **Memory growth.** El cache crece lineal con los namespaces
   versionados. En la práctica son < 1 KB por entrada. Sin TTL
   "físico" de eviction por tamaño; `_pending` solo evita el
   thundering herd, no el memory leak. Si el operador nota
   crecimiento, puede llamar `app/core/cache.clear_all()` desde una
   ruta de admin.
3. **Dispatcher race.** El patrón "ambos writers leen el flag y
   escriben el cache" puede generar escrituras duplicadas en cold
   start + alta concurrencia. Es benigno (mismo valor) pero gasta un
   SELECT extra.
