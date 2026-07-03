# 05 — Backend (Referencia técnica)

> Detalle por archivo: modelos SQLAlchemy, routers FastAPI, servicios.

---

## 1. 📁 Estructura

```
backend/
├── app/
│   ├── main.py              # App FastAPI, lifespan, mounts
│   ├── config.py            # Settings (pydantic-settings, .env)
│   ├── models.py            # SQLAlchemy ORM
│   ├── schemas.py           # Pydantic v2 schemas
│   ├── api/
│   │   └── v1/
│   │       ├── auth.py            # JWT login + setup
│   │       ├── email_accounts.py  # CRUD + test + poll
│   │       ├── platforms.py       # CRUD
│   │       ├── codes.py           # CRUD + stats + WS
│   │       └── public.py          # Endpoints sin auth
│   ├── auth/
│   │   └── auth.py          # bcrypt + JWT helpers
│   ├── db/
│   │   └── database.py      # engine, SessionLocal, Base, get_db
│   └── services/
│       ├── imap_poller.py   # asyncio background task
│       └── code_extractor.py # regex platform + code
├── seed.py                  # Datos iniciales
├── requirements.txt
└── codigos.db               # SQLite (dev) generado al boot
```

---

## 2. ⚙️ Config (`app/config.py`)

```python
class Settings(BaseSettings):
    app_name: str = "Sistema de Códigos de Verificación"
    database_url: str = "sqlite:///./codigos.db"
    secret_key: str = "CHANGE-ME-dev-secret-key-do-not-use-in-production-please"
    fernet_key: str = "<default dev>"          # Ver `app/auth/auth.py`.
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    poll_interval_seconds: int = 30
    cors_origins: str = ""                     # Lista CSV. NUNCA "*" en prod.
    vericode_env: str = "development"          # Cualquier variante de "production" activa guards.
    bootstrap_token: str = ""                  # Requerido en prod para /auth/setup.
    auth_rate_limit_max_attempts: int = 5
    auth_rate_limit_window_minutes: int = 15
    trusted_proxies: str = ""                  # Lista CSV de IPs/CIDRs. "*" permitido.
    real_ip_header: str = "X-Forwarded-For"

    class Config:
        env_file = ".env"
```

Carga desde `.env` si existe. Override por env vars.

### 2.1 Compatibilidad SQLite ↔ PostgreSQL

Las queries usan SQL estándar compatible con ambos motores. La unica exepción es la mini-migracion `_run_user_migrations()` en `app/main.py` que usa `DEFAULT TRUE` (en vez de `DEFAULT 1`) para ser portable a Postgres. En un setup fresh de Supabase, `Base.metadata.create_all` crea todas las columnas y la migración es no-op.

**Importante para producción en Supabase**: usar el **pooler puerto 6543** (no 5432 directo) y agregar `?sslmode=require` al final del DATABASE_URL. Ver `docs/07-DEPLOY.md` §1 para el rationale.

---

## 3. 🗄️ Modelo de datos (`app/models.py`)

### 3.1 Enum types

```python
class EmailType(str, enum.Enum):
    gmail = "gmail"
    outlook = "outlook"
    yahoo = "yahoo"
    custom = "custom"

class ProviderType(str, enum.Enum):
    streaming = "streaming"
    ai = "ai"
    other = "other"
```

### 3.2 Tablas

> En **producción** (Supabase Postgres), todas las tablas usan tipos nativos de Postgres: `Integer` → `INTEGER`, `String(N)` → `VARCHAR(N)`, `Text` → `TEXT`, `Boolean` → `BOOLEAN`, `Enum` → `VARCHAR(N) CHECK (in (...))`. No requiere `Alembic` para el setup fresh; las columnas se crean via `Base.metadata.create_all` en el primer arranque.

#### `email_accounts`

| Column | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| email | String(255) UNIQUE | |
| email_type | Enum(EmailType) | default=`custom` |
| imap_host | String(255) | nullable, autocompleta por tipo |
| imap_port | Integer | default=993 |
| username | String(255) | nullable, default=email |
| password_encrypted | String(1024) | **HOY PLANO** (TODO cifrar) |
| is_active | Boolean | default=True |
| last_checked | DateTime | nullable |
| notes | Text | nullable |
| **platform_id** | Integer FK → platforms.id | **NUEVO**, nullable |
| created_at | DateTime | |
| updated_at | DateTime | onupdate |

Relaciones:
- `codes: VerificationCode[]` (cascade delete-orphan)
- `platform: Platform`

#### `platforms`

| Column | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| name | String(100) UNIQUE | ID lógico ("netflix") |
| display_name | String(100) | nombre mostrado |
| provider_type | Enum(ProviderType) | |
| code_pattern | String(500) | regex para extraer código |
| sender_pattern | String(500) | regex para detectar remitente |
| subject_pattern | String(500) | regex para detectar asunto |
| icon | String(50) | clave de icono / emoji |
| is_active | Boolean | default=True |
| created_at | DateTime | |

#### `verification_codes`

| Column | Tipo | Notas |
|--------|------|-------|
| id | Integer PK | |
| email_account_id | FK email_accounts.id NOT NULL | |
| platform_id | FK platforms.id NULL | |
| sender | String(255) | from del email |
| subject | String(500) | |
| code | String(100) NOT NULL | el código extraído |
| raw_body | Text | primeros 5000 chars |
| is_read | Boolean | default=False |
| is_delivered | Boolean | default=False |
| delivered_to | String(255) | a quién se entregó |
| delivered_at | DateTime | |
| received_at | DateTime NOT NULL | del email |
| created_at | DateTime | |

### 3.3 Diagrama ER

```
┌──────────────────┐         ┌─────────────────┐
│   platforms      │         │  email_accounts │
│   id (PK)        │◄────────┤  id (PK)        │
│   name           │  (N)    │  email          │
│   display_name   │         │  platform_id(FK)│
│   code_pattern   │         │  is_active      │
│   sender_pattern │         │  password_enc   │
│   subject_pattern│         │  ...            │
└────────┬─────────┘         └────────┬────────┘
         │ (1)                       │ (1)
         │                           │
         │       ┌───────────────────┴──┐
         └──────►│  verification_codes  │
                 │  id (PK)             │
                 │  email_account_id FK │
                 │  platform_id FK      │
                 │  code                │
                 │  is_delivered        │
                 │  ...                 │
                 └──────────────────────┘
```

---

## 4. 🔐 Auth (`app/auth/auth.py`)

```python
security = HTTPBearer()

def verify_password(plain, hashed) -> bool: ...
def get_password_hash(password) -> str: ...
def create_access_token(data, expires_delta=None) -> str: ...
def verify_token(token) -> Optional[dict]: ...
def get_current_user(credentials) -> dict: ...
```

- **bcrypt**: nativo `bcrypt.hashpw/.checkpw` con salt autogenerado.
- **JWT**: `python-jose.jwt.encode/decode` HS256 con `SECRET_KEY`.
- **Dependencia**: `Depends(security)` extrae el header `Authorization: Bearer <token>`.

### Endpoint de setup (`app/api/v1/auth.py`)

```python
USERS_DB = {}  # ⚠️ en memoria — mover a BD

@router.get("/setup")
def setup_admin(db):
    if USERS_DB:
        return {"message": "Admin already exists"}
    USERS_DB["admin"] = {
        "username": "admin",
        "password": get_password_hash("admin123"),
        "is_admin": True,
    }
    return {"message": "Admin created: admin / admin123"}
```

⚠️ **Issue conocido**: `USERS_DB` está en memoria → se pierde al reiniciar. Solución propuesta: tabla `users` en BD, y ejecutar el setup automáticamente en `lifespan` solo si la tabla está vacía.

---

## 5. 🌐 Routers

### 5.1 `/api/v1/auth`

| Verbo | Path | Body | Resp |
|-------|------|------|------|
| GET | `/setup` | — | `{message}` |
| POST | `/token` | `{username, password}` | `{access_token, token_type}` |
| GET | `/me` | — | payload del JWT |

### 5.2 `/api/v1/email-accounts` (auth)

| Verbo | Path | Body | Resp |
|-------|------|------|------|
| GET | `/` | — | `[EmailAccountOut]` |
| POST | `/` | `EmailAccountCreate` | `EmailAccountOut` |
| GET | `/{id}` | — | `EmailAccountOut` |
| PUT | `/{id}` | `EmailAccountUpdate` | `EmailAccountOut` |
| DELETE | `/{id}` | — | 204 |
| POST | `/{id}/test` | — | `{message, email}` |
| POST | `/{id}/poll` | — | `{message, email}` |

#### Schemas

```python
class EmailAccountCreate(BaseModel):
    email: str
    email_type: EmailType = EmailType.custom
    imap_host: Optional[str]
    imap_port: int = 993
    username: Optional[str]
    password: str                # ← se guarda como password_encrypted
    notes: Optional[str]
    platform_id: Optional[int]   # ← NUEVO

class EmailAccountUpdate(BaseModel):
    # Todos los campos opcionales
    is_active: Optional[bool]
    platform_id: Optional[int]
    password: Optional[str]      # si presente → password_encrypted

class EmailAccountOut(BaseModel):
    # Sin password (es interno)
    is_active, last_checked, created_at, platform_id
```

### 5.3 `/api/v1/platforms` (auth)

CRUD estándar. `PlatformCreate`, `PlatformUpdate`, `PlatformOut`.

### 5.4 `/api/v1/codes` (auth)

| Verbo | Path | Notas |
|-------|------|-------|
| GET | `/` | Query: `q`, `platform_id`, `email_account_id`, `is_delivered`, `limit`, `offset` |
| GET | `/recent?minutes=N` | últimos N minutos |
| GET | `/stats` | `{total, unread, undelivered, last_hour}` |
| PUT | `/{id}/deliver` | body: `delivered_to` |
| PUT | `/{id}/read` | |
| WS | `/ws` | broadcast `{type: new_code, data: {...}}` |

### 5.5 `/api/v1/public` (sin auth)

| Verbo | Path | Notas |
|-------|------|-------|
| GET | `/email-accounts` | solo `is_active=true`, sin password |
| GET | `/platforms` | solo `is_active=true`, sin detalles internos |
| GET | `/verify-email-access` | query: `email`, `platform_name` → devuelve código o 404 |
| POST | `/request-code` | query: `email`, `platform_name` → mismo comportamiento |

> ⚠️ Estos endpoints filtran intencionalmente para no exponer `password_encrypted`, `raw_body`, ni datos de admin.

---

## 6. 🤖 Servicios

### 6.1 `IMAPPoller` (`app/services/imap_poller.py`)

```python
class IMAPPoller:
    def __init__(self):
        self.running = False
        self.connections: dict[int, imaplib.IMAP4_SSL] = {}
        self.callbacks = []
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None

    # ── Lifecycle ──
    async def start(self, interval: int = 30):
        self._main_loop = asyncio.get_running_loop()
        while self.running:
            await self.run_once()
            await asyncio.sleep(interval)

    def stop(self): self.running = False

    # ── Per-account ──
    def connect_account(self, account) -> Optional[imaplib.IMAP4_SSL]:
        # autocompleta host según email_type
        # retorna None si falla

    def fetch_unread(self, mail) -> list[dict]:
        # busca últimos 10 UNSEEN, marca como Seen
        # devuelve [{sender, subject, body, date, uid}]

    def process_account(self, account_id, db):
        # 1. connect
        # 2. fetch
        # 3. logout
        # 4. for msg: account.platform ?? guess_platform; extract_code
        # 5. INSERT si no existe (dedup por email_account_id+code+subject)
        # 6. _notify_new_code_threadsafe

    # ── Notificación ──
    def _notify_new_code_threadsafe(self, code, db):
        # usa asyncio.run_coroutine_threadsafe con self._main_loop
        # garantiza que el callback corre en el event loop principal
```

### 6.2 `code_extractor` (`app/services/code_extractor.py`)

#### `guess_platform(sender, subject, platforms) -> Optional[Platform]`

Lógica de detección (orden de prioridad):

1. **`platform.sender_pattern` BD** → `re.search(pattern, sender, IGNORECASE)`.
2. **`platform.subject_pattern` BD** → `re.search(pattern, subject, IGNORECASE)`.
3. **Diccionario `PLATFORM_PATTERNS` hardcodeado** → match entre `sender in lower` o `subject in lower`. Si matchea `key`, busca plataforma con `name == key` en `platforms[]`.
4. **Si nada matchea** → devuelve `None` (NO crea Platform huérfano).

#### `extract_code_from_body(body, platform?) -> Optional[str]`

1. Si `platform.code_pattern` está definido → usarlo.
2. Fallback → lista de regex:
   - `(?:código|code|otp|pin)\s*:\s*(\d{4,8})`
   - `(\d{4,8})\s*(?:es|is)\s*t[uú]\s*(?:código|code)`
   - `t[uú]\s*(?:código de verificación|código|code)\s*:\s*(\d{4,8})`
   - `(?:verification|security)\s*code\s*:\s*(\d{4,8})`
   - `\b(\d{6})\b` (genérico 6 dígitos)

---

## 7. 🔄 Lifespan (`app/main.py`)

```python
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(bind=engine)
    seed_platforms()              # idempotente
    poller.on_new_code(broadcast_new_code_handler)
    await poller.start()
    yield
    poller.stop()
```

`poller.start()` crea una tarea asyncio por cada cuenta activa que mantiene una conexión IMAP IDLE persistente usando `aioimaplib`. Cuando el servidor notifica un nuevo correo (push), el watcher extrae el código, lo guarda en BD y lo emite vía WebSocket. Esto elimina la necesidad de sondear cada N segundos.

---

## 8. 🛠️ Comandos útiles

```bash
cd backend

# Inicializar
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python seed.py

# Arrancar dev
uvicorn app.main:app --reload --port 8000

# Arrancar con PG local (docker-compose)
DATABASE_URL=postgresql://vericode:vericode_pass@localhost:5432/vericode \
  uvicorn app.main:app --reload --port 8000

# Arrancar apuntando a Supabase (pooler 6543 obligatorio)
DATABASE_URL='postgresql://postgres.[ref]:[pw]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require' \
  uvicorn app.main:app --reload --port 8000

# Formato / lint (opcionales)
black app/ && flake8 app/ && isort app/ && mypy app/
```

---

## 9. 🔌 CORS

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # ⚠️ restringir en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 10. ⚠️ Issues & mejoras

Ver `06-PLAN.md` para el backlog completo. Resumen:

- `password_encrypted` plano → cifrar.
- `USERS_DB` en memoria → tabla `users`.
- `USERS_DB["admin"]` no se auto-crea → ejecutar setup en `lifespan`.
- Listener WS no autentica → cualquiera con la URL se conecta → restringir por token en `?token=` query.
- `api.setup.validateImap` en frontend apunta a endpoint inexistente → eliminar.
