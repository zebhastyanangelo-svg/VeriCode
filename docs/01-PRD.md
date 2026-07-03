# 01 — Product Requirements Document (PRD)

**Producto**: VeriCode — Sistema de Códigos de Verificación
**Versión**: 1.0
**Estado**: Aprobado para desarrollo

---

## 1. 🎯 Visión del producto

VeriCode es un sistema ERP-style que automatiza la **recepción, extracción y entrega de códigos de verificación** que llegan a casillas de correo electrónico. Está pensado para negocios que venden o gestionan accesos a plataformas de streaming (Netflix, Disney+, Spotify) e IA (ChatGPT, Claude, Midjourney), y que necesitan entregar esos códigos a sus clientes de forma rápida, confiable y trazable.

> **Problema que resuelve**: hoy los operadores revisan casillas manualmente, copian códigos a mano y se pierden en el camino. VeriCode lo hace **automático**: mantiene conexiones IMAP IDLE persistentes, recibe notificaciones push cuando llega un correo, extrae el código, lo asocia a la plataforma correcta, y lo entrega al cliente en una pantalla pública.

---

## 2. 👥 Usuarios objetivo

| Persona | Necesidad | Cómo lo usa VeriCode |
|---------|-----------|----------------------|
| **Admin / Operador** | Monitorear múltiples casillas, configurar plataformas, ver historial. | Login → Dashboard / Cuentas / Plataformas. |
| **Cliente final** | Obtener el código que le llegó al correo, sin registrarse. | URL pública → ingresar su correo + seleccionar plataforma → ver código. |
| **Manager** | Tener visibilidad de actividad, métricas, quién recibió qué. | Dashboard con stats en tiempo real. |

> El **cliente final NO tiene cuenta**. La URL `/#/code-request` debe ser pública sin auth. *(Ver issue conocido #2 en `06-PLAN.md`)*

---

## 3. ✅ Objetivos & OKRs

### Objetivo 1: Entrega confiable de códigos

- **KR1**: ≥ 99% de códigos recibidos → entregados al cliente en < 10 s tras su llegada al buzón (IMAP IDLE lo reduce a ~1 s).
- **KR2**: 0% de códigos entregados a plataforma equivocada.
- **KR3**: Todos los códigos quedan trazados (auditoría: `is_delivered`, `delivered_to`, `delivered_at`).

### Objetivo 2: Operación simple para el admin

- **KR1**: El admin puede configurar una nueva casilla en ≤ 2 minutos (formulario, test de conexión, guardar).
- **KR2**: El admin puede agregar una plataforma nueva sin tocar código (campo `sender_pattern` en el form).

### Objetivo 3: Operación autosuficiente

- **KR1**: El sistema se reinicia y los códigos siguen funcionando sin intervención manual.
- **KR2**: Un nuevo admin puede entender el flujo leyendo el dashboard en ≤ 5 minutos.

---

## 4. 🚫 Fuera de alcance (v1)

- ❌ SMS / 2FA — solo email/IMAP.
- ❌ Envío de códigos al usuario (solo recepción y entrega).
- ❌ Multi-tenant (un solo operador por deploy).
- ❌ OAuth para los clientes finales.
- ❌ App móvil — solo web responsive.
- ❌ Pagos / billing.
- ❌ Notificación por push / email al cliente cuando llega su código (solo entrega on-demand).

---

## 5. 🎬 User Stories

### US-1 — Operador configura casilla
> Como **operador**, quiero agregar una casilla IMAP al sistema para que los códigos que lleguen ahí empiecen a procesarse automáticamente.

**Criterios de aceptación**:
- Formulario con email, tipo (Gmail/Outlook/Yahoo/custom), password, host/puerto opcionales.
- Campo opcional "Plataforma" para asociar la casilla a su plataforma principal.
- Botón "Probar conexión" que valida IMAP antes de guardar.
- Botón "Verificar ahora" para forzar poll manual.
- Mensaje de éxito/error claro.

### US-2 — Cliente pide su código
> Como **cliente**, quiero entrar a una página pública, ingresar mi correo, elegir la plataforma, y ver mi código.

**Criterios de aceptación**:
- URL pública, sin login.
- Input de email (type="email", sin lista de correos registrados).
- Select de plataformas (solo `is_active=True`).
- Sistema busca el código más reciente, lo muestra prominentemente.
- Si no hay código → mensaje claro.

### US-3 — Operador ve códigos en tiempo real
> Como **operador**, quiero ver todos los códigos que llegan al sistema en un dashboard, con búsqueda y filtros.

**Criterios de aceptación**:
- Lista de códigos con código, email, plataforma, remitente, asunto, fecha.
- Filtro por texto (código/email/plataforma/remitente).
- WebSocket: nuevos códigos aparecen arriba sin recargar.
- Marcar como leído / entregado.

### US-4 — Operador configura plataforma
> Como **operador**, quiero agregar una plataforma nueva (ej: Crunchyroll) sin tocar código.

**Criterios de aceptación**:
- Form con: nombre, display_name, tipo (streaming/ai/other), regex de código, regex de remitente, regex de asunto, icono.

### US-5 — Admin entra al sistema
> Como **admin**, quiero loguearme con usuario/contraseña y mantener la sesión por 8 horas.

**Criterios de aceptación**:
- Login con token JWT, 480 min de expiración.
- Si token expira → redirige a login.
- Credenciales dev por defecto: `admin / admin123`.

---

## 6. 🔁 Flujos de alto nivel

### Flujo A — Configuración inicial (admin)
```
Login admin → Cuentas → Agregar casilla (Gmail) → Probar conexión → Guardar
Login admin → Plataformas → Verificar que Netflix/Disney+ están precargadas
```

### Flujo B — Operación normal
```
[Cliente] solicita código → elige mail + plataforma
[Sistema] busca en BD el último código para esa combinación
[Cliente] ve el código en pantalla → lo copia → lo usa en Netflix/ChatGPT/etc
```

### Flujo C — Operación interna
```
[IMAP IDLE] recibe push notification → extrae código → lo persiste → notifica WS
[Dashboard admin] lo muestra en vivo
```

*(Detalles paso-a-paso en `04-FLUJO.md`)*

---

## 7. 📊 Métricas de éxito

| Métrica | Cómo se mide | Target |
|---------|--------------|--------|
| Latencia IMAP → UI | `received_at - created_at` | < 2 s (IDLE push) |
| Códigos correctamente clasificados | % códigos con `platform_id` no nulo | ≥ 95% |
| Uptime del poller | Logs de watchdog | ≥ 99% |
| Satisfacción del operador | NPS informal | — |

---

## 8. ⚠️ Riesgos & mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Contraseña IMAP comprometida | Alto | Cifrar `password_encrypted` en BD (bcrypt con salt único o `cryptography.fernet`). |
| IMAP rate-limiting del proveedor | Medio | IMAP IDLE timeout configurable (default 1680s), reconexión automática con backoff. |
| Cambio de remitente por proveedor | Medio | Diccionario `PLATFORM_PATTERNS` actualizable + campo `sender_pattern` por plataforma. |
| Pérdida de conexión WS | Bajo | Reconexión automática cada 5 s en cliente. |

---

## 9. 📅 Roadmap (resumen)

| Fase | Alcance | Estado |
|------|---------|--------|
| **v0.1** | Backend funcional + IMAP poller | ✅ |
| **v0.2** | Frontend admin + dashboard | ✅ |
| **v0.3** | Fix bugs críticos (auth setup, ruta pública, detección plataforma) | 🔄 En curso |
| **v1.0** | Cifrado credenciales, polling robusto, doc completa | 🎯 Próximo |
| **v1.1** | Notificación al cliente + email cuando llega código | 📋 Idea |
| **v2.0** | Multi-tenant + OAuth admin | 💭 Futuro |
