"""
Multi-database session wiring.

The AI service connects to THREE Postgres databases owned by the other microservices:
  * candidate  → hiremind_candidate  (candidate, parse_jobs, resume_embeddings, fake_profile_scores, …)
  * company    → hiremind_company    (jobs, job_embeddings, match_scores, ghost_job_scores, …)
  * users      → hiremind_users      (users; read-only, optional)

Each gets its own engine and sessionmaker. FastAPI dependencies in `app/api/v1/deps.py`
yield the correct session for each router. Repositories accept a `Session` and never
care which database it's bound to — they just operate on their declared tables.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings

# ── module-level engine + session-factory caches ─────────────────────────────
_engines: dict[str, Engine] = {}
_factories: dict[str, sessionmaker[Session]] = {}


def init_engine(settings: Settings) -> None:
    """Build engines + session factories for every DB. Call once at app startup."""
    _build("candidate", settings.candidate_database_url)
    _build("company", settings.company_database_url)
    _build("users", settings.users_database_url)


def _build(name: str, url: str) -> None:
    engine = create_engine(url, pool_pre_ping=True, future=True)
    _engines[name] = engine
    _factories[name] = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False, future=True
    )


def _yield(name: str) -> Iterator[Session]:
    factory = _factories.get(name)
    if factory is None:
        raise RuntimeError(
            f"Database '{name}' session factory not initialized. Did app startup run?"
        )
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_candidate_session() -> Iterator[Session]:
    """FastAPI dep: yields a Session bound to hiremind_candidate."""
    yield from _yield("candidate")


def get_company_session() -> Iterator[Session]:
    """FastAPI dep: yields a Session bound to hiremind_company."""
    yield from _yield("company")


def get_users_session() -> Iterator[Session]:
    """FastAPI dep: yields a Session bound to hiremind_users (read-only)."""
    yield from _yield("users")


def ping() -> dict[str, bool]:
    """Check connectivity to every wired DB. Used by /health."""
    from sqlalchemy import text

    out: dict[str, bool] = {}
    for name, engine in _engines.items():
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            out[name] = True
        except Exception:
            out[name] = False
    return out
