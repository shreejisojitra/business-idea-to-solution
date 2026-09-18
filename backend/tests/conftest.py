import os
import sys
import pytest

# Ensure backend root directory is on Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import engine, Base, init_db, SessionLocal

@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    """Automatically initialize database schema cleanly before running tests."""
    Base.metadata.drop_all(bind=engine)
    init_db()


@pytest.fixture
def db():
    """Provides a fresh database session for tests requiring db fixture."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
