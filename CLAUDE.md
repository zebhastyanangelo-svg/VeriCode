# Sistema Administrativo

Sistema de gestión administrativa tipo ERP con FastAPI backend + React frontend.

## Stack

- **Backend**: Python 3.14, FastAPI 0.115, SQLAlchemy 2.0, SQLite/PostgreSQL
- **Frontend**: React 18, Vite 5, React Router 7, Font Awesome 7
- **Auth**: JWT (python-jose + bcrypt)

## Convenciones de código

### Backend
- Type hints obligatorios en todas las funciones
- Schemas Pydantic v2 para validación request/response
- SQLAlchemy models con `declarative_base`
- Endpoints RESTful con prefijo `/api/v1/{recurso}`
- Formato: `black`, lint: `flake8`, imports: `isort`, types: `mypy`

### Frontend
- Componentes funcionales con hooks
- Estado global via Context API (AuthContext + AppContext + ToastContext)
- CSS con custom properties, sin Tailwind
- Nombres PascalCase para componentes, camelCase para hooks/funciones
- Iconos Font Awesome (fas, colección completa)

## Estructura del proyecto

```
├── backend/
│   ├── app/
│   │   ├── api/v1/       # Routers CRUD
│   │   ├── auth/         # JWT auth
│   │   ├── db/           # Database session
│   │   ├── models.py     # SQLAlchemy models
│   │   ├── schemas.py    # Pydantic schemas
│   │   └── main.py       # FastAPI app
│   ├── seed.py           # Datos de prueba
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── components/   # UI reutilizable
│       ├── context/      # Context providers
│       ├── pages/        # Page components
│       ├── api.js        # API client con JWT
│       ├── App.jsx       # Router + providers
│       └── App.css       # Design system
├── docker-compose.yml    # PostgreSQL
└── opencode-skills/      # Skills y templates
```

## Skills disponibles

`opencode-skills/skills/` contiene 38+ skills para diversas tareas. Las más relevantes:

| Skill | Para qué |
|-------|----------|
| `frontend-design` | Diseño UI consistente con el sistema de diseño |
| `webapp-testing` | Testing de frontend con Playwright |
| `changelog-generator` | Changelogs desde commits git |
| `doc-coauthoring`, `docx`, `pdf`, `xlsx` | Documentación y reportes |
| `file-organizer`, `invoice-organizer` | Organización de archivos |
| `composio-skills` | 835+ automatizaciones SaaS |
| `mcp-builder` | Creación de MCP servers |

Ver `opencode-skills/README.md` para el catálogo completo.

## Reglas importantes
1. NO modificar `opencode-skills/` sin autorización explícita
2. NO hardcodear secrets; usar variables de entorno
3. Mantener retrocompatibilidad en APIs existentes
4. Usar `apiFetch` del frontend (incluye JWT automáticamente)
5. Mensajes y UI en español
6. Usar colores del sistema de diseño (brand, ink, cream, neutral, gold, success, danger, warning) en vez de raw Tailwind colors (`gray-*`, `slate-*`)
