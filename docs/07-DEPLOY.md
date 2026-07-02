# Despliegue en Producción

> **Stack oficial (costo $0/mes):**
> - **Cloudflare Pages** — frontend estático + dominio propio
> - **Render** — backend FastAPI
> - **Supabase** — PostgreSQL managed
>
> 📘 Setup paso-a-paso abajo. Para dev local con SQLite, ver `README.md`.

---

## 1. TL;DR

```text
┌────────────────────────────────────────────────────────────────────┐
│  Usuario final ──DNS──▶ Cloudflare Pages ──HTTPS──▶ Tu Frontend     │
│  (https://app.tu-dominio.com)            ↘ VITE_API_URL baked         │
│                                              ▼                       │
│                                          Render (FastAPI)            │
│                                          (https://api.onrender.com)  │
│                                              ▼                       │
│                                          Supabase Pooler (6543)       │
│                                          (datos en Postgres)          │
└────────────────────────────────────────────────────────────────────┘
```

**Por qué este stack**:
- ✅ **Cero costo** con free tiers.
- ✅ **SSL automático** en los 3 servicios (Cloudflare, Render, Supabase).
- ✅ **Dominio propio** vía Cloudflare.
- ✅ **Postgres managed** sin运维.

**Limitaciones a aceptar**:
- ⚠️ Render free duerme tras 15 min sin tráfico inbound (cron externo obligatorio).
- ⚠️ Supabase free pausa tras 1 semana de inactividad (menos probable si Render está activo).
- ⚠️ 500 MB DB / 5 GB egress/mes (Supabase).
- ⚠️ 512 MB RAM / 750 instance-hours/mes (Render).
- ⚠️ 1 build concurrente en Cloudflare Pages.

---

## 2. Setup paso-a-paso

### 2.1. Supabase (Base de datos)

1. **Crear cuenta y proyecto**
   - Ir a https://supabase.com → New project.
   - Region: elegir la más cercana a Render (ej: `us-east-1` si Render está en US East).
   - Anotar el **database password** que generes.

2. **Copiar la URL del pooler (puerto 6543)** ⚠️
   - Project Settings → Database → Connection string → "Transaction pooler" (no "Direct connection").
   - Formato: `postgresql://postgres.[ref]:[tu-password]@aws-0-[region].pooler.supabase.com:6543/postgres`

3. **CRÍTICO: por qué puerto 6543 y no 5432**?
   - Supabase quitó **IPv4 del puerto directo 5432** (solo IPv6).
   - Render free tier **NO tiene salida IPv6** (es IPv4-only).
   - Si usás 5432, tu app no puede conectar a la DB al desplegar.
   - El pooler 6543 acepta IPv4 + maneja hasta 200 conexiones concurrentes (suficiente para 1 instancia de FastAPI).

4. **Agregar `?sslmode=require` al final de la URL** (Supabase requiere SSL).

   URL final para Render:
   ```
   postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require
   ```

5. (Opcional) Crear las tablas via el SQL editor de Supabase — **NO recomendado**. En nuestro caso, `Base.metadata.create_all` corre al primer arranque del backend y crea todo idempotentemente.

### 2.2. Render (Backend)

1. **Crear Web Service**
   - New → Web Service → conectar repo GitHub (`sistema-codigos`).
   - Root directory: `backend`.
   - Environment: **Python 3** (Render detecta `requirements.txt` automáticamente).
   - Build command: `pip install --upgrade pip && pip install -r requirements.txt`
   - Start command:
     ```bash
     uvicorn app.main:app \
       --host 0.0.0.0 \
       --port $PORT \
       --workers 1 \
       --proxy-headers \
       --forwarded-allow-ips="*"
     ```
   - Region: misma que Supabase para minimizar latencia entre Render y DB.

2. **Setear las variables de entorno** (Environment → Add environment variable):

   | Variable | Valor |
   |----------|-------|
   | `VERICODE_ENV` | `production` |
   | `DATABASE_URL` | `postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres?sslmode=require` |
   | `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(64))"` |
   | `FERNET_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
   | `BOOTSTRAP_TOKEN` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
   | `CORS_ORIGINS` | `https://app.tu-dominio.com,https://app.tu-dominio.onrender.com` |
   | `TRUSTED_PROXIES` | `*` |
   | `POLL_INTERVAL_SECONDS` | `30` |
   | `AUTH_RATE_LIMIT_MAX_ATTEMPTS` | `5` |
   | `AUTH_RATE_LIMIT_WINDOW_MINUTES` | `15` |
   | `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` |

3. **Deploy**: hacer push o "Manual Deploy". En los logs deberías ver:

   ```
   ────────────────────────────────────────
     VeriCode arrancando en modo: PRODUCCIÓN
     CORS origins: 2 orígenes
     Bootstrap token: set
     Rate-limit /auth/token: 5 intentos / 15 min
     JWT expiración: 60 min
     ⚠️  Modo producción — todas las safeguards activas.
   ────────────────────────────────────────
   ```

   Si ves `RuntimeError ARRANQUE BLOQUEADO`, alguna env var crítica está vacía/default. Ver "Troubleshooting" §5.

### 2.3. Cloudflare Pages (Frontend)

1. **Crear proyecto**
   - Workers & Pages → Create application → Pages → Connect to Git.
   - Seleccionar el repo `sistema-codigos`.

2. **Configurar build**
   - Project name: `vericode` (o lo que prefieras) → resultado: `vericode.pages.dev`.
   - Production branch: `main`.
   - **Root directory**: `frontend`  ← setear esto evita el `cd` en el comando.
   - **Build command**: `npm run build`   (Vite + oxlint ya están en `package.json`).
   - **Build output directory**: `dist`    (relativo al Root directory).

3. **Setear `VITE_API_URL`** (Settings → Environment variables):
   - Production: `https://api.tu-dominio.com/api/v1` (si agregaste custom domain a Render)
   - Preview (opcional): `https://vericode-backend-pr-xyz.onrender.com/api/v1`

   Vite lee cualquier variable prefijada con `VITE_` en build-time y la inyecta estática al bundle. No requiere cambio en `package.json` ni en el build command.

4. **First deploy**: el primer build tarda ~2 min. Una vez listo, Cloudflare te asigna un dominio `*.pages.dev` automáticamente.

### 2.4. Custom domain (dominio propio)

**Opción A — Dominio en Cloudflare** (recomendado):
1. **Frontend**: Cloudflare Pages → Custom domains → Set up a custom domain → `app.tu-dominio.com`. Cloudflare configura el CNAME automáticamente porque tu dominio ya está en su DNS.
2. **Backend**: Render ya te da un domínio `*.onrender.com` por defecto. Para `api.tu-dominio.com`:
   - Render dashboard → Settings → Custom domain → `api.tu-dominio.com`.
   - Cloudflare DNS → agregar CNAME `api` → `vericode-backend.onrender.com` (Cloudflare proxy ON = orange cloud).
   - Render emite cert Let's Encrypt automáticamente.

**Opción B — Dominio en otro registrar** (GoDaddy, Namecheap, etc.):
- Agregar records en su panel DNS:
  - `app.tu-dominio.com` CNAME → `vericode.pages.dev`
  - `api.tu-dominio.com` CNAME → `vericode-backend.onrender.com`
- El cert SSL lo emite Cloudflare Pages y Render respectivamente (no necesitás Let's Encrypt manual).

---

## 3. Cron keep-alive (CRÍTICO para Render free)

Por defecto, Render apaga tu Web Service tras **15 minutos sin tráfico HTTP inbound**. Como nuestro IMAP poller hace conexiones outbound (IMAP, Supabase), Render no las considera actividad y el proceso muere. Esto interrumpe:
- Recepción de códigos (poller parado).
- WebSockets activos (clientes desconectados).

**Solución**: un cron externo que haga GET a tu backend cada 14 minutos.

### 3.1. cron-job.org (recomendado — granularidad de 1 min)

1. Crear cuenta en https://cron-job.org (free, sin límite práctico de jobs).
2. Create cronjob:
   - URL: `https://api.tu-dominio.com/api/v1/public/email-accounts` (cualquier endpoint público sirve como probe).
   - Interval: every **14 minutes** (cron-job.org sí permite intervalos impares en el free tier).
3. El cron pingea tu backend cada 14 min → Render nunca duerme → poller IMAP siempre vivo.

### 3.2. UptimeRobot (alternativa — solo intervalos fijos)

1. Crear cuenta en https://uptimerobot.com (free, 50 monitores).
2. Add Monitor → HTTP(s).
   - URL: igual a la de arriba.
   - Monitoring Interval: **5 minutes** (⚠️ el free tier NO permite 14 min — solo 5/15/30/45/60). **Nunca elegir 15**: coincide exacto con el sleep boundary de Render y genera race condition.
3. Margen seguro sin tocar el tier sleep.

### 3.3. Por qué NO usar el dashboard de Render / GitHub Actions

- **Render cron jobs**: ya no son gratis (plan paid).
- **GitHub Actions**: el intervalo mínimo es cada 5 min y corre en sus servers (cold start ocasional). Funcional pero menos control.

---

## 4. Cross-service integration

### 4.1. CORS

| Origen | Permitido? | Variable |
|--------|-----------|----------|
| `https://app.tu-dominio.com` (Cloudflare Pages) | ✅ | `CORS_ORIGINS` |
| `https://vericode-frontend.pages.dev` (fallback) | ✅ | `CORS_ORIGINS` |
| `http://localhost:5173` (dev) | ✅ | `CORS_ORIGINS` |
| Cualquier otro origen | ❌ | Backend rechaza con CORS error |

`VITE_API_URL` en Cloudflare Pages debe apuntar al backend con protocolo `https://` (no `http://`).

### 4.2. Reverse proxy (`--proxy-headers`)

Render pone un load balancer delante de tu proceso uvicorn. El LB setea `X-Forwarded-For` con la IP real del cliente. Por eso necesitamos:

- uvicorn: `--proxy-headers --forwarded-allow-ips="*"` (confiar en cualquier IP upstream porque solo Render puede llegar a tu proceso).
- backend: `TRUSTED_PROXIES=*` (desactivar el segundo filtro de FastAPI — es redundante).

**¿Es seguro?** Sí, porque el puerto de uvicorn NO es accesible directamente desde internet. Render cierra ese puerto y todo el tráfico inbound pasa forzosamente por su LB.

### 4.3. WebSockets y cold starts

- **Cold start típico**: ~1 min cuando Render "despierta" tras sleep.
- Durante este tiempo, los WS conectados fallan.
- El frontend ya implementa **reconnect con backoff** (cliente hace retry cada 5 s).
- Action item: si querés experiencia sin cold starts, pagá Render Starter ($7/mes) o usá un always-on service.

---

## 5. Bootstrap del primer admin

Una vez deployado y healthy, hay que crear el admin inicial:

```bash
curl -X POST https://api.tu-dominio.com/api/v1/auth/setup \
  -H "Content-Type: application/json" \
  -H "X-Bootstrap-Token: <tu-BOOTSTRAP_TOKEN>" \
  -d '{
    "username": "admin",
    "password": "<password seguro de 12+ chars>",
    "is_admin": true
  }'
```

(O directamente desde la UI del frontend, que tendrá un form de bootstrap si la tabla `users` está vacía.)

Al primer login, el sistema fuerza cambio de password (`must_change_password=True`). En producción no hay auto-seed de admin — tenés que llamar a este endpoint.

---

## 6. Checklist pre-launch

| # | Check | Cómo verificar |
|---|-------|----------------|
| 1 | `VERICODE_ENV=production` en Render | Ver env vars del Web Service |
| 2 | `SECRET_KEY` no es default | Lo generás con `secrets.token_urlsafe(64)` |
| 3 | `FERNET_KEY` válida de Fernet | Lo generás con `Fernet.generate_key()` |
| 4 | `BOOTSTRAP_TOKEN` no vacío | Lo generás con `secrets.token_urlsafe(32)` |
| 5 | `CORS_ORIGINS` no es `*` ni vacío | Lista explícita de tu dominio |
| 6 | `DATABASE_URL` apunta a Supabase pooler 6543 | `psql 'postgresql://...pooler.supabase.com:6543/postgres?sslmode=require'` (URL entre comillas simples porque tiene `?` y `&`) |
| 7 | `TRUSTED_PROXIES=*` | En Render con LB, confia en todas las upstream |
| 8 | Uvicorn con `--proxy-headers --forwarded-allow-ips="*"` | Start command de Render |
| 9 | UptimeRobot ping cada 14 min | Dashboard de UptimeRobot |
| 10 | Frontend `VITE_API_URL=https://...` | Cloudflare Pages env vars |

Si TODO está ✓, los logs de Render te muestran:
```
VeriCode arrancando en modo: PRODUCCIÓN
✅ 10 plataformas creadas
```

Si falta algo, verás un `RuntimeError` con mensaje claro de qué variable falta.

---

## 7. Limitaciones conocidas y upgradepath

### 7.1. Single-instance only (rate-limit + WS + poller)

El rate-limit, el ConnectionManager del WS y el IMAP poller son **in-memory**. Render free corre 1 instancia pero si en el futuro escalás a 2+ workers, cada proceso tendrá su propio bucket y se rompe el rate-limit.

| Componente | Estado actual | Migración cuando escales |
|---|---|---|
| Rate-limit `/auth/token` | dict + Lock en proceso | Redis (Upstash free tier) |
| WS broadcast | lista en memoria | Redis pub/sub o NATS |
| IMAP poller | asyncio task en proceso | Designar worker específico con `--role=poller` |

**Upgradepath cuando necesites más**:
- Render Starter ($7/mes): no duerme, 512 MB → 2 GB RAM configurable.
- Supabase Pro ($25/mes): 8 GB DB, no pausa, backups automáticos.
- Upstash Redis (free tier): 10k cmd/día, suficiente para rate-limit compartido.
- Cloudflare Pages sigue siendo free (ilimitado).

### 7.2. IMAP sin backoff exponencial

Si una cuenta IMAP rechaza conexión (CUPS, ISP throttling), el poller reintenta cada 30 s sin escalonar. No es crítico en free tier (10 cuentas < 100 emails/día fácil), pero en Producción real conviene agregar backoff por cuenta.

### 7.3. JWT sin refresh tokens

Access token expira a 60 min → usuario debe re-loginear. Para mejor UX, sumar refresh token en cookie httpOnly con rotación. Documentado en `docs/06-PLAN.md` #17.

### 7.4. No hay healthcheck dedicado

`/api/v1/auth/me` sirve como probe (responde 401 si está vivo). Si necesitás algo LB-friendly, sumá un endpoint `/api/v1/health` público.

---

## 8. Monitoreo & alertas

- **Render**: actividad del Web Service, métricas de CPU/RAM en el dashboard.
- **Cloudflare**: Analytics del Pages project (requests, bandwidth, builds).
- **Supabase**: Database health, queries lentas, en el dashboard.
- **UptimeRobot**: te avisa por email si el backend cae.

Recomendado: configurar alertas de email/Slack en UptimeRobot para downtime del backend. Si bajás más de 5 min, sabés que algo está mal.

---

## 9. Resumen del deploy

```
$0/mes total (mientras no superes límites)
├── Cloudflare Pages     → $0       (free, dominio custom incluido)
├── Render Web Service   → $0       (free, duerme, requiere cron)
├── Supabase PostgreSQL   → $0       (free, 500 MB, pausa tras 1 semana)
└── UptimeRobot          → $0       (free, 50 monitores)
```

Upgrade cuando empieces a pegar límites:
- $7/mes Render Starter → backend no duerme, 2 GB RAM.
- $25/mes Supabase Pro → DB 8 GB, sin pausa, backups.
- **Total ≤ $32/mes** = setup de producción profesional.
