import unicodedata

from pydantic_settings import BaseSettings


# --------------------------------------------------------------------------
# Markers de defaults inseguros
# --------------------------------------------------------------------------
# Promoción de los valores que la clase Settings usa como default de dev a
# constantes públicas. Centralizar acá evita que `main.py` duplique los
# strings (que pueden quedar desincronizados y hacer inerte el detector de
# "looks_insecure").
DEV_SECRET_PREFIX: str = "CHANGE-ME"
DEV_FERNET_MARKER: str = "2s9SHRQ36vwyY1g8VZEiVCdJ7W7Czt7ynFfv4vsyiZg="


# --------------------------------------------------------------------------
# Detección case-insensitive del modo producción
# --------------------------------------------------------------------------
# Cualquier variante ortográfica de "production" debe disparar el modo
# estricto. Esto evita el footgun donde un operador setea
# VERICODE_ENV="Production" y queda fuera de las guards (banner dice
# "PRODUCTION" pero `_production_guards()` y `seed_admin()` la
# comparación exacta `== "production"` fallan → admin auto-creado,
# fail-fast inerte).
_PRODUCTION_ALIASES: frozenset[str] = frozenset({
    "production",
    "prod",
})


def _normalize_env_value(s: str) -> str:
    """Lowercase + strip + remover diacríticos para tolerar typos comunes.

    "PRODUCTION", "Production", "producción", "Producción" → todas dan
    "production". El comportement fail-safe: si un operador pierde el
    acento ("Produccion"), el sistema se queda en dev (más permisivo,
    seguro por default) — preferible a un falso positivo en prod.
    """
    return (
        unicodedata.normalize("NFKD", (s or "").strip().lower())
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def is_production() -> bool:
    """Devuelve True si `vericode_env` está seteado a cualquier variante
    case-insensitive y ortográfica de "producción".

    Usar SIEMPRE esta función (nunca comparar `settings.vericode_env ==
    "production"` directo) para evitar el bug case-sensitive.
    """
    return _normalize_env_value(settings.vericode_env) in _PRODUCTION_ALIASES


class Settings(BaseSettings):
    app_name: str = "Sistema de Códigos de Verificación"
    database_url: str = "sqlite:///./codigos.db"
    # En producción, definir SECRET_KEY y FERNET_KEY en .env.
    # Generar nuevas claves con:
    #   SECRET_KEY: cualquier string aleatorio largo
    #   FERNET_KEY: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    secret_key: str = "CHANGE-ME-dev-secret-key-do-not-use-in-production-please"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    poll_interval_seconds: int = 30
    # Tiempo máximo en segundos para cada ciclo IDLE (RFC 2177: max 29 min).
    # Por defecto 28 min (1680 s). El servidor notifica al cliente en tiempo
    # real cuando llega un correo, eliminando la necesidad de sondeo periódico.
    imap_idle_timeout: int = 1680
    # Clave Fernet válida de 32 bytes (base64 url-safe). Se usa para cifrar
    # las contraseñas IMAP en BD. Generar con:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # El default es sólo para DEV; auth/auth.py validará y hará raise si en
    # producción se deja sin configurar.
    fernet_key: str = DEV_FERNET_MARKER
    # Orígenes permitidos para CORS (separados por coma).
    cors_origins: str = "https://vericode.dpdns.org,http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    # ---------------------------------------------------------------
    # Seguridad
    # ---------------------------------------------------------------
    # Modo de operación. En cualquier variante de "production" (case-
    # insensitive, sin acentos, ver `is_production()` arriba) se endurecen
    # varios defaults:
    # - /auth/setup requiere BOOTSTRAP_TOKEN (devuelve 404 si no está seteada)
    # - auto-seed de admin en lifespan se desactiva (hay que usar /auth/setup)
    # - production_guards() corrobora BOOTSTRAP_TOKEN set, CORS_ORIGINS != '*',
    #   SECRET_KEY sin prefijo 'CHANGE-ME'.
    vericode_env: str = "development"
    # Token de bootstrap. Requerido en producción para crear el admin inicial.
    # Generar con: python -c "import secrets; print(secrets.token_urlsafe(32))"
    bootstrap_token: str = ""
    # Rate-limit del endpoint /auth/token (intentos fallidos por IP antes del lockout).
    auth_rate_limit_max_attempts: int = 5
    # Ventana del rate-limit, en minutos.
    auth_rate_limit_window_minutes: int = 15
    # Rate-limit para endpoints públicos (request-code, verify-email-access).
    public_rate_limit_max_attempts: int = 10
    public_rate_limit_window_minutes: int = 1
    # Tiempo de expiración de códigos no reclamados (en minutos).
    code_expiration_minutes: int = 30
    # Días que se conservan los códigos antes de purga automática.
    code_retention_days: int = 7
    # Minutos tras los cuales se anonymiza raw_body.
    raw_body_retention_minutes: int = 60
    # Intervalo entre limpiezas automáticas (en minutos).
    cleanup_interval_minutes: int = 60
    # ---------------------------------------------------------------
    # Reverse proxy / IP de cliente
    # ---------------------------------------------------------------
    # Lista de IPs/CIDRs/redes que consideramos proxies confiables (separados
    # por coma). Si la IP del socket del request matchea alguno, se acepta el
    # header configurado en `real_ip_header` para extraer la IP real del
    # cliente. En otro caso, se usa `client.host` directamente y cualquier
    # header de spoofing se ignora.
    # Valores: "" (deshabilitado, recomendado en dev), "*" (confiar en todo,
    # útil detrás de balanceadores gestionados tipo Render/Heroku/Cloudflare
    # donde la IP del LB es dinámica), o lista explícita (recomendado en prod
    # p.ej. "10.0.0.0/8,127.0.0.1/32").
    trusted_proxies: str = ""
    # Header HTTP del cual extraer la IP "real" del cliente. Por defecto
    # X-Forwarded-For. Configurable para stacks específicos:
    # - Cloudflare: "CF-Connecting-IP"
    # - NGINX proxy_set_header X-Real-IP: "X-Real-IP"
    # - Heroku / Render X-Forwarded-For: dejar default.
    real_ip_header: str = "X-Forwarded-For"

    class Config:
        env_file = ".env"


settings = Settings()
