"""
Shared pytest fixtures.
Isolates test execution completely to test_runner.db so pytest
NEVER touches or clears the local production database (data/auth.db).
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base

TEST_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "test_runner.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Overrides app SessionLocal and engine for all tests to use test_runner.db."""
    Base.metadata.create_all(bind=test_engine)
    monkeypatch.setattr("app.database.SessionLocal", TestingSessionLocal)
    monkeypatch.setattr("app.database.engine", test_engine)
    monkeypatch.setattr("app.main.SessionLocal", TestingSessionLocal)
    from app.main import app
    from app.database import get_db
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
