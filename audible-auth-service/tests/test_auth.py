import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import init_db
from app.security import encrypt_data, decrypt_data
from app.amazon import create_auth_session

@pytest.fixture(autouse=True)
def setup_db():
    init_db()

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/", follow_redirects=True)
    assert response.status_code == 200
    assert "OpenAudible Manager" in response.text


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_security_encryption():
    secret_text = "test_token_12345_sample"
    encrypted = encrypt_data(secret_text)
    assert encrypted != secret_text
    decrypted = decrypt_data(encrypted)
    assert decrypted == secret_text


def test_amazon_url_builder():
    session_id, url, session_info = create_auth_session("br")
    assert "https://www.amazon.com.br/ap/signin" in url
    assert "openid.assoc_handle=amzn_audible_ios_br" in url
    assert "openid.ns" in url
    assert session_info["domain"] == "com.br"


def test_login_page_html():
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert "OpenAudible Manager" in response.text
    assert "Audible Brasil" in response.text


def test_auth_status_empty():
    response = client.get("/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert "has_active_token" in data
