# VeriCode — Sistema de Códigos de Verificación

Sistema administrativo tipo ERP para gestionar códigos de verificación de plataformas streaming y IA. Los usuarios pueden solicitar códigos desde una interfaz pública sin necesidad de registrarse, mientras que los administradores gestionan las cuentas de correo y plataformas.

> **Repositorio liviano.** Este repo **NO** incluye dependencias instaladas ni artefactos generados: `backend/venv/`, `frontend/node_modules/`, `frontend/dist/`, `*.db`, `__pycache__/`, etc. se regeneran con los comandos de abajo. Por eso pesa pocos MB y se sube fácil a GitHub.

## ⚡ Instalación rápida (TL;DR)

### Prerrequisitos
- Python **3.11+**
- Node.js **20+** (lo requiere Vite 8)
- (Opcional) PostgreSQL 16 — si no, usa SQLite que ya viene configurado

### 1. Backend

```bash
cd backend

# Crear entorno virtual
python -m venv venv
source venv/bin/activate           # Linux / macOS
# venv\Scripts\activate            # Windows (PowerShell o CMD)

# Instalar dependencias (~120 MB)
pip install -r requirements.txt

# (Opcional) Configurar variables de entorno
cp .env.example .env               # editar solo si vas a usar PostgreSQL

# Sembrar la base de datos con datos de prueba
python seed.py

# Levantar el servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend (en otra terminal)

```bash
cd frontend

# Instalar dependencias (~80 MB)
npm install

# Levantar el dev server
npm run dev
```

Abrí <http://localhost:5173> (frontend) y la API queda expuesta en <http://localhost:8000>.

### 3. Accesos por defecto

| Rol | URL | Usuario | Contraseña |
|---|---|---|---|
| Admin | `http://localhost:5173/#/login` | `admin` | `admin123` |
| Usuario público | `http://localhost:5173/#/code-request` | — | — |

Desde el panel admin podés:
- **Dashboard**: Ver todos los códigos en tiempo real.
- **Correos**: Gestionar cuentas IMAP (agregar, editar, eliminar y probar conexión).
- **Plataformas**: Configurar plataformas streaming/IA y los patrones de detección de códigos.

### 4. (Opcional) Docker Compose para PostgreSQL local

```bash
docker-compose up -d
# y en backend/.env:
# DATABASE_URL=postgresql://vericode:vericode_pass@localhost:5432/vericode
```

---

## 🏗️ Arquitectura

- **Backend**: FastAPI + SQLAlchemy + PostgreSQL (prod) / SQLite (dev)
- **Frontend**: React 19 + Vite 8 + React Router 7
- **Auth**: JWT (python-jose + bcrypt) + Fernet para credenciales IMAP
- **Email**: IMAP polling automático cada 30s

### 🚀 Stack de despliegue (costo $0)

| Servicio | Uso | Tier |
|----------|-----|------|
| **[Supabase](https://supabase.com)** | PostgreSQL managed | Free (500 MB, pausa tras 1 semana) |
| **[Render](https://render.com)** | Backend FastAPI | Free Web Service (512 MB, duerme tras 15 min) |
| **[Cloudflare Pages](https://pages.cloudflare.com)** | Frontend estático + dominio propio | Free (ilimitado bandwidth) |

> 📘 La guía paso-a-paso del deploy vive en [`docs/07-DEPLOY.md`](docs/07-DEPLOY.md). Cubre Supabase + Render + Cloudflare Pages, dominio custom, DNS en Cloudflare, evitar el sleep de Render y bootstrap del admin.

## 📁 Estructura del Proyecto

```
.
├── .github/                 # Workflows de GitHub Actions
├── .agents/                 # Skills para agentes IA (Codebuff)
├── CLAUDE.md                # Contexto para asistentes IA (no es docs de usuario)
├── backend/                 # FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── api/v1/          # Routers REST: auth · codes · email_accounts · platforms · public
│   │   ├── auth/            # JWT auth + dependencies
│   │   ├── core/            # Cross-cutting: cache, headers
│   │   ├── db/              # Sesión y engine de SQLAlchemy
│   │   ├── services/        # Lógica de negocio:
│   │   │                    #   imap_poller · code_extractor · rate_limit
│   │   ├── config.py        # Settings (env vars)
│   │   ├── models.py        # Modelos SQLAlchemy
│   │   ├── schemas.py       # Schemas Pydantic
│   │   └── main.py          # App FastAPI + routers + CORS
│   ├── tests/               # E2E + unit (cache, production guards)
│   ├── scripts/             # Paquete Python para scripts auxiliares
│   ├── .env.example         # Plantilla de variables de entorno (copiar a .env)
│   ├── seed.py              # Datos iniciales de la BD
│   ├── _launch_e2e.py       # Helper para lanzar backend en modo E2E
│   └── requirements.txt
├── frontend/                # React 19 + Vite 8 + React Router 7
│   ├── src/
│   │   ├── components/      # Reutilizables: CodeCard, Navbar, Marquee,
│   │   │                    #   LogoSphere, WavyText, ScrollReveal, Loading
│   │   ├── context/         # AuthContext · ToastContext
│   │   ├── pages/           # Vistas: Dashboard · AccountsPage · PlatformsPage ·
│   │   │                    #   LandingPage · LoginPage · ChangePasswordPage ·
│   │   │                    #   PublicCodeRequestPage
│   │   ├── assets/          # Recursos estáticos
│   │   ├── api.js           # Cliente API con JWT (apiFetch)
│   │   ├── App.jsx          # Router + providers
│   │   ├── main.jsx         # Entry point
│   │   └── index.css        # Design system (custom properties)
│   └── package.json
├── docs/                    # Documentación del proyecto
│   ├── 00-INDICE.md         # Índice general
│   ├── 01-PRD.md            # Product Requirements
│   ├── 02-TRD.md            # Technical Requirements
│   ├── 03-UI-UX.md          # Diseño UI/UX y design system
│   ├── 04-FLUJO.md          # Flujos de usuario y admin
│   ├── 05-BACKEND.md        # Arquitectura backend
│   ├── 06-PLAN.md           # Plan de implementación
│   ├── 07-DEPLOY.md         # Deploy (Supabase + Render + Cloudflare)
│   └── 08-CACHING.md        # Estrategia de caché
├── docker/                  # Dockerfiles auxiliares
├── opencode-skills/         # Skills y templates (dev tooling)
├── docker-compose.yml       # PostgreSQL local (desarrollo)
├── .gitignore
└── README.md
```

> 🛡️ **Archivos excluidos del repo** (regenerables con `pip install` y `npm install`): `backend/venv/`, `backend/codigos.db`, `frontend/node_modules/`, `frontend/dist/`, `__pycache__/`, `*.pyc`, `*.log`. Ver `.gitignore` para la lista completa.

## 📡 API Endpoints Principales

### Públicos (sin auth)

```
GET  /api/v1/public/email-accounts    # Lista correos activos
GET  /api/v1/public/platforms         # Lista plataformas activas
POST /api/v1/public/request-code      # Solicitar código (email + platform)
GET  /api/v1/public/verify-email-access  # Verificar acceso
```

### Admin (requiere JWT)

```
POST   /api/v1/auth/token             # Login
GET    /api/v1/email-accounts         # CRUD cuentas
GET    /api/v1/platforms              # CRUD plataformas
GET    /api/v1/codes                  # Listar/filtrar códigos
GET    /api/v1/codes/recent           # Últimos N minutos
GET    /api/v1/codes/stats            # Estadísticas
PUT    /api/v1/codes/{id}/deliver     # Marcar entregado
PUT    /api/v1/codes/{id}/read        # Marcar leído
WS     /api/v1/codes/ws               # WebSocket tiempo real
```

## 🔄 Flujo de Trabajo

```
1. Admin agrega cuenta de correo (IMAP) + plataformas
2. Poller escanea emails cada 30s automáticamente
3. Usuario entra a /code-request
4. Selecciona su correo + plataforma
5. Sistema busca código no entregado para esa combinación
6. Si existe → muestra código al usuario
7. Código marcado como "entregado" (opcional)
```

## ⚙️ Configuración

### Variables de Entorno (Backend)

```env
# backend/.env
APP_NAME="Sistema de Códigos"
# En dev usa SQLite; en prod apuntá al pooler de Supabase
# (puerto 6543, NO 5432 — ver docs/07-DEPLOY.md).
DATABASE_URL=sqlite:///./codigos.db
# DATABASE_URL=postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require
SECRET_KEY=cambiar-en-produccion-clave-segura
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
POLL_INTERVAL_SECONDS=30
```

### Cuentas de Correo (Admin)
El admin debe configurar en **Correos**:
- Email y contraseña de la cuenta IMAP
- Tipo: Gmail / Outlook / Yahoo / Personalizado
- Servidor IMAP y puerto (auto-completado por tipo)
- La cuenta debe tener **IMAP habilitado** y **contraseña de aplicación** (no la principal)

### Plataformas
Pre-configuradas: Netflix, Disney+, HBO Max, Prime Video, Spotify, ChatGPT, Claude, Midjourney
- Patrones de remitente/asunto para detectar emails
- Regex para extraer códigos (default: 6 dígitos)

## 🛠️ Comandos Útiles

```bash
# Backend
cd backend
python seed.py              # Re-ejecutar seed
python -m pytest            # Tests (si existen)
black app/                  # Formatear código
flake8 app/                 # Lint

# Frontend
cd frontend
npm run build               # Build producción
npm run lint                # ESLint
npm run preview             # Preview del build

# Docker
docker-compose up -d        # Levantar PostgreSQL
docker-compose down         # Parar
docker-compose logs -f db   # Ver logs DB
```

## 🎨 Personalización

### Colores (CSS Variables en `frontend/src/index.css`)

```css
:root {
  --brand: #2563eb;
  --brand-hover: #1d4ed8;
  --ink: #111827;
  --cream: #fafafa;
  --gold: #f59e0b;
  --success: #10b981;
  --danger: #ef4444;
}
```

### Agregar Plataforma
1. Admin → Plataformas → Nueva
2. Nombre único (ej: `crunchyroll`)
3. Display name: `Crunchyroll`
4. Tipo: `streaming` / `ai` / `other`
5. Patrones opcionales: sender, subject, código regex

## 🐛 Troubleshooting

| Problema | Solución |
|----------|----------|
| IMAP connection failed | Verificar contraseña de aplicación, no la principal. Gmail: https://myaccount.google.com/apppasswords |
| No llegan códigos | Revisar que la cuenta tenga IMAP habilitado y emails no leídos en INBOX |
| CORS error | Backend permite `*` en desarrollo. En producción configurar `allow_origins` específico |
| Token expirado | Login de nuevo. Token dura ~1 h por defecto (configurable vía `ACCESS_TOKEN_EXPIRE_MINUTES` en `.env`) |
| DB locked (SQLite) | Solo una instancia de backend a la vez. Usar PostgreSQL para multi-instancia |
| **GitHub rechaza el push por tamaño** | Asegurate de no haber arrastrado `venv/` o `node_modules/`. El `.gitignore` ya los excluye. Para regenerar: `pip install -r requirements.txt` y `npm install`. |

## 📝 Licencia

Proyecto interno — VeriCode System.
# VeriCode
