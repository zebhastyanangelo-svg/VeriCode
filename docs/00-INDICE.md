# 📚 Documentación VeriCode — Índice General

> Sistema administrativo ERP para extracción y entrega de códigos de verificación de plataformas streaming e IA.

---

## 📂 Documentos

| # | Documento | Descripción |
|---|-----------|-------------|
| 01 | [PRD](./01-PRD.md) | **Product Requirements Document** — Visión de negocio, usuarios, objetivos, alcance. |
| 02 | [TRD](./02-TRD.md) | **Technical Requirements Document** — Stack, arquitectura, infraestructura, decisiones técnicas. |
| 03 | [UI/UX](./03-UI-UX.md) | Sistema de diseño, wireframes, flujos de pantalla, paleta de colores, accesibilidad. |
| 04 | [Flujo](./04-FLUJO.md) | Flujos de usuario end-to-end: admin, usuario público, ciclo del código. |
| 05 | [Backend](./05-BACKEND.md) | Modelo de datos, endpoints, servicios, autenticación, IMAP poller. |
| 06 | [Plan](./06-PLAN.md) | Plan de implementación priorizado, issues conocidos, backlog. |
| 07 | [Deploy](./07-DEPLOY.md) | **Despliegue en producción** — stack $0 Supabase + Render + Cloudflare Pages. |

---

## 🎯 Resumen ejecutivo (TL;DR)

**VeriCode** es un sistema que:

1. **Recibe** códigos de verificación vía correos IMAP (Gmail, Outlook, etc.).
2. **Procesa** en tiempo real mediante conexiones IMAP IDLE persistentes, extrayendo el código (regex) y asociándolo a su plataforma.
3. **Entrega** el código al usuario final mediante una URL pública sin login.

**Casos de uso principales**:
- Un cliente necesita el código de Netflix que llegó a su casilla → entra a `/#/code-request`, ingresa su email + selecciona Netflix → recibe el código.
- El admin configura qué casillas IMAP se monitorean y qué plataformas se reconocen (`Plataformas`).
- El dashboard muestra todos los códigos en tiempo real vía WebSocket.

---

## 🔑 Credenciales por defecto (solo dev)

| Rol | Usuario | Contraseña |
|-----|---------|------------|
| Admin | `admin` | `admin123` |

> ⚠️ Cambiar en producción. El setup debe ejecutarse la primera vez (`GET /api/v1/auth/setup` o vía seed).

---

## 🗺️ Stack

### Código (este repo)

```
┌──────────────────────────────────────────────┐
│  Frontend (React 19 + Vite 8 + FontAwesome)   │
├──────────────────────────────────────────────┤
│  Backend (FastAPI 0.138 + SQLAlchemy 2.0)     │
│  ├─ IMAP IDLE Watcher (aioimaplib, push)        │
│  ├─ JWT Auth (bcrypt + HS256 + must_change)    │
│  └─ WebSocket /codes/ws                        │
├──────────────────────────────────────────────┤
│  DB: SQLite (dev/test) / PostgreSQL 16 (prod)  │
└──────────────────────────────────────────────┘
```

### Deploy (costo $0)

| Servicio | Rol | Tier |
|----------|-----|------|
| **Cloudflare Pages** | Frontend estático + dominio propio | Free (500 builds/mes, bandwidth ilimitado) |
| **Render** | Backend FastAPI | Free Web Service (512 MB, duerme tras 15 min sin tráfico inbound) |
| **Supabase** | PostgreSQL managed | Free (500 MB, pausa tras 1 semana sin actividad) |

> 📘 Setup paso-a-paso en [`docs/07-DEPLOY.md`](07-DEPLOY.md). Gotchas críticos: Render free tier es IPv4-only (usar Supabase pooler puerto **6543**, no 5432), y Render duerme por inactividad HTTP (el frontend hace ping cada 5 min + cron externo opcional para evitarlo).

---

## 📝 Estado actual del proyecto

| Aspecto | Estado | Notas |
|---------|--------|-------|
| backend (API + DB) | ✅ Funcional | Modelos, schemas, CRUD completos |
| IMAP IDLE Watcher | ✅ Funcional | aioimaplib, conexiones persistentes, push en tiempo real |
| Auth JWT | ✅ Funcional | Admin user se crea con `GET /auth/setup` |
| Frontend admin | ✅ Funcional | Login, Dashboard, Cuentas, Plataformas |
| Frontend público | ✅ Funcional | `/#/code-request` público, input email + select plataforma |
| Detección plataforma | ✅ Mejorada | Estrategia primaria: `account.platform_id`, fallback: regex |
| Auto-docs (Swagger) | ✅ `/docs` | Habilitado por FastAPI |

---

## 🚀 Quickstart

```bash
# Backend
cd sistema-codigos/backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python seed.py
uvicorn app.main:app --reload --port 8000

# Frontend
cd sistema-codigos/frontend
npm install
npm run dev
```

- Admin → http://localhost:5173/#/login  (`admin` / `admin123`)
- Público → http://localhost:5173/#/code-request  *(requiere fix en App.jsx)*
- API docs → http://localhost:8000/docs
