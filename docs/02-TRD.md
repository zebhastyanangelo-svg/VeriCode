# 02 — Technical Requirements Document (TRD)

**Producto**: VeriCode
**Stack**: Python 3.14 + FastAPI 0.115 + React 18 + PostgreSQL/SQLite
**Versión**: 1.0

---

## 1. 🏗️ Arquitectura general

```
┌──────────────────────────────────────────────────────────────────┐
│                          CLIENTE FINAL                            │
│  Navegador (Chrome/Firefox/Safari)  → http://localhost:5173       │
│  Acceso: /#/code-request (sin auth)                               │
└──────────────────────────────┬───────────────────────────────────┘
                               │ HTTPS
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React 18)                       │
│  • Vite 5 como bundler                                           │
│  • Hash-routing manual (no React Router instalado)                │
│  • Context API: AuthContext + ToastContext                        │
│  • FontAwesome 7 para iconos                                      │
│  • apiFetch con JWT automático en headers                         │
└──────────────────────────────┬───────────────────────────────────┘
                               │ fetch + Bearer JWT
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                    BACKEND (FastAPI 0.115)                         │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ Routers REST (api/v1/)                                   │     │
│  │  • /auth       → JWT                                     │     │
│  │  • /email-accounts, /platforms, /codes                   │     │
│  │  • /public     → sin auth                                │     │
│  │  • /codes/ws   → WebSocket broadcast                     │     │
│  └─────────────────────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ Services                                                 │     │
│  │  • IMAP IDLE Watcher → aioimaplib, push, persistente    │     │
│  │  • code_extractor → regex                                    │     │
│  └─────────────────────────────────────────────────────────┘     │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │ auth (JWT + bcrypt)                                       │     │
│  └─────────────────────────────────────────────────────────┘     │
└──────────────────────────────┬───────────────────────────────────┘
                                │ SQLAlchemy 2.0
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                  │
│  • Dev/test: SQLite (codigos.db / codigos_e2e.db)                  │
│  • Prod: Supabase PostgreSQL (pooler puerto 6543, sslmode=require) │
│                                                                       │
│  Tablas:                                                              │
│    email_accounts   ←──┐                                            │
│    platforms           ├──→ verification_codes                       │
│    users               ←──┘                                            │
└──────────────────────────────────────────────────────────────────┘
```

---

## 2. 📦 Versiones

### Backend (`backend/requirements.txt`)

| Paquete | Versión | Uso |
|---------|---------|-----|
| fastapi | 0.138.2 | Framework HTTP |
| uvicorn[standard] | 0.49.0 | ASGI server |
| sqlalchemy | 2.0.51 | ORM |
| pydantic | 2.13.4 | Validación |
| pydantic-settings | 2.14.2 | Config desde .env |
| python-jose[cryptography] | 3.5.0 | JWT |
| bcrypt | 5.0.0 | Hash passwords |
| python-multipart | 0.0.32 | Upload forms |
| cryptography | 49.0.0 | TLS / future Fernet |
| alembic | 1.18.5 | Migrations (no inicializadas) |
| websockets | ≥16.0 | WS support FastAPI |
| aioimaplib | ≥2.0.0 | Cliente IMAP asíncrono con IDLE (RFC 2177) |

### Frontend (`frontend/package.json`)

| Paquete | Uso |
|---------|-----|
| react | 18.x UI |
| react-dom | 18.x Render |
| vite | 5.x dev server / bundler |
| @vitejs/plugin-react | React fast refresh |
| react-router-dom | (instalado, no usado realmente) |
| @fortawesome/fontawesome-free | Iconos |
| oxlint | Linter |

---

## 3. ⚙️ Variables de entorno

### 3.1 Backend (`backend/.env` — dev local)

```env
APP_NAME="Sistema de Códigos"
DATABASE_URL=sqlite:///./codigos.db
SECRET_KEY=cambiar-en-produccion-clave-segura
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
POLL_INTERVAL_SECONDS=30
```

Cargado vía `pydantic-settings` en `app/config.py`.

### 3.2 Backend en producción (Render)

Las variables se setean en el dashboard de Render, no en `.env`. Mínimo obligatorio:

| Variable | Valor ejemplo | Notas |
|----------|---------------|-------|
| `VERICODE_ENV` | `production` | Activa fail-fast guards. Case-insensitive. |
| `SECRET_KEY` | `secrets.token_urlsafe(64)` | ≥ 64 chars, no prefix `CHANGE-ME` |
| `FERNET_KEY` | `Fernet.generate_key().decode()` | 32 bytes (base64 url-safe) |
| `BOOTSTRAP_TOKEN` | `secrets.token_urlsafe(32)` | Para POST /auth/setup |
| `DATABASE_URL` | `postgresql://postgres.[ref]:[pw]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require` | **Pooler puerto 6543** (ver docs/07-DEPLOY.md §1) |
| `CORS_ORIGINS` | `https://app.tu-dominio.com` | NO usar `*` en prod |
| `TRUSTED_PROXIES` | `*` | Detrás de Render LB, todas las IPs son proxy confiable |
| `POLL_INTERVAL_SECONDS` | `30` | Mantenido por retrocompatibilidad (no usado por IDLE) |
| `IMAP_IDLE_TIMEOUT` | `1680` | Tiempo máximo del ciclo IDLE (RFC 2177, máx 29 min = 1740 s) |
| `AUTH_RATE_LIMIT_MAX_ATTEMPTS` | `5` | |
| `AUTH_RATE_LIMIT_WINDOW_MINUTES` | `15` | |

### 3.3 Frontend (Cloudflare Pages)

| Variable | Valor ejemplo | Notas |
|----------|---------------|-------|
| `VITE_API_URL` | `https://api.tu-dominio.com/api/v1` | Build-time, baked en el bundle JS |

Setear en `Cloudflare Pages → Settings → Environment variables → Production` antes del primer build. No requiere ningún cambio en `package.json` ni en el comando de build (`npm run build`).

---

## 4. 🔐 Seguridad

### 4.1 Auth

- **JWT HS256** firmado con `SECRET_KEY`.
- **Expiración**: 480 min (8 h) configurable.
- **Password**: `bcrypt.checkpw` con salt autogenerado.
- **Header**: `Authorization: Bearer <token>`.

### 4.2 Issues conocidos

| # | Issue | Mitigación |
|---|-------|------------|
| 1 | `password_encrypted` se guarda en texto plano | Cifrar con `cryptography.fernet` (key en env) — **pendiente**. |
| 2 | `SECRET_KEY` default en código | Sobrescribir en `.env` antes de deploy. |
| 3 | CORS `allow_origins=["*"]` | Restringir a dominios confiables en prod. |
| 4 | Admin user no se auto-crea en arranque | Solucionado: ejecutar `GET /api/v1/auth/setup` cada primer boot. |
| 5 | URL pública protegida por auth (bug en `App.jsx`) | Fix: renderizar `PublicCodeRequestPage` antes del guard. |

### 4.3 Defensa en profundidad

- Routers admin usan `Depends(get_current_user)`.
- Router público (`/api/v1/public/*`) **NO** requiere auth → devuelve solo datos no sensibles (lista de correos y plataformas activas, no las contraseñas).
- IDs internos nunca expuestos a clientes públicos.

---

## 5. 🗄️ Modelo de datos

*(Ver detalle completo en `05-BACKEND.md` §3)*

Tablas (SQLAlchemy 2.0 estilo `DeclarativeBase`):

- `email_accounts` — casillas IMAP
- `platforms` — Netflix, Disney+, etc.
- `verification_codes` — códigos extraídos
- (futuro) `users` — admin users (hoy en memoria `USERS_DB`)

Relaciones clave:
- `email_account.platform_id (FK → platforms.id)` nueva
- `verification_code.email_account_id (FK → email_accounts.id)`
- `verification_code.platform_id (FK → platforms.id)` nullable

---

## 6. 🔌 Endpoints REST

Prefijo: `/api/v1`

### Admin (requieren JWT)

| Método | Endpoint | Función |
|--------|----------|---------|
| POST | `/auth/token` | Login → JWT |
| GET | `/auth/me` | Info del usuario del token |
| GET | `/auth/setup` | Crea admin si no existe |
| GET | `/email-accounts` | Listar |
| POST | `/email-accounts` | Crear |
| GET | `/email-accounts/{id}` | Detalle |
| PUT | `/email-accounts/{id}` | Editar |
| DELETE | `/email-accounts/{id}` | Borrar |
| POST | `/email-accounts/{id}/test` | Probar IMAP |
| POST | `/email-accounts/{id}/poll` | Poll manual |
| GET | `/platforms` | Listar |
| POST | `/platforms` | Crear |
| PUT | `/platforms/{id}` | Editar |
| DELETE | `/platforms/{id}` | Borrar |
| GET | `/codes` | Listar (filtros: q, platform_id, email_account_id, is_delivered, limit/offset) |
| GET | `/codes/recent?minutes=N` | Últimos N minutos |
| GET | `/codes/stats` | Total, unread, undelivered, last_hour |
| PUT | `/codes/{id}/deliver` | Marcar entregado |
| PUT | `/codes/{id}/read` | Marcar leído |
| WS | `/codes/ws` | WebSocket broadcast |

### Público (sin auth)

| Método | Endpoint | Función |
|--------|----------|---------|
| GET | `/public/ping` | Health-check (sin auth, sin DB). Usado por frontend como keep-alive cada 5 min |
| GET | `/public/platforms` | Lista plataformas activas |
| GET | `/public/verify-email-access` | Verifica combinación email + platform + devuelve código |
| POST | `/public/request-code` | Solicita código |

---

## 7. 🤖 Servicios backend

### 7.1 IMAPPoller (`app/services/imap_poller.py`)

- Singleton creado en `main.py`.
- Arranca en `lifespan` con `await poller.start()`.
- Crea una tarea asyncio por cuenta activa usando IMAP IDLE (RFC 2177).
- Cada tarea mantiene una conexión persistente con `aioimaplib` y recibe notificaciones push del servidor cuando llega un nuevo correo, eliminando el sondeo periódico.
- `process_account`: one-shot connect → fetch UNSEEN → extract → save → callback (usado por el endpoint manual `/poll`).
- `connect_account`: usa IMAP4_SSL con host según `email_type` (autofill Gmail/Outlook/Yahoo).
- `fetch_unread`: marca `\\Seen` después de procesar para no duplicar.
- `notify_new_code`: lanza `asyncio.run_coroutine_threadsafe` para que `broadcast_new_code` corra en el loop principal y use el WS.
- Cuando se crea/edita/elimina una cuenta, el router llama a `poller.reload_accounts()` para reiniciar los watchers.

### 7.2 code_extractor (`app/services/code_extractor.py`)

- `guess_platform(sender, subject, platforms)`:
  1. Prioridad 1: patrón `sender_pattern` / `subject_pattern` definido en BD.
  2. Prioridad 2: diccionario hardcodeado `PLATFORM_PATTERNS` → matchea `from`/`asunto` → busca plataforma por `name` en BD.
  3. Si nada matchea → devuelve `None`.
- `extract_code_from_body(body, platform?)`:
  1. Usa `platform.code_pattern` si existe en BD.
  2. Fallback: lista de regex:
     - `código/code/otp/pin:NNNN`
     - `[YYYY] es tu código`
     - `tu código de verificación: NNNN`
     - `verification/security code: NNNN`
     - Cualquier `\b\d{6}\b`.

---

## 8. 🌐 WebSocket

- Path: `/api/v1/codes/ws`
- Implementado en `app/api/v1/codes.py` con `ConnectionManager`.
- Mensaje al cliente: `{ "type": "new_code", "data": { id, code, sender, subject, platform_name, email, received_at } }`.
- Cliente (`Dashboard.jsx`): reconnect con backoff de 5 s.

---

## 9. 🚀 Deployment

**Stack costo $0 oficial**: Supabase (DB) + Render (backend) + Cloudflare Pages (frontend con dominio propio).

Setup paso-a-paso en [`docs/07-DEPLOY.md`](07-DEPLOY.md). Resumen ejecutivo:

```bash
# Dev local (SQLite, todo en localhost)
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload
cd frontend && npm install && npm run dev

# Prod ($0)
# 1. Supabase: crear proyecto → copiar DATABASE_URL del pooler (puerto 6543)
# 2. Render: crear Web Service → start command:
#      uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 \
#        --proxy-headers --forwarded-allow-ips="*"
#    + env vars (ver §3.2)
# 3. Cloudflare Pages: conectar repo → build command `npm run build`
#    + env var VITE_API_URL=https://api.tu-dominio.com/api/v1
# 4. Cron externo (cron-job.org cada 14 min, o UptimeRobot cada 5 min) → GET a Render
```

> ⚠️ Gotchas críticos de la stack free (explicados en detalle en `docs/07-DEPLOY.md`):
> - Render free es IPv4-only → usar Supabase pooler **6543**, no directo 5432.
> - Render duerme tras 15 min sin tráfico inbound → cron externo obligatorio.
> - WebSockets aguante ~1-2 min durante cold start → frontend ya tiene reconnect con backoff.

---

## 10. 🧪 Tests (estado actual)

- **Backend**: sin tests automatizados (`pytest` referenciado en README pero no hay archivos).
- **Frontend**: sin tests.
- Pendiente: agregar `pytest` para routers + Playwright para flujos E2E.

---

## 11. 📐 Decisiones técnicas

| Decisión | Por qué | Trade-off |
|----------|---------|-----------|
| SQLite en dev | Cero config para arrancar | Solo single-instance; usar PG para multi. |
| Hash-routing manual | SPA simple, sin necesidad de server config | Menos features que React Router (sin nested). |
| IMAP IDLE (RFC 2177) | Notificaciones push en tiempo real (~1 s). Sin carga de polling. | Requiere `aioimaplib`. Reconexión automática. |
| IMAP IDLE timeout 1680 s | Por defecto 28 min (RFC 2177 máx 29 min). Configurable vía `IMAP_IDLE_TIMEOUT`. | Tras el timeout se re-entra en IDLE automáticamente. |
| Polling legacy | Mantenido vía `POLL_INTERVAL_SECONDS` para retrocompatibilidad. | El poller ya no usa este valor. |
| `account.platform_id nullable` | Permite cuentas multi-plataforma (auto-detect) | Más complejo que 1:1 estricto. |
| Diccionario `PLATFORM_PATTERNS` hardcodeado | Cubre los casos más comunes out-of-the-box | Hay que actualizarlo cuando cambian remitentes. |
| `USERS_DB` en memoria (no BD) | Simple para v1 | Se pierde al reiniciar — fix: mover a tabla `users`. |
| Stack Supabase+Render+CF Pages | Costo $0 con free tiers de los 3 | Limitaciones: 500 MB DB, sleep 15 min en Render, 500 builds/mes en Pages. |
| Supabase pooler (6543) en vez de directo (5432) | Render free es IPv4-only y Supabase quitó IPv4 del directo | Si no, la app no puede conectar a la DB. |
| Cron externo (UptimeRobot) para evitar Render sleep | Render no considera tráfico outbound como "actividad" | Sin esto, el poller IMAP muere cada 15 min de inactividad HTTP. |
