from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def init_engine(settings: Settings) -> None:
    """Build the engine + session factory. Call once at app startup."""
    global _engine, _SessionLocal
    _engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
    )
    _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False, future=True)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a Session and closes it after the request."""
    if _SessionLocal is None:
        raise RuntimeError("Database session factory not initialized. Did app startup run?")
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()


def ping() -> bool:
    """Cheap connectivity check for /health."""
    if _engine is None:
        return False
    from sqlalchemy import text

    with _engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return True
