# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

**MenuGran PWA** — Aplicación de gestión administrativa tipo ERP con menú digital para restaurante. Consiste en un backend FastAPI + frontend React/Vite (también migrado a Next.js PWA).

## Stack

- **Backend**: Python 3.14, FastAPI 0.115, SQLAlchemy 2.0, SQLite/PostgreSQL
- **Frontend**: React 18, Vite 5, React Router 7, Font Awesome 7 (legacy); Next.js 14+ con Tailwind CSS y Prisma (moderno)
- **Auth**: JWT (python-jose + bcrypt)
- **Mobile**: PWA con manifest + service worker, instalable en Android/iOS

## Estructura del proyecto

```
├── backend/
│   ├── app/
│   │   ├── api/v1/       # Routers CRUD (clientes, pedidos, productos, etc.)
│   │   ├── auth/         # JWT auth
│   │   ├── db/           # Database session
│   │   ├── models.py     # SQLAlchemy models
│   │   ├── schemas.py    # Pydantic schemas
│   │   └── main.py       # FastAPI app
│   ├── seed.py           # Datos de prueba
│   └── requirements.txt
├── frontend/             # Legacy React/Vite
│   └── src/
│       ├── components/   # UI reutilizable
│       ├── context/      # AuthContext, AppContext, ToastContext
│       ├── pages/        # Page components
│       ├── api.js        # API client con JWT
│       ├── App.jsx       # Router + providers
│       └── App.css       # Design system
├── menugran/             # Next.js PWA (moderna)
│   ├── src/
│   │   ├── app/          # App Router pages
│   │   ├── components/   # Componentes React
│   │   ├── lib/          # Utilidades
│   │   └── prisma/       # Schema + migrations
│   └── tailwind.config.ts # Custom palette (brand, ink, cream, neutral, gold, success, danger, warning)
├── docker-compose.yml    # PostgreSQL
└── opencode-skills/      # Skills reutilizables
    ├── skills/           # 38+ skills organizadas
    │   ├── frontend-design/  # Diseño UI/UX
    │   ├── mcp-builder/     # Creación de MCP servers
    │   ├── docx/pdf/pptx/xlsx/ # Procesamiento documentos
    │   ├── composio-skills/ # 835+ automatizaciones SaaS
    │   └── ...
    ├── agents/           # Agentes especializados
    ├── commands/         # Comandos slash
    └── templates/        # Plantillas de proyecto
```

## Skills disponibles

El directorio `opencode-skills/skills/` contiene skills reutilizables agrupadas por categoría:

### Frontend & UI Design
- `frontend-design` — Guía de diseño visual distintivo
- `canvas-design` — Creación de arte visual en PNG/PDF
- `web-artifacts-builder` — Artefactos HTML/React complejos
- `theme-factory` — Temas profesionales predefinidos
- `brand-guidelines` — Aplica marca a artefactos
- `image-enhancer` — Mejora de imágenes y screenshots

### Document Processing
- `docx` — Manipulación de documentos Word
- `pdf` — Procesamiento de archivos PDF
- `pptx` — Creación y edición de presentaciones
- `xlsx` — Manipulación de hojas de cálculo
- `doc-coauthoring` — Coautoría de documentación técnica

### Development & Code Tools
- `mcp-builder` — Creación de MCP servers (FastMCP / TypeScript)
- `skill-creator` — Creación de skills efectivas
- `changelog-generator` — Changelogs desde commits git
- `langsmith-fetch` — Debug de agentes LangChain/LangGraph
- `webapp-testing` — Testing con Playwright
- `developer-growth-analysis` — Análisis de patrones de código

### Business & Marketing
- `competitive-ads-extractor` — Análisis de anuncios de competidores
- `content-research-writer` — Redacción con investigación
- `domain-name-brainstormer` — Ideas de dominios
- `internal-comms` — Comunicaciones internas
- `lead-research-assistant` — Investigación de leads
- `tailored-resume-generator` — CVs personalizados
- `twitter-algorithm-optimizer` — Optimización de tweets

### Productivity & Organization
- `file-organizer` — Organización inteligente de archivos
- `invoice-organizer` — Organización de facturas
- `raffle-winner-picker` — Sorteos aleatorios
- `meeting-insights-analyzer` — Análisis de reuniones

### App Automation (Composio)
- `connect` / `connect-apps` — Conexión a 500+ apps externas
- `composio-skills` — 835+ automatizaciones SaaS (CRM, PM, Comms, Email, Code, HR)

## Convenciones de código

### Backend (FastAPI)
- Type hints obligatorios en todas las funciones
- Schemas Pydantic v2 para validación request/response
- SQLAlchemy models con `declarative_base`
- Endpoints RESTful con prefijo `/api/v1/{recurso}`
- Formato: `black`, lint: `flake8`, imports: `isort`, types: `mypy`

### Frontend (Next.js PWA)
- Componentes funcionales con hooks
- Sistema de diseño con colores custom (brand, ink, cream, neutral, gold, success, danger, warning)
- CSS con Tailwind y `globals.css` para clases utilitarias
- Nombres PascalCase para componentes, camelCase para hooks/funciones
- Iconos Font Awesome (fas, colección completa)
- Mensajes y UI en español

## Reglas importantes

1. NO modificar `opencode-skills/` sin autorización explícita
2. NO hardcodear secrets; usar variables de entorno
3. Mantener retrocompatibilidad en APIs existentes
4. Usar `apiFetch` del frontend (incluye JWT automáticamente)
5. Mensajes y UI en español
6. Usar colores del sistema de diseño (no Tailwind raw colors como `gray-*`, `slate-*`, `#f9fafb`)
7. Preferir clases utilitarias (`card`, `btn-primary`, `btn-secondary`, `badge-*`, `input`) sobre inline styles

## Skills más relevantes para MenuGran

| Para qué | Skill recomendado |
|----------|------------------|
| Diseño de UI consistente | `frontend-design`, `theme-factory` |
| Testing de frontend | `webapp-testing` |
| Documentación técnica | `doc-coauthoring`, `docx`, `pdf` |
| Reportes (Excel) | `xlsx` |
| Automatización de procesos | `connect`, `composio-skills` |
| Debug de errores | `langsmith-fetch` |
| Generar changelogs | `changelog-generator` |
| Organizar assets | `file-organizer`, `invoice-organizer` |
