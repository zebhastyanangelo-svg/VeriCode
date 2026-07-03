# 06 — Plan de Implementación

> Backlog priorizado de issues conocidos + tareas futuras. Cada item tiene severidad, descripción, criterios de aceptación y estimación.

---

## 🚦 Convención de severidad

| Símbolo | Significado |
|---------|-------------|
| 🔴 **Crítico** | Impide el funcionamiento end-to-end. Hay que arreglar antes de usar. |
| 🟠 **Alto** | Funcionalidad rota pero no bloqueante. Afecta UX o seguridad. |
| 🟡 **Medio** | Mejora importante. Cubre deuda técnica. |
| 🟢 **Bajo** | Nice-to-have, queda para iteraciones siguientes. |

---

## ⚙️ Estado actual vs objetivo

| Capacidad | Hoy | Objetivo v1.0 |
|-----------|-----|----------------|
| Backend arranca y Lee configuración | ✅ | ✅ |
| Admin se crea | ⚠️ manual `GET /auth/setup` | ✅ auto en `lifespan` |
| Casilla IMAP se configura | ✅ | ✅ |
| Casilla → plataforma asignada | ⚠️ solo auto-detect | ✅ manual + fallback |
| IMAP IDLE detecta códigos en tiempo real (push) | ✅ | ✅ |
| WS notifica nuevos códigos | ✅ | ✅ |
| Frontend admin funciona | ✅ | ✅ |
| **Cliente final entra sin login** | ❌ bloqueado | ✅ acceso público |
| Cifrado credenciales | ❌ plano | ✅ fernet/cipher |
| Cleanup code → BD estable | ⚠️ orphans por bug `guess_platform` | ✅ solo platforms con id |
| tests automatizados | ❌ | ✅ básicos (pytest + smoke E2E) |

---

## 🔴 Críticos (sprint 0 — antes de mostrar al cliente)

### #1 — Admin no se auto-crea al boot

**Síntoma**: backend arranca, `USERS_DB = {}`, frontend intenta login → **401**.

**Causa**: `app/api/v1/auth.py` mantiene usuarios en un dict en memoria que solo se llena si alguien hace `GET /auth/setup`. Nadie lo llama.

**Fix propuesto**:
```python
# En app/main.py lifespan
@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(bind=engine)
    seed_platforms()
    seed_admin_users()     # ← nuevo helper
    ...
```

Donde `seed_admin_users()` consulta si existe algún admin y si no, llama a la lógica de setup. **Opcional**: hacer el setup en la primera request a `/auth/setup` con flag `force=False` (no-op si ya existe).

**Criterios de aceptación**:
- [ ] Arrancar el backend, esperar, login con `admin/admin123` → 200 sin llamar manualmente a `/auth/setup`.
- [ ] Re-arrancar → no duplica admin.

**Estimación**: 15 min.

---

### #2 — URL `/#/code-request` requiere login (frontend bug)

**Síntoma**: README y PRD dicen "URL pública sin auth". Sin embargo, en `frontend/src/App.jsx`:
```jsx
if (!user) return <LoginPage />;   // ← cualquier hash sin user va a Login
```

**Causa**: el guard global evalúa `user` antes de discriminar la ruta.

**Fix propuesto**:
```jsx
function AppContent() {
  const { user, loading } = useAuth();
  const publicHashes = ['/code-request'];

  const rawHash = window.location.hash.slice(1) || '/';
  const isPublic = publicHashes.includes(rawHash.split('?')[0]);

  useEffect(() => {
    const onHash = () => { /* ... */ };
  }, []);

  if (loading) return <Loading />;
  if (!user && !isPublic) return <LoginPage />;

  // Si es pública y hay user -> renderizar igual (UX "también logueado")
  const Page = mapHashToPage(rawHash);

  if (isPublic) {
    return <main className="main-content"><Page /></main>;  // sin Navbar
  }

  return (
    <div className="app-layout">
      <Navbar />
      <main className="main-content"><Page /></main>
    </div>
  );
}
```

**Criterios de aceptación**:
- [ ] Visitante anónimo puede acceder a `/#/code-request` y ver el formulario.
- [ ] No se muestra la Navbar en esa ruta.
- [ ] Cualquier otra ruta sigue requiriendo login.

**Estimación**: 15 min.

---

### #3 — `guess_platform` puede crear objetos `Platform` huérfanos

**Síntoma**: códigos persistidos con `platform_id=NULL` ("huérfanos"), cuelgan en el Dashboard.

**Causa** (en `code_extractor.py` líneas ~50):
```python
if sender_match or subject_match:
    plat = Platform(name=key, display_name=...)   # ← platform CON id=None
    return plat
```

Y luego `imap_poller.process_account`:
```python
platform_id=platform.id if platform else None,
```

→ graba `NULL` en la FK.

**Fix propuesto**: buscar el match en `platforms[]` (BD); si no existe → devolver `None`.
```python
for platform in platforms:
    if platform.name == key:
        return platform
return None
```

**Criterios de aceptación**:
- [ ] Si llega un email de un patrón conocido pero la plataforma no existe en BD → el código se persiste con `platform_id=NULL` intencionalmente (sin intentar crar Platform nuevo), y aparece en el Dashboard con plataforma "Desconocida".
- [ ] Si la plataforma existe → queda asociada correctamente.

**Estimación**: 10 min.

---

### #4 — Mejorar la lógica de asociación plataforma ↔ código

**Decisión de producto**: actualmente `guess_platform` es la única fuente. Hay que agregar `account.platform_id` como **fuente primaria** (lo que el operador configuró).

**Fix propuesto** (en `imap_poller.process_account`):
```python
# PRIORIDAD 1: la plataforma asignada al crear la cuenta
platform = account.platform

# PRIORIDAD 2: si la cuenta no tiene plataforma, autodetectar
if not platform:
    platform = guess_platform(msg["sender"], msg["subject"], platforms)

# PRIORIDAD 3 (futuro): permitir override manual desde el Dashboard
```

**Criterios de aceptación**:
- [ ] Si una cuenta tiene asignado `platform_id = netflix_id`, todos los códigos que llegan ahí se persisten con esa plataforma, sin importar el remitente.
- [ ] Si no tiene, detecta automáticamente.
- [ ] Se permite visualizar y editar la plataforma de un código ya guardado (v1.1 — ver backlog).

**Estimación**: 15 min.

---

### #5 — `main.py` y `email_accounts.py` usan dos instancias de `poller`

**Síntoma**: `email_accounts.py` define `poller = IMAPPoller()` distinto al de `main.py`. El `/poll` manual puede no usar el mismo singleton que el poller automático.

**Fix propuesto**: mover la creación del poller a un módulo singleton (ej. `app/services/poller_singleton.py`) o importarlo desde `main`.

**Estimación**: 5 min.

---

## 🟠 Altos (sprint 1 — calidad + estabilidad)

### #6 — Cifrar `password_encrypted`

**Hoy**: se guarda plano.
**Fix**: usar `cryptography.fernet` con `FIELD_ENCRYPTION_KEY` en `.env`.

```python
from cryptography.fernet import Fernet
cipher = Fernet(settings.field_encryption_key.encode())
password_encrypted = cipher.encrypt(password.encode()).decode()
```

**Criterios de aceptación**:
- [ ] En BD, la columna `password_encrypted` muestra bytes base64 (no el password legible).
- [ ] El poller descifra al usar IMAP y todo funciona igual.

**Estimación**: 30 min.

---

### #7 — Poller no maneja correctamente cuentas con error IMAP persistente

**Hoy**: `connect_account` retorna `None` y la cuenta nunca se chequea hasta intervención manual.

**Fix propuesto**:
- Backoff exponencial por cuenta: `attempt_count` + `last_error_message`.
- Vistas de admin que muestren cuentas con "X intentos fallidos".

**Estimación**: 45 min.

---

### #8 — WS `/codes/ws` no autentica

**Cualquiera** con la URL puede subscribirse al feed de códigos en tiempo real.

**Fix**: pasar token en query `?token=...` y validarlo en el handshake.

**Estimación**: 20 min.

---

### #9 — Definir lógica de "entrega" del código

**Hoy**: `is_delivered` se setea solo cuando el admin lo marca manualmente desde el dashboard.

**Pregunta de producto**:
- ¿La entrega al usuario público debe contarse como "entregado"?
- ¿O solo el admin puede "consumir" códigos?

**Decisión recomendada**: contar como entregado cuando el cliente ejecuta `POST /public/request-code` con éxito y persiste:
- `is_delivered=True`
- `delivered_to=email del cliente`
- `delivered_at=now`

**Criterios de aceptación**:
- [ ] Tras una entrega pública exitosa, el código aparece como entregado en el dashboard del admin.
- [ ] La métrica `undelivered` decrece correctamente.

**Estimación**: 20 min.

---

### #10 — Duplicación de plataformas y de iconos (seed)

**Síntoma**: `seed.py` y `main.py`'s `seed_platforms()` tienen listas similares pero con iconos distintos (`🔴` vs `"netflix" string`). Si corren ambos, hay inconsistencia.

**Fix**: unificar en un único helper en `app/db/seed_data.py`, importar desde `seed.py` y `main.py`.

**Estimación**: 10 min.

---

## 🟡 Medios (sprint 2 — producto)

### #11 — Tabla `users` en BD + CRUD

Reemplazar `USERS_DB` en memoria por tabla persistente con password hasheado.

**Estimación**: 1 hora.

### #12 — `Alembic` para migrations

El paquete está en `requirements.txt` pero no hay `alembic init`. Hoy los cambios de schema se aplican vía `Base.metadata.create_all`, que no permite migrar破坏ivamente.

**Estimación**: 1.5 horas.

### #13 — Override manual de plataforma desde el Dashboard

El operador debería poder corregir un código mal clasificado in-place.

**Estimación**: 30 min.

### #14 — Vista de "actividad reciente" del poller

Lista de últimas N ejecuciones por cuenta: `last_checked`, `last_error`, `codes_found`.

**Estimación**: 1 hora.

### #15 — Validación IMAP antes de guardar cuenta

Endpoint `POST /email-accounts/validate` que toma credenciales y devuelve {ok, mensaje, plataformas_sugeridas} antes de `POST /email-accounts`.

**Estimación**: 30 min.

---

## 🟢 Bajos (sprint 3 — polish)

### #16 — Caché de plataformas en memoria

Las listas de plataformas cambian poco → cache 5 min en backend.

### #17 — Logout / refresh token

Hoy el logout es solo `localStorage.removeItem('token')`. Agregar endpoint `/auth/logout` (invalidar en backend) si se quisiera auditoria.

### #18 — Modo oscuro (dark mode)

CSS variables alternadas con `[data-theme="dark"]`.

### #19 — Tests E2E con Playwright

Flujos críticos:
- Login admin.
- Agregar cuenta.
- Crear plataforma.
- Solicitar código público (mock del backend con un código en BD).

### #20 — Audit log

Tabla `audit_log` que registre: quién, cuándo, qué acción, sobre qué entidad.

---

## 📊 Roadmap resumido

| Sprint | Alcance | Items |
|--------|---------|-------|
| **Sprint 0 (Críticos)** | Hacer funcionar end-to-end | #1, #2, #3, #4, #5 |
| **Sprint 1 (Altos)** | Seguridad + robustez | #6, #7, #8, #9, #10 |
| **Sprint 2 (Producto)** | Features de admin y producto | #11, #12, #13, #14, #15 |
| **Sprint 3 (Polish)** | UX + calidad | #16–#20 |

---

## ✅ Definición de "Done" para v1.0

- [ ] Todos los críticos (#1-#5) merged y validados en dev con cuenta IMAP real.
- [ ] Todos los altos (#6-#10) merged.
- [ ] Tests básicos: al menos un test por router (pytest).
- [ ] Documentación (`docs/`) completa y revisada.
- [ ] Deploy reproducible con docker-compose + script `bin/run-prod.sh`.
- [ ] Credenciales por defecto documentadas y `.env.example` publicado.

---

## 📌 Notas para opencode (lo que viene)

Cuando se abra la implementación (opencode o trabajo manual), el orden sugerido es:

1. Issue #2 (frontend guard) y #1 (auto-setup) — son 30 min en total y desbloquean el flujo público.
2. Issue #4 (`account.platform_id` ya está en BD, falta aplicar) — 15 min.
3. Issue #3 (fix `guess_platform`) — 10 min.
4. Tests de smoke con cuenta IMAP real (crear `bin/test_e2e.sh` que mockee el IMAP con `imaplib` → un servidor local).
