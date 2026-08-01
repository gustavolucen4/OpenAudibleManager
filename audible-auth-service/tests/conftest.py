"""
Shared pytest fixtures.
IMPORTANT: Tests MUST use the `db_session` fixture or manually
guard database mutations with try/finally so that the production
DB (data/auth.db) is never left in a corrupted state.
"""
import os
import pytest
from app.database import SessionLocal, init_db


@pytest.fixture(autouse=True)
def ensure_db():
    """Ensure tables exist before every test."""
    init_db()
    yield


@pytest.fixture()
def db_session():
    """
    Provides a DB session that is always rolled back after the test.
    Use this for tests that mutate shared settings (e.g. download_dir).
    """
    db = SessionLocal()
    yield db
    db.rollback()
    db.close()
