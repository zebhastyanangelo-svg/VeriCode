import asyncio
import logging
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

logger = logging.getLogger(__name__)


def _create_engine():
    url = settings.database_url
    if url.startswith("postgresql"):
        return create_engine(
            url,
            pool_size=1,
            max_overflow=0,
            pool_pre_ping=True,
            pool_recycle=600,
            pool_timeout=45,
            connect_args={"connect_timeout": 15, "sslmode": "require"},
        )
    return create_engine(url, pool_pre_ping=True)


engine = _create_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def db_keepalive():
    """Mantiene al menos una conexión activa en el pool para evitar
    la latencia de ~19s al conectar desde Render Oregon a Supabase us-east-2."""
    while True:
        try:
            t0 = time.monotonic()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            elapsed = time.monotonic() - t0
            logger.debug("DB keepalive OK (%.2fs)", elapsed)
        except Exception as exc:
            logger.warning("DB keepalive error: %s", exc)
        await asyncio.sleep(25)
