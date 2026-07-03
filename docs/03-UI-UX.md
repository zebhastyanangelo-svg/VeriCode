# 03 — UI / UX

**Producto**: VeriCode
**Lenguaje visual**: moderno, denso, tipo "admin panel" — limpio, con sombras sutiles.

---

## 1. 🎨 Sistema de diseño

### Paleta de colores (CSS custom properties)

Definidas en `frontend/src/index.css`:

| Variable | Valor | Uso |
|----------|-------|-----|
| `--brand` | `#2563eb` | CTAs, links, acentos |
| `--brand-hover` | `#1d4ed8` | Estado hover de CTAs |
| `--ink` | `#111827` | Texto principal |
| `--cream` | `#fafafa` | Fondo general |
| `--gold` | `#f59e0b` | Highlights, badges premium |
| `--success` | `#10b981` | OK, entregado, leído |
| `--danger` | `#ef4444` | Errores, eliminar |
| `--warning` | `#f59e0b` | Advertencias |
| `--neutral` | gris | Texto secundario, bordes |

> **Regla del equipo**: usar siempre estas variables. Nunca colores raw de Tailwind/Bootstrap (`gray-*`, `slate-*` → usar `var(--neutral)`).

### Tipografía

- Sans-serif del sistema (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`).
- Pesos: 400 (body), 600 (subtítulos), 700 (títulos).
- Tamaño base: `14px`.

### Iconografía

- **Font Awesome 7** (colección completa, `fas`).
- Convención: cada botón lleva un icono a la izquierda.

---

## 2. 📐 Layout y rejilla

```
┌────────────────────────────────────────────────────┐
│  Navbar (sticky-top, fondo --cream)                │
│  [logo] [links]                              [user]│
├────────────────────────────────────────────────────┤
│                                                     │
│  Main content (ancho máx 1200px, centrado)         │
│                                                     │
└────────────────────────────────────────────────────┘
```

- **Breakpoints**: mobile-first; prueba visual: 375 / 768 / 1280.
- **Cards**: `border-radius: var(--radius-md)` (8 px), sombra `box-shadow: 0 1px 3px rgba(0,0,0,0.05)`.

---

## 3. 🗂️ Pantallas (wireframes)

### 3.1 Login (`/#/login`)

```
┌──────────────────────────────┐
│         [icon shield]        │
│          VeriCode            │
│  Sistema de Códigos de       │
│       Verificación           │
│                              │
│   👤 Usuario     [admin    ] │
│   🔒 Contraseña  [admin123 ] │
│                              │
│       [ Ingresar ]           │
│                              │
└──────────────────────────────┘
```

- Centrada vertical y horizontalmente.
- Tarjeta con borde `--neutral` y sombra suave.
- `input:focus` → anillo azul (`--brand`).

### 3.2 Dashboard (`/#/` o `/#/dashboard` por default)

```
┌────────────────────────────────────────────────────┐
│  🏠 Dashboard                          [ Actualizar ] │
├────────────────────────────────────────────────────┤
│ ┌────┐ ┌────┐ ┌────┐ ┌────┐                        │
│ │128 │ │ 14 │ │  9 │ │ 23 │                        │
│ │Tot │ │New │ │Pen │ │1h  │ ← Stats grid (4 cards) │
│ └────┘ └────┘ └────┘ └────┘                        │
├────────────────────────────────────────────────────┤
│ 🔍 [Buscar por código, correo, plataforma...]  [✕] │
├────────────────────────────────────────────────────┤
│ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│ │ Netflix  │ │ ChatGPT  │ │ Spotify  │              │
│ │ 123456   │ │ 987654   │ │ 456123   │              │
│ │ from ... │ │ from ... │ │ from ... │              │
│ │ [📤][✓]  │ │ [📤][✓]  │ │ [📤][✓]  │              │
│ └──────────┘ └──────────┘ └──────────┘              │
└────────────────────────────────────────────────────┘
```

- **Stats grid**: 4 cards (`total`, `unread`, `undelivered`, `last_hour`) — fondo color suave.
- **Code cards**: grid responsive (3 columnas desktop, 2 tablet, 1 mobile).
- Los nuevos códigos aparecen arriba (WS push) — animación `slide-in` 200 ms.

### 3.3 Cuentas de Correo (`/#/accounts`)

```
┌────────────────────────────────────────────────────┐
│  📨 Cuentas de Correo      [ + Agregar Cuenta ]     │
├────────────────────────────────────────────────────┤
│ Email │ Tipo │ Plataf│ Estado │ Último │ Notas │ ... │
│ ──────┼──────┼───────┼────────┼────────┼───────┼──── │
│ a@..  │ gmail│Netflx │  ●     │ 12:34  │  -    │ ✎🗑 │
└────────────────────────────────────────────────────┘
```

- Tabla con `tr:hover { background: var(--cream-hover) }`.
- Botones de acción por fila: probar conexión, poll manual, editar, eliminar.
- **Modal** para creación/edición:
  ```
  └── Modal (overlay oscuro) ──┐
      ├── Correo [input]            │
      ├── Tipo [select: gmail/outlook/yahoo/custom] │
      ├── Plataforma [select opcional]              │
      ├── Contraseña [password]                      │
      ├── Servidor IMAP [input opcional]            │
      ├── Puerto [number=993]                        │
      ├── Notas [textarea]                           │
      └── [Cancelar]  [Crear Cuenta]                 │
  ```

### 3.4 Plataformas (`/#/platforms`)

```
┌────────────────────────────────────────────────────┐
│  📺 Plataformas          [ + Agregar Plataforma ]  │
├────────────────────────────────────────────────────┤
│ Display │ Tipo │ Regex │ Remitente │ Estado │ ... │
│ ────────┼──────┼───────┼───────────┼────────┼──── │
│ Netflix │ 📺   │ \d... │ info@...  │  ●     │ ✎🗑 │
└────────────────────────────────────────────────────┘
```

- Modal igual a Cuentas pero con campos: nombre (id único), display_name, provider_type, code_pattern (regex), sender_pattern (regex), subject_pattern (regex), icon.

### 3.5 Solicitar Código (Público) (`/#/code-request`)

```
┌──────────────────────────────┐
│  🔑  Solicitar Código        │
│  Introduce tus datos...      │
│                              │
│  ✉  Correo:                  │
│    [input type="email"       │
│     placeholder="ejemplo@correo.com"] │
│                              │
│  📚 Plataforma:              │
│    [select plataformas]      │
│                              │
│      [ Buscar Código ]       │
│                              │
│ ─── Resultado ───            │
│   ✓ Código Encontrado        │
│   ┌────────────────┐         │
│   │   123456       │         │
│   └────────────────┘         │
│   Plataforma: Netflix        │
│   Correo: cliente@a.com      │
│   Recibido: 12:34:56         │
│   [ Solicitar otro ]         │
└──────────────────────────────┘
```

- Página fullscreen, sin Navbar (porque es pública, sin auth).
- **Énfasis visual en el código**: tipografía `2.5rem`, `letter-spacing: 0.5em`, color `--ink`, fondo blanco con `border: 2px dashed var(--success)`.

---

## 4. 🌗 Temas / modos

- v1: solo **modo claro**. Modo oscuro queda para v1.1 (variable `--ink` / `--cream` invertirían valores).

---

## 5. ♿ Accesibilidad (a11y)

- Labels en cada input (`htmlFor`).
- Focus visible (anillo `--brand`).
- Contraste mínimo WCAG AA en texto principal.
- Botones con `aria-label` cuando solo tienen icono.
- Inputs con `autoFocus` solo en el primero del flujo.
- Mensajes de error con rol `role="alert"` (vía `ToastContext`).

> Pendiente v1.1: auditoría completa con axe / Lighthouse.

---

## 6. 🍞 Toasts y feedback

`ToastContext` provee `toast.success/error/info/warning`.

- Aparecen en esquina inferior derecha.
- Auto-dismiss: 4 s (success) / 6 s (error).
- Pila de hasta 5 toasts.
- Animación slide-in/out 150 ms.

---

## 7. ⌨️ Convenciones de interacción

| Acción | UI Feedback |
|--------|-------------|
| Submit form | Botón disabled mientras loading + spinner |
| Acción destructiva (delete) | `confirm()` JS antes de llamar API |
| Lista vacía | Ícono grande + mensaje ("No hay códigos de verificación") |
| Error de red | Toast + mantener estado anterior |
| Carga inicial | Skeleton o `<Loading />` centrado con texto |

---

## 8. 📱 Responsive

| Breakpoint | Cambios |
|-----------|---------|
| `< 768 px` | Stats grid 2 columnas; tabla → cards (pendiente). |
| `768 – 1024` | Stats grid 4 columnas; 2 cards de código por fila. |
| `> 1024` | Layout completo, tabla como tabla. |

---

## 9. 🧩 Componentes reutilizables (`frontend/src/components/`)

- `Navbar.jsx` — barra superior con brand y links.
- `Loading.jsx` — spinner centralizado, prop `text`.
- `CodeCard.jsx` — tarjeta de código con botones de acción → entregado / leído.

---

## 10. 📌 Pendientes / mejoras v1.1

- [ ] Página de estadísticas con gráficas (Chart.js o Recharts).
- [ ] Sistema de notificaciones push dentro de la app.
- [ ] Dark mode.
- [ ] Búsqueda en tiempo real con FUSE.js (autocomplete).
- [ ] Audit trail visual (quién entregó qué y cuándo).
