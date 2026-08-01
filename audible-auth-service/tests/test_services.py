import pytest
from app.database import init_db, SessionLocal
from app.services.storage_service import StorageService
from app.services.auth_service import AuthService
from app.services.library_service import LibraryService
from app.services.download_service import DownloadService
from app.models import User, Token, Book, Setting


@pytest.fixture
def db_session():
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_storage_service_sanitize_folder_name():
    assert StorageService.sanitize_folder_name('Title: Subtitle? / Test*') == 'Title Subtitle  Test'
    assert StorageService.sanitize_folder_name('') == 'Unknown'


def test_storage_service_get_settings(db_session):
    conf = StorageService.get_configured_settings(db_session)
    assert 'download_dir' in conf
    assert 'activation_bytes' in conf


def test_storage_service_browse_directories():
    res = StorageService.browse_directories()
    assert 'drives' in res
    assert 'directories' in res


def test_auth_service_status(db_session):
    db_session.query(Token).delete()
    db_session.query(User).delete()
    db_session.commit()

    service = AuthService(db_session)
    status = service.get_auth_status()
    assert status['has_active_token'] is False

    user = User(email="test@audible.com.br", marketplace="br")
    db_session.add(user)
    db_session.commit()
    token = Token(user_id=user.id, access_token="encrypted_access_token")
    db_session.add(token)
    db_session.commit()

    assert service.is_authenticated() is True
    status_auth = service.get_auth_status()
    assert status_auth['has_active_token'] is True
    assert status_auth['email'] == "test@audible.com.br"


def test_expired_token_purging(db_session):
    from datetime import datetime, timedelta, timezone
    db_session.query(Token).delete()
    db_session.query(User).delete()
    db_session.commit()

    user = User(email="expired@audible.com.br", marketplace="br")
    db_session.add(user)
    db_session.commit()

    past_date = datetime.now(timezone.utc) - timedelta(days=1)
    token = Token(user_id=user.id, access_token="expired_token", expires_at=past_date)
    db_session.add(token)
    db_session.commit()

    service = AuthService(db_session)
    assert service.is_authenticated() is False
    assert db_session.query(Token).count() == 0


def test_library_service_stored_books(db_session):
    service = LibraryService(db_session)
    books = service.get_stored_books()
    assert isinstance(books, list)


def test_download_service_cancel_and_delete_non_existent(db_session):
    with pytest.raises(ValueError):
        DownloadService.cancel_download("INVALID_ASIN", db_session)

    with pytest.raises(ValueError):
        DownloadService.delete_download_file("INVALID_ASIN", db_session)
