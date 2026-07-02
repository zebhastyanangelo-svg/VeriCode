"""Launcher de backend con patch imaplib para tests E2E.

Parchea `imaplib.IMAP4_SSL` para que sea `imaplib.IMAP4` (sin TLS),
luego arranca uvicorn. Sólo se usa para tests; nunca en producción.
"""
import imaplib

# Patch ANTES de importar app (para que imap_poller use IMAP4 plano).
imaplib.IMAP4_SSL = imaplib.IMAP4  # type: ignore

import os
import sys
from pathlib import Path

# Asegurar CWD = backend (para que sqlite:///./codigos.db funcione).
BACKEND_DIR = Path(__file__).resolve().parent
os.chdir(BACKEND_DIR)
sys.path.insert(0, str(BACKEND_DIR))

# Variables de entorno explícitas del test.
os.environ.setdefault("DATABASE_URL", "sqlite:///./codigos_e2e.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production-32chars")
os.environ.setdefault("POLL_INTERVAL_SECONDS", "3600")  # No auto-poll durante E2E.
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")

import uvicorn  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("BACKEND_PORT", "8765"))
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
        access_log=True,
        # CRÍTICO para que el fix de X-Forwarded-For funcione en el E2E:
        # uvicorn trae ProxyHeadersMiddleware HABILITADO por defecto y
        # sobreescribe `scope["client"]` con la IP del header cuando viene
        # de 127.0.0.1 (forwarded_allow_ips="127.0.0.1"). Esto neutraliza
        # nuestra logic de `client_ip(request)`. Desactivamos ambos flags:
        proxy_headers=False,
        forwarded_allow_ips="",
    )
