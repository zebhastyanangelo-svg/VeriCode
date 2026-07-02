# Claude Code Skills & Templates

Repositorio organizado de skills, agents, commands, hooks, MCPs y templates para Claude Code.

## Estructura

```
opencode-skills/
├── agents/          # Agentes especializados IA (13)
├── commands/        # Comandos slash personalizados (8)
├── hooks/           # Automatizaciones y hooks
├── mcp/             # Integraciones MCP (Model Context Protocol)
├── rules/           # Reglas de proyecto (CLI, Cloudflare, Dashboard)
├── skills/          # Skills reutilizables (38+ categorías)
│   ├── frontend-design/       # Diseño UI/UX
│   ├── canvas-design/         # Arte visual en PNG/PDF
│   ├── web-artifacts-builder/ # Artefactos HTML/React
│   ├── theme-factory/         # Temas profesionales
│   ├── brand-guidelines/      # Guías de marca
│   ├── image-enhancer/        # Mejora de imágenes
│   ├── docx/pdf/pptx/xlsx/    # Documentos Office
│   ├── doc-coauthoring/       # Coautoría de documentos
│   ├── mcp-builder/           # Creación de MCP servers
│   ├── skill-creator/         # Creación de skills
│   ├── skill-share/           # Compartir skills via Slack
│   ├── template-skill/        # Template para nuevas skills
│   ├── changelog-generator/   # Changelogs desde git
│   ├── langsmith-fetch/       # Debug de LangChain/LangGraph
│   ├── webapp-testing/        # Testing con Playwright
│   ├── developer-growth/      # Análisis de crecimiento dev
│   ├── competitive-ads/       # Análisis de anuncios competencia
│   ├── content-research/      # Investigación y redacción
│   ├── domain-name/           # Generador de dominios
│   ├── internal-comms/        # Comunicaciones internas
│   ├── lead-research/         # Investigación de leads
│   ├── resume-generator/      # Generación de CVs
│   ├── twitter-optimizer/     # Optimización de tweets
│   ├── algorithmic-art/       # Arte generativo p5.js
│   ├── slack-gif-creator/     # GIFs animados para Slack
│   ├── video-downloader/      # Descarga de videos
│   ├── file-organizer/        # Organización de archivos
│   ├── invoice-organizer/     # Organización de facturas
│   ├── raffle-picker/         # Sorteos aleatorios
│   ├── meeting-insights/      # Análisis de reuniones
│   ├── connect/               # Conectar Claude a apps externas
│   ├── connect-apps/          # Plugin de conexión a apps
│   ├── composio-skills/       # 835+ automatizaciones de apps SaaS
│   └── claude-api/            # Integración con Claude API
└── templates/       # Plantillas de proyecto
    ├── api/         # FastAPI templates
    ├── scripts/     # Scripts setup/deploy
    └── CLAUDE.md    # Configuración de referencia
```

## Origen

- **davila7/claude-code-templates** — Agents, commands, hooks, MCPs, rules, templates
- **ComposioHQ/awesome-claude-skills** — Skills de frontend, diseño, documentos, automatización
- **anthropics/skills** — Skills oficiales de Anthropic

## Skills por categoría

### Frontend & UI Design

| Skill | Descripción |
|-------|-------------|
| `frontend-design` | Guía de diseño visual distintivo para UI. Tipografía, paleta, layout, animación intencional |
| `canvas-design` | Creación de arte visual en PNG/PDF con filosofía de diseño |
| `web-artifacts-builder` | Artefactos HTML complejos con React + Tailwind + shadcn/ui |
| `theme-factory` | 10 temas predefinidos con colores/fuentes para slides, docs, landing pages |
| `brand-guidelines` | Aplica colores y tipografía oficial de Anthropic a artefactos |
| `image-enhancer` | Mejora resolución, nitidez y claridad de imágenes y screenshots |

### Document Processing

| Skill | Descripción |
|-------|-------------|
| `docx` | Crear, editar, analizar documentos Word con tracked changes |
| `pdf` | Extraer texto, tablas, metadata; mergear y anotar PDFs |
| `pptx` | Leer, generar y ajustar slides, layouts y templates |
| `xlsx` | Manipulación de hojas de cálculo: fórmulas, charts, transformaciones |
| `doc-coauthoring` | Flujo estructurado para coautoría de documentación técnica |

### Development & Code Tools

| Skill | Descripción |
|-------|-------------|
| `mcp-builder` | Guía para crear MCP servers en Python (FastMCP) o TypeScript |
| `skill-creator` | Creación de skills efectivas con conocimiento especializado |
| `skill-share` | Crea skills y las comparte automáticamente en Slack |
| `template-skill` | Template base para nuevas skills |
| `changelog-generator` | Genera changelogs desde commits git automáticamente |
| `langsmith-fetch` | Debug de agentes LangChain/LangGraph con traces de LangSmith |
| `webapp-testing` | Testing de apps web locales con Playwright |
| `developer-growth-analysis` | Analiza patrones de código y sugiere recursos de aprendizaje |
| `algorithmic-art` | Arte generativo con p5.js (randomness seedeada) |

### Business & Marketing

| Skill | Descripción |
|-------|-------------|
| `competitive-ads-extractor` | Extrae y analiza anuncios de competidores de ad libraries |
| `content-research-writer` | Redacción con investigación, citas y feedback sección por sección |
| `domain-name-brainstormer` | Genera ideas de dominios y verifica disponibilidad en múltiples TLDs |
| `internal-comms` | Redacción de comunicaciones internas (newsletters, FAQs, reportes) |
| `lead-research-assistant` | Identifica y califica leads de alta calidad |
| `tailored-resume-generator` | Genera CVs adaptados a descripciones de trabajo |
| `twitter-algorithm-optimizer` | Optimiza tweets para máximo alcance usando algoritmo open-source |

### Productivity & Organization

| Skill | Descripción |
|-------|-------------|
| `file-organizer` | Organiza archivos entendiendo contexto, encuentra duplicados |
| `invoice-organizer` | Organiza facturas y recibos para preparación de impuestos |
| `raffle-winner-picker` | Selecciona ganadores aleatorios con randomness criptográfica |
| `meeting-insights-analyzer` | Analiza transcripciones de reuniones para patrones de comportamiento |

### Creative & Media

| Skill | Descripción |
|-------|-------------|
| `slack-gif-creator` | Crea GIFs animados optimizados para Slack |
| `video-downloader` | Descarga videos de YouTube y otras plataformas |

### App Automation (Composio)

| Skill | Descripción |
|-------|-------------|
| `connect` | Conecta Claude a apps externas (Gmail, Slack, GitHub, Notion) |
| `connect-apps` | Plugin para conectar Claude a 500+ apps via Composio |
| `composio-skills` | 835+ skills de automatización para apps SaaS (CRM, PM, Comms, Email, Code, HR, etc.) |

### API & Claude Integration

| Skill | Descripción |
|-------|-------------|
| `claude-api` | Integración con Claude API para flujos avanzados |

## Skills más útiles para este proyecto (MenuGran PWA)

| Categoría | Skills | Uso |
|-----------|--------|-----|
| **Frontend** | `frontend-design`, `canvas-design`, `web-artifacts-builder`, `webapp-testing`, `theme-factory`, `brand-guidelines`, `image-enhancer` | Diseño y testing de UI |
| **Documentos** | `docx`, `pdf`, `pptx`, `xlsx`, `doc-coauthoring` | Reportes, facturas, documentación |
| **Desarrollo** | `mcp-builder`, `skill-creator`, `changelog-generator`, `langsmith-fetch` | Herramientas de desarrollo |
| **Marketing** | `content-research-writer`, `internal-comms`, `domain-name-brainstormer`, `lead-research-assistant` | Contenido y comunicación |
| **Productividad** | `file-organizer`, `invoice-organizer`, `meeting-insights-analyzer` | Organización |
| **Automatización** | `connect`, `composio-skills` | Integración con apps externas |
