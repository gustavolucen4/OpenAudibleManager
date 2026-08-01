import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db, SessionLocal
from app.models import User, Book, Token

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

client = TestClient(app)


def test_library_ui_endpoint():
    db = SessionLocal()
    user = User(email="ui_test@audible.com.br", marketplace="br")
    db.add(user)
    db.commit()
    user_id = user.id
    token = Token(user_id=user_id, access_token="fake_access_token")
    db.add(token)
    db.commit()
    db.close()

    response = client.get("/audible/library-ui")
    assert response.status_code == 200
    assert "OpenAudible Manager" in response.text
    assert "Sincronizar Biblioteca" in response.text

    db = SessionLocal()
    db.query(Token).filter(Token.user_id == user_id).delete()
    db.query(User).filter(User.id == user_id).delete()
    db.commit()
    db.close()


def test_stored_books_empty():
    response = client.get("/audible/books")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_book_model_persistence():
    import uuid
    db = SessionLocal()
    unique_email = f"user_{uuid.uuid4().hex[:8]}@audible.com.br"
    user = User(email=unique_email, marketplace="br")
    db.add(user)
    db.commit()

    test_asin = f"B08{uuid.uuid4().hex[:6]}"
    book = Book(
        asin=test_asin,
        title="Audiolivro de Teste",
        authors="Autor Exemplo",
        narrators="Narrador Exemplo",
        duration_ms=3600000,
        user_id=user.id
    )
    db.add(book)
    db.commit()

    fetched = db.query(Book).filter(Book.asin == test_asin).first()
    assert fetched is not None
    assert fetched.title == "Audiolivro de Teste"
    assert fetched.download_status == "not_downloaded"
    
    db.delete(fetched)
    db.delete(user)
    db.commit()
    db.close()


def test_auto_discovery_of_existing_file(tmp_path):
    import os, uuid
    db = SessionLocal()
    unique_email = f"user_{uuid.uuid4().hex[:8]}@audible.com.br"
    user = User(email=unique_email, marketplace="br")
    db.add(user)
    db.commit()

    test_asin = f"B09{uuid.uuid4().hex[:6]}"
    book = Book(
        asin=test_asin,
        title="Livro Existente no Disco",
        authors="Autor Desconhecido",
        download_status="not_downloaded",
        user_id=user.id
    )
    db.add(book)

    from app.models import Setting
    s = db.query(Setting).filter(Setting.key == "download_dir").first()
    if not s:
        s = Setting(key="download_dir", value=str(tmp_path))
        db.add(s)
    else:
        s.value = str(tmp_path)
    db.commit()

    dummy_dir = tmp_path / "Autor Desconhecido" / "Livro Existente no Disco"
    dummy_dir.mkdir(parents=True, exist_ok=True)
    dummy_file = dummy_dir / "Livro Existente no Disco.m4b"
    dummy_file.write_text("fake m4b audio content")

    from app.services.library_service import LibraryService
    srv = LibraryService(db)
    srv.sync_local_disk_status()

    updated_book = db.query(Book).filter(Book.asin == test_asin).first()
    assert updated_book is not None
    assert updated_book.download_status == "downloaded"
    assert updated_book.local_path == str(dummy_file)

    db.delete(updated_book)
    db.delete(user)
    db.commit()
    db.close()
