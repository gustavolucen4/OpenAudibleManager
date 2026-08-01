import base64
import hashlib
from cryptography.fernet import Fernet
from app.config import settings


def _get_fernet() -> Fernet:
    key_str = getattr(settings, "ENCRYPTION_KEY", None) or getattr(settings, "SECRET_KEY", "default-audible-auth-secret-key-32b")
    key_bytes = key_str.encode('utf-8')
    try:
        return Fernet(key_bytes)
    except Exception:
        hashed = hashlib.sha256(key_bytes).digest()
        return Fernet(base64.urlsafe_b64encode(hashed))


def encrypt_data(plain_text: str) -> str:
    """Encrypt a plain text string using Fernet (AES-128 in CBC mode with HMAC)."""
    if not plain_text:
        return ""
    fernet = _get_fernet()
    return fernet.encrypt(plain_text.encode('utf-8')).decode('utf-8')


def decrypt_data(cipher_text: str) -> str:
    """Decrypt a Fernet cipher text back to plain text."""
    if not cipher_text:
        return ""
    fernet = _get_fernet()
    return fernet.decrypt(cipher_text.encode('utf-8')).decode('utf-8')
