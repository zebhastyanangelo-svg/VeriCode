import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import inspect, text


from app.api.v1 import auth, codes, email_accounts, platforms, public
from app.auth.auth import get_password_hash, validate_fernet_key
from app.config import (
    DEV_FERNET_MARKER,
    DEV_SECRET_PREFIX,
    is_production,
    settings,
)
from app.core import cache as app_cache
from app.db.database import Base, engine, SessionLocal
from app.models import Platform, User, VerificationCode
from app.services.imap_poller import poller_instance as poller


def _cors_origins() -> list[str]:
    raw = (settings.cors_origins or "").strip()
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]


def _resolve_cors() -> tuple[list[str], bool]:
    """Reglas CORS:
    - Si los orígenes NO incluyen '*' => usar lista explícita CON credenciales.
    - Si los orígenes SON '*'          => sin credenciales (los navegadores
      rechazan `*` + `withCredentials`)."""
    origins = _cors_origins()
    return origins, origins != ["*"]


def _run_user_migrations() -> None:
    """Mini-migración idempotente para SQLite (sin Alembic).

    Agrega columnas que fueron introducidas después del build inicial sin
    tocar las filas existentes. Falla silenciosamente si la columna ya
    existe (idempotente bajo múltiples re-arranques).
    """
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return  # Base.metadata.create_all aún no corrió, se hace después.
    cols = {c["name"] for c in inspector.get_columns("users")}
    statements: list[str] = []
    if "must_change_password" not in cols:
        statements.append(
            "ALTER TABLE users ADD COLUMN must_change_password BOOLEAN NOT NULL DEFAULT TRUE"
        )
    if statements:
        with engine.begin() as conn:
            for stmt in statements:
                try:
                    conn.execute(text(stmt))
                except Exception as e:
                    print(f"⚠️  Migration skipped ({e.__class__.__name__}): {stmt}")

    # Migración específica para verification_codes.expires_at
    if "verification_codes" in inspector.get_table_names():
        vc_cols = {c["name"] for c in inspector.get_columns("verification_codes")}
        vc_statements: list[str] = []
        if "expires_at" not in vc_cols:
            vc_statements.append(
                "ALTER TABLE verification_codes ADD COLUMN expires_at TIMESTAMP"
            )
        if vc_statements:
            with engine.begin() as conn:
                for stmt in vc_statements:
                    try:
                        conn.execute(text(stmt))
                    except Exception as e:
                        print(f"⚠️  VC Migration skipped ({e.__class__.__name__}): {stmt}")


def _production_guards() -> None:
    """Fail-fast checks que se ejecutan siempre. En modo dev son no-op;
    en modo producción (case-insensitive vía is_production()), lanzan
    RuntimeError si la configuración es insegura o llevaría a lockouts.

    Errores hard (raise):
      - BOOTSTRAP_TOKEN vacío: sin él no se puede crear el primer admin
        y /auth/setup devuelve 404 → lockout total del panel admin.
      - CORS_ORIGINS '*' o vacío en producción: expone la API a cualquier
        origen web (XSS-magnifier en combinación con JWT en localStorage).
      - SECRET_KEY default ("CHANGE-ME..."): un atacante con acceso al
        código puede firmar tokens válidos.

    Advertencias soft (print): configuración de proxy reverso, porque
    depende del entorno del operador y se documenta en PRODUCTION.md.
    """
    if not is_production():
        return  # Solo se aplica en modo producción (case-insensitive).

    problems: list[str] = []

    # 1. BOOTSTRAP_TOKEN: previene lockout.
    if not (settings.bootstrap_token or "").strip():
        problems.append(
            "BOOTSTRAP_TOKEN está vacío. En producción no se puede "
            "llamar a POST /auth/setup para crear el admin inicial → "
            "lockout total del panel admin.\n"
            "  Generá uno con: python -c \"import secrets; "
            "print(secrets.token_urlsafe(32))\""
        )

    # 2. CORS_ORIGINS: '*' o vacío en prod = XSS-magnifier.
    cors = (settings.cors_origins or "").strip()
    if cors == "" or cors == "*":
        problems.append(
            f"CORS_ORIGINS={cors!r}. En producción eso expone la API a "
            "cualquier origen web. Definí una lista explícita, ej.: "
            "CORS_ORIGINS=https://app.tu-dominio.com"
        )

    # 3. SECRET_KEY: default detectable.
    if settings.secret_key.startswith(DEV_SECRET_PREFIX):
        problems.append(
            "SECRET_KEY usa el valor por defecto. Cualquiera con acceso "
            "al código puede firmar tokens JWT válidos.\n"
            "  Generá uno con: python -c \"import secrets; "
            "print(secrets.token_urlsafe(64))\""
        )

    if problems:
        sep = "\n\n  ✗ "
        msg = (
            "╔════════════════════════════════════════════════════════════╗\n"
            "║  ARRANQUE BLOQUEADO — configuración insegura para prod     ║\n"
            "╚════════════════════════════════════════════════════════════╝\n\n"
            f"  ✗ {sep.join(problems)}\n\n"
            "  Corregí las variables de entorno en .env y volvé a arrancar.\n"
            "  Ver docs/07-DEPLOY.md para el checklist completo."
        )
        raise RuntimeError(msg)


def _print_proxy_headers_guidance() -> None:
    """Recordatorio sobre cómo arrancar uvicorn según el escenario de
    proxy. Esto NO valida — uvicorn no expone introspección de sus flags
    runtime — pero reduce el riesgo de deploy silenciosamente
    incorrecto."""
    if not is_production():
        return  # En dev la guía T12 ya cubre el caso.
    trusted = (settings.trusted_proxies or "").strip()
    if trusted:
        print(
            "ℹ️  TRUSTED_PROXIES configurado. Asegurate de lanzar uvicorn con "
            "el flag --proxy-headers y --forwarded-allow-ips adecuado "
            "(ver docs/07-DEPLOY.md §3)."
        )
    else:
        print(
            "ℹ️  TRUSTED_PROXIES está vacío. Si NO usás un reverse proxy, "
            "lanzá uvicorn con --proxy-headers=false --forwarded-allow-ips=\"\"\n"
            "   Si SÍ usás un proxy, configurá TRUSTED_PROXIES con la "
            "IP/CIDR del LB y lanzá con --proxy-headers "
            "--forwarded-allow-ips=<IP/CIDR>.\n"
            "   Ver docs/07-DEPLOY.md §3 para más detalle."
        )


def _print_startup_banner() -> None:
    """Banner resumen del modo de operación al arrancar. Sólo se imprime
    al final del lifespan (después de guards exitosos) para que el operador
    vea primero los errores de configuración si los hubiera."""
    env = "PRODUCCIÓN" if is_production() else "DESARROLLO"
    cors = _cors_origins()
    cors_repr = "*" if cors == ["*"] else f"{len(cors)} orígenes"
    print("─" * 60)
    print(f"  VeriCode arrancando en modo: {env}")
    print(f"  CORS origins: {cors_repr}")
    print(f"  Bootstrap token: {'set' if settings.bootstrap_token else 'EMPTY ⚠️'}")
    print(
        f"  Rate-limit /auth/token: "
        f"{settings.auth_rate_limit_max_attempts} intentos / "
        f"{settings.auth_rate_limit_window_minutes} min"
    )
    print(
        f"  JWT expiración: "
        f"{settings.access_token_expire_minutes} min"
    )
    if env == "PRODUCCIÓN":
        print("  ⚠️  Modo producción — todas las safeguards activas.")
    print("─" * 60)


async def _cleanup_task():
    """Limpieza periódica: purga códigos viejos y anonymiza raw_body."""
    while True:
        try:
            await asyncio.sleep(settings.cleanup_interval_minutes * 60)
            db = SessionLocal()
            try:
                now = datetime.utcnow()
                # Anonymizar raw_body de códigos con más de raw_body_retention_minutes
                cutoff_raw = now - timedelta(minutes=settings.raw_body_retention_minutes)
                db.query(VerificationCode).filter(
                    VerificationCode.received_at < cutoff_raw,
                    VerificationCode.raw_body.isnot(None),
                ).update(
                    {VerificationCode.raw_body: None},
                    synchronize_session=False,
                )
                # Eliminar códigos más antiguos que code_retention_days
                cutoff_delete = now - timedelta(days=settings.code_retention_days)
                deleted = db.query(VerificationCode).filter(
                    VerificationCode.received_at < cutoff_delete
                ).delete(synchronize_session=False)
                db.commit()
                if deleted:
                    print(f"  🧹 Limpieza: {deleted} códigos antiguos purgados")
            except Exception as e:
                print(f"  ⚠️ Error en limpieza: {e}")
                db.rollback()
            finally:
                db.close()
        except asyncio.CancelledError:
            break


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validar secrets al arranque. Modo estricto se activa automáticamente
    # si detecta cualquier secreto de dev (defense in depth: el operador
    # no tiene que recordar setear una env extra).
    looks_insecure = (
        settings.secret_key.startswith(DEV_SECRET_PREFIX)
        or settings.fernet_key == DEV_FERNET_MARKER
    )
    # is_production() es case-insensitive y evita el bug donde
    # VERICODE_ENV="Production" (capital P) bypaseaba esta rama.
    strict_secrets = looks_insecure or is_production()

    # Fail-fast en producción: BOOTSTRAP_TOKEN vacío, CORS=*, SECRET_KEY
    # default. Lanza RuntimeError → uvicorn no termina de arrancar.
    # DEBE correr ANTES del banner: si falla, queremos el error primero,
    # y el banner al final como confirmación de "arranque exitoso en modo X".
    _production_guards()
    # Guía soft sobre flags de uvicorn (solo si pasó _production_guards).
    _print_proxy_headers_guidance()

    validate_fernet_key(strict=strict_secrets)

    Base.metadata.create_all(bind=engine)
    # Mini-migración para columnas añadidas después del create_all inicial.
    _run_user_migrations()
    seed_platforms()
    seed_admin()
    # Banner se imprime al final, sólo si todo lo anterior pasó: es la
    # confirmación visible para el operador de que arrancó en modo X.
    _print_startup_banner()
    # Registrar el handler y arrancar IDLE watchers.
    poller.on_new_code(broadcast_new_code_handler)
    await poller.start()
    # Arrancar tarea de limpieza en segundo plano
    cleanup = asyncio.create_task(_cleanup_task())
    yield
    poller.stop()
    cleanup.cancel()


app = FastAPI(
    title="Sistema de Códigos de Verificación",
    description="Monitoreo de correos para extracción de códigos de verificación",
    version="1.0.0",
    lifespan=lifespan,
)

_cors_list, _cors_credentials = _resolve_cors()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_list,
    allow_credentials=_cors_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
# GZipMiddleware: comprime responses JSON grandes (listas de códigos,
# listados de cuentas). min_size=500 evita comprimir responses triviales
# donde el overhead del gzip es mayor al beneficio.
app.add_middleware(GZipMiddleware, minimum_size=500)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(email_accounts.router, prefix="/api/v1")
app.include_router(platforms.router, prefix="/api/v1")
app.include_router(codes.router, prefix="/api/v1")
app.include_router(public.router, prefix="/api/v1")


# --------------------------------------------------------------------------
# Seeds
# --------------------------------------------------------------------------
def seed_platforms():
    db = SessionLocal()
    try:
        existing = db.query(Platform).count()
        if existing > 0:
            return

        default_platforms = [
            Platform(name="netflix", display_name="Netflix", provider_type="streaming", icon="netflix", code_pattern=r"\b(\d{6})\b", sender_pattern=r"@(netflix\.com|account\.netflix\.com)", subject_pattern=r"(c[oó]digo|verificaci[oó]n|verification)"),
            Platform(name="disney_plus", display_name="Disney+", provider_type="streaming", icon="disney", code_pattern=r"\b(\d{6})\b", sender_pattern=r"@(disneyplus\.com|disney\.com)", subject_pattern=r"(c[oó]digo|verificaci[oó]n|verification)"),
            Platform(name="hbo_max", display_name="HBO Max", provider_type="streaming", icon="hbo", code_pattern=r"\b(\d{6})\b", sender_pattern=r"@(hbomax\.com|hbo\.com)", subject_pattern=r"(c[oó]digo|verificaci[oó]n|verification)"),
            Platform(name="prime_video", display_name="Prime Video", provider_type="streaming", icon="prime", code_pattern=r"\b(\d{6})\b", sender_pattern=r"@(primevideo\.com|amazon\.com)", subject_pattern=r"(c[oó]digo|verificaci[oó]n|otp|verification)"),
            Platform(name="spotify", display_name="Spotify", provider_type="streaming", icon="spotify", code_pattern=r"\b(\d{6})\b", sender_pattern=r"@(spotify\.com)", subject_pattern=r"(c[oó]digo|verificaci[oó]n|verification)"),
            Platform(name="chatgpt", display_name="ChatGPT", provider_type="ai", icon="openai", code_pattern=r"\b(\d{6})\b", sender_pattern=r"@(openai\.com|chatgpt\.com)", subject_pattern=r"(c[oó]digo|verificaci[oó]n|verification|login)"),
            Platform(name="claude", display_name="Claude AI", provider_type="ai", icon="anthropic", code_pattern=r"\b(\d{6})\b", sender_pattern=r"@(anthropic\.com|claude\.ai)", subject_pattern=r"(c[oó]digo|verificaci[oó]n|verification)"),
            Platform(name="midjourney", display_name="Midjourney", provider_type="ai", icon="midjourney", code_pattern=r"\b(\d{6})\b", sender_pattern=r"@(midjourney\.com)", subject_pattern=r"(c[oó]digo|verificaci[oó]n|verification)"),
            Platform(name="paramount", display_name="Paramount+", provider_type="streaming", icon="paramount", code_pattern=r"\b(\d{6})\b", sender_pattern=r"@(paramountplus\.com|paramount\.com)", subject_pattern=r"(c[oó]digo|verificaci[oó]n|verification)"),
            Platform(name="crunchyroll", display_name="Crunchyroll", provider_type="streaming", icon="crunchyroll", code_pattern=r"\b(\d{6})\b", sender_pattern=r"@(crunchyroll\.com)", subject_pattern=r"(c[oó]digo|verificaci[oó]n|verification)"),
            Platform(name="google", display_name="Google", provider_type="google", icon="google", code_pattern=r"\b(\d{6})\b", sender_pattern=r"@(google\.com|accounts\.google\.com)", subject_pattern=r"(c[oó]digo|verificaci[oó]n|verification|otp)"),
        ]
        for p in default_platforms:
            db.add(p)
        db.commit()
        print(f"✅ {len(default_platforms)} plataformas creadas")
    finally:
        db.close()


def seed_admin():
    """Crea un admin por defecto SOLO en modo desarrollo y SOLO si la tabla
    está vacía (idempotente). En producción no auto-seedea: el operador
    debe correr POST /auth/setup con X-Bootstrap-Token para crear el admin.

    Flags:
    - is_admin=True
    - must_change_password=True: fuerza cambio en el próximo login.
    """
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return
        if is_production():
            print(
                "⚠️  PRODUCCIÓN sin admin: llamá POST /auth/setup con "
                "X-Bootstrap-Token (BOOTSTRAP_TOKEN) para crear el primero."
            )
            return
        admin = User(
            username="admin",
            password_hash=get_password_hash("admin123"),
            is_admin=True,
            must_change_password=True,
        )
        db.add(admin)
        db.commit()
        print(
            "✅ Usuario admin creado (dev: admin / admin123). "
            "Forzá cambio en el primer login."
        )
    finally:
        db.close()


# --------------------------------------------------------------------------
# Poller -> WebSocket bridge
# --------------------------------------------------------------------------
def broadcast_new_code_handler(code, db):
    """Handler registrado en el singleton poller. Devuelve una coroutine
    que `notify_new_code` va a `await`."""
    from app.api.v1.codes import broadcast_new_code

    async def _coro():
        await broadcast_new_code({
            "id": code.id,
            "code": code.code,
            "sender": code.sender,
            "subject": code.subject,
            "platform_name": code.platform.display_name if code.platform else "Desconocida",
            "platform_icon": code.platform.icon if code.platform else None,
            "email": code.email_account.email if code.email_account else "",
            "received_at": code.received_at.isoformat() if code.received_at else None,
        })

    return _coro()
