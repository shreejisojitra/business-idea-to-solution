from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# SQLite needs check_same_thread=False; PostgreSQL needs pool settings
if _is_sqlite:
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
    """Dependency that provides a database session for requests."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Initialize database tables (development / SQLite only).

    In production with PostgreSQL, use Alembic migrations instead.
    This function is kept for backward-compatible local development.
    """
    import app.db.models  # noqa: F401 — registers all models with Base
    Base.metadata.create_all(bind=engine)

    # Lightweight column migration for SQLite dev databases that predate
    # the stage_statuses column.  Safe to run repeatedly — errors are swallowed.
    if _is_sqlite:
        from sqlalchemy import text
        try:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE blueprints ADD COLUMN stage_statuses JSON;"))
                conn.commit()
        except Exception:
            pass
