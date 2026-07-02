# Sistema de Códigos de Verificación (VeriCode)

Sistema administrativo tipo ERP para gestionar códigos de verificación de plataformas streaming y IA. Los usuarios pueden solicitar códigos desde una interfaz pública sin necesidad de registrarse, mientras que los administradores gestionan las cuentas de correo y plataformas.

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

> 📘 La guía paso-a-paso del deploy vive en [`docs/07-DEPLOY.md`](sistema-codigos/docs/07-DEPLOY.md). Cubre Supabase + Render + Cloudflare Pages, dominio custom, DNS en Cloudflare, evitar el sleep de Render y bootstrap del admin.

## 📁 Estructura del Proyecto

```
sistema-codigos/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Routers REST
│   │   ├── auth/            # JWT authentication
│   │   ├── db/              # Database session
│   │   ├── models.py        # SQLAlchemy models
│   │   ├── schemas.py       # Pydantic schemas
│   │   └── main.py          # FastAPI app
│   ├── seed.py              # Datos iniciales
│   ├── requirements.txt
│   └── codigos.db           # SQLite (dev)
├── frontend/
│   ├── src/
│   │   ├── components/      # UI reutilizable
│   │   ├── context/         # AuthContext, ToastContext
│   │   ├── pages/           # Vistas principales
│   │   ├── api.js           # Cliente API con JWT
│   │   ├── App.jsx          # Router + providers
│   │   └── index.css        # Design system
│   └── package.json
├── docker-compose.yml       # PostgreSQL
└── README.md
```

## 🚀 Inicio Rápido (Desarrollo)

### Prerrequisitos
- Python 3.11+
- Node.js 18+
- PostgreSQL 16 (opcional, usa SQLite por defecto)

### 1. Backend

```bash
cd sistema-codigos/backend

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno (opcional)
cp .env.example .env  # Editar si usas PostgreSQL

# Inicializar BD y seed
python seed.py

# Iniciar servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend

```bash
cd sistema-codigos/frontend

# Instalar dependencias
npm install

# Iniciar servidor de desarrollo
npm run dev
```

### 3. Con Docker (PostgreSQL local)

```bash
# En la raíz del proyecto
docker-compose up -d

# Configurar .env en backend para usar PostgreSQL:
# DATABASE_URL=postgresql://vericode:vericode_pass@localhost:5432/vericode
```

### 4. Deploy a producción (costo $0)

Stack recomendada: **Supabase (DB) + Render (backend) + Cloudflare Pages (frontend)**.

Ver [`docs/07-DEPLOY.md`](docs/07-DEPLOY.md) para el paso-a-paso completo (Supabase pooler puerto 6543, Render keep-alive con UptimeRobot, Cloudflare Pages con dominio propio).

## 🔐 Acceso al Sistema

### Administrador
- **URL**: `http://localhost:5173/#/login`
- **Usuario**: `admin`
- **Contraseña**: `admin123`

Desde el panel admin puedes:
- **Dashboard**: Ver todos los códigos en tiempo real
- **Correos**: Gestionar cuentas IMAP (agregar/editar/eliminar/probar)
- **Plataformas**: Configurar plataformas streaming/IA

### Usuario Final (Público)
- **URL**: `http://localhost:5173/#/code-request`
- **Sin registro ni login**
- Solo selecciona:
  1. **Correo electrónico** (de la lista de cuentas configuradas por admin)
  2. **Plataforma** (streaming o IA)
- El sistema verifica si hay código disponible y lo muestra

## ⚙️ Configuración

### Variables de Entorno (Backend)
```env
# .env en backend/
APP_NAME="Sistema de Códigos"
# En dev usa SQLite; en prod apuntá al pooler de Supabase
# (puerto 6543, NO 5432 - ver docs/07-DEPLOY.md).
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
npm run preview             # Preview build

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
| Token expirado | Login de nuevo. Token dura 8 horas (configurable) |
| DB locked (SQLite) | Solo una instancia de backend a la vez. Usar PostgreSQL para multi-instancia |

## 📝 Licencia

Proyecto interno - VeriCode System