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
            connect_args={"connect_timeout": 25, "sslmode": "require"},
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


def _warm_db_pool():
    """Crea una conexión y la devuelve al pool, dejándola lista para
    requests posteriores. El timeout largo (connect_timeout=25) es
    necesario porque Supabase pooler (us-east-2) tarda ~19s desde
    Render Oregon (us-west-2), y Render LB solo da ~15s."""
    t0 = time.monotonic()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    elapsed = time.monotonic() - t0
    logger.info("DB warm-up complete (%.2fs)", elapsed)


async def db_keepalive():
    """Mantiene al menos una conexión activa en el pool."""
    loop = asyncio.get_running_loop()
    while True:
        try:
            await loop.run_in_executor(None, _do_ping)
        except Exception as exc:
            logger.warning("DB keepalive error: %s", exc)
        await asyncio.sleep(25)


def _do_ping():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
