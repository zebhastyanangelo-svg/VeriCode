# 04 — Flujos de Usuario (End-to-End)

> Diagramas de flujo paso-a-paso. Cada flujo describe: actores, pantallas, transiciones, datos involucrados y casos de error.

---

## Flujo A — Primer arranque (admin)

**Actor**: operador nuevo.
**Objetivo**: dejar el sistema funcionando en su primera sesión.

```mermaid
graph TD
    A[Inicio] --> B[Levantar backend uvicorn]
    B --> C[seed.py crea plataformas base]
    C --> D[IMAP IDLE Watcher arranca (conexiones persistentes)]
    D --> E[Levantar frontend npm run dev]
    E --> F[Abrir /#/login]
    F --> G[GET /api/v1/auth/setup<br/>crea admin/admin123]
    G --> H[Login admin/admin123]
    H --> I[GET /jwt → token 8 h]
    I --> J[Redirect a /#/]
    J --> K[Dashboard carga: stats + códigos vía WS]
    K --> L[Ir a /#/accounts]
    L --> M[Agregar Cuenta IMAP]
    M --> N[Test conexión → OK]
    N --> O[Cuenta queda is_active=true]
    O --> P[Próximo poll del backend procesa emails]
```

### Pasos detallados

1. **Backend init** (`backend/seed.py` o `lifespan`):
   - Crea tablas con `Base.metadata.create_all`.
   - Inserta plataformas por defecto si `Platform.count() == 0`.
   - Levanta el poller en background.
2. **Frontend init**: solo necesita `npm install && npm run dev`.
3. **Auto-creación admin**: en `app/api/v1/auth.py`, `GET /auth/setup` crea `admin/admin123` si `USERS_DB["admin"]` no existe.
   - En producción esto debe ser idempotente y seguro (rate-limit + log).

---

## Flujo B — Cliente pide su código (público)

**Actor**: cliente final sin cuenta.
**Objetivo**: obtener el código que le llegó al correo.

```mermaid
graph TD
    A1[Visita /#/code-request] --> B1{Cargó frontend sin auth?}
    B1 -- Sí --> C1[Carga selectores]
    B1 -- Bloqueado por guard<br/>BUG --> X1[Lo arregla opencode]
    C1 --> D2[GET /api/v1/public/platforms]
    D2 --> E2[Renderiza select de plataformas activas]
    E2 --> F1[Cliente ingresa correo + selecciona plataforma]
    F1 --> G1[Click 'Buscar Código']
    G1 --> H1[POST /api/v1/public/request-code]
    H1 --> I1[Backend busca código en BD]
    I1 --> J1{Existe código para<br/>email + plataforma?}
    J1 -- Sí --> K1[Devuelve code + recibido_at + ...]
    K1 --> L1[Frontend muestra:<br/>código grande + detalles + botón 'Solicitar otro']
    J1 -- No --> M1[404 'No hay código...']
    M1 --> N1[Toast error + mantener form]
```

### Notas

- Este flujo **NO debe pedir autenticación**. Si el guard de `App.jsx` lo bloquea, es el bug #2 del plan.
- La respuesta muestra el código, plataforma, correo, fecha de recepción y estado leído/no leído.
- **No** marca `is_delivered` automáticamente — eso depende de la decisión de negocio (ver `06-PLAN.md` #9).

---

## Flujo C — IMAP IDLE Watcher procesa un correo nuevo

**Actor**: sistema (background).
**Objetivo**: mantener conexiones IMAP IDLE persistentes y procesar correos entrantes en tiempo real.

```mermaid
sequenceDiagram
    participant Loop as asyncio loop
    participant Watcher as IMAP IDLE Watcher (por cuenta)
    participant IMAP as Servidor IMAP
    participant DB as SQLAlchemy/SQLite
    participant WS as ConnectionManager

    Loop->>Watcher: crear watchers (1 por cuenta activa)
    Watcher->>IMAP: aioimaplib.IMAP4_SSL.connect + login
    IMAP-->>Watcher: ok
    Watcher->>IMAP: SELECT INBOX
    IMAP-->>Watcher: ok
    Watcher->>IMAP: IDLE (RFC 2177)
    Note right of Watcher: Conexión persistente, sin polling
    IMAP-->>Watcher: push: * N EXISTS (nuevo correo!)
    Watcher->>IMAP: IDLE DONE → search UNSEEN
    IMAP-->>Watcher: [uid]
    Watcher->>IMAP: fetch RFC822 + store +FLAGS \Seen
    IMAP-->>Watcher: raw bytes
    Watcher->>Watcher: parse from, subject, body
    Watcher->>Watcher: account.platform ?? guess_platform
    Watcher->>Watcher: extract_code_from_body
    alt código extraído y no existe
        Watcher->>DB: INSERT verification_code
        DB-->>Watcher: new_code object
        Watcher->>Loop: run_coroutine_threadsafe(notify_new_code)
        Loop->>WS: broadcast_new_code({type:new_code,data})
        WS-->>Frontend: WS message al dashboard
    end
    Watcher->>IMAP: IDLE (nuevo ciclo, espera próximo push)
```

### Garantías

- **Idempotencia**: si el mismo (email_account, code, subject) ya existe en BD → no duplica.
- **Thread-safety**: la notificación al WS se ejecuta en el loop principal vía `asyncio.run_coroutine_threadsafe`, evitando el bug clásico de `loop.run_until_complete` desde thread sync.
- **Conexión persistente**: cada watcher mantiene su conexión aioimaplib abierta. Si se pierde (timeout, error de red) → reconexión automática con backoff de 10 s.
- **IDLE timeout**: configurable vía `IMAP_IDLE_TIMEOUT` (default 1680 s = 28 min). Al expirar se re-entra en IDLE automáticamente.

---

## Flujo D — Admin configura plataforma nueva

```mermaid
graph TD
    A[/#/platforms] --> B[Click + Agregar Plataforma]
    B --> C[Modal: nombre, display_name, tipo, regex code, regex sender, regex subject, icono]
    C --> D[Submit]
    D --> E[POST /api/v1/platforms]
    E --> F{Existe name?}
    F -- Sí --> G[400 'Esta plataforma ya existe']
    F -- No --> H[INSERT platforms]
    H --> I[Modal cierra, lista recarga]
    I --> J[Próximo poll usa sender_pattern / code_pattern]
```

**Casos**:
- Plataforma **sin patrones** → el sistema cae al fallback `PLATFORM_PATTERNS` hardcodeado.
- Plataforma **con `sender_pattern`** → gana sobre el hardcodeado si matchea.

---

## Flujo E — Admin agrega casilla IMAP

```mermaid
graph TD
    A[/#/accounts] --> B[Click + Agregar Cuenta]
    B --> C[Modal: email, tipo, password, host?, port?, plataforma?, notas]
    C --> D[Click 'Probar conexión'<br/>opcional pre-save]
    D --> E[POST /email-accounts/{id}/test]
    E --> F{Conecta?}
    F -- Sí --> G[Toast: 'Conexión exitosa']
    F -- No --> H[Toast error: 'No se pudo conectar']
    C --> I[Save]
    I --> J[POST /email-accounts]
    J --> K{Email único?}
    K -- No --> L[400 'Esta cuenta ya existe']
    K -- Sí --> M[INSERT email_accounts]
    M --> N[is_active=true por default]
    N --> O[Próximo poll la incluye]
```

**Detalles**:
- Tipo `gmail/outlook/yahoo` → autocompleta host si no se dio.
- El password se almancena en `password_encrypted` (hoy en plano — ver `06-PLAN.md` #8).
- Click en "Verificar ahora" del listado → `POST /email-accounts/{id}/poll` ejecuta `process_account` inmediato.

---

## Flujo F — Cliente entrega código al admin (futuro)

> Idea para v1.1 — el cliente recibe una notificación cuando llega su código, sin necesidad de pedirlo on-demand.

```mermaid
sequenceDiagram
    participant Poller as IMAPPoller
    participant DB as BD
    participant Notify as NotificationService (futuro)
    participant Cliente as Cliente

    Poller->>DB: nuevo código
    Poller->>Notify: dispatch(email, platform, code)
    Notify->>Cliente: Email / SMS / Web Push
    Cliente->>Notify: GET /public/request-code?email=...&platform=...
    Notify-->>Cliente: code
```

Hoy **no existe**: el cliente tiene que entrar a `/#/code-request` activamente.

---

## Estado de cada flujo vs implementación actual

| Flujo | Estado |
|-------|--------|
| **A** — Primer arranque | ✅ Funciona con `python seed.py`. ⚠️ Falta auto-llamar `/auth/setup` desde `lifespan`. |
| **B** — Cliente pide código | ⚠️ Backend OK, frontend bug (guard auth). **Fix en `App.jsx`**. |
| **C** — IMAP IDLE Watcher | ✅ Funcional (aioimaplib, conexiones persistentes, push). |
| **D** — Admin plataforma | ✅ Funciona. |
| **E** — Admin casilla | ✅ Funciona. `platform_id` ya soportado. |
| **F** — Notificación proactiva | ❌ No implementado — roadmap v1.1. |
