import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models import User, Token
from app.audible_client import AudibleAuthManager
from app.amazon import create_auth_session, get_latest_pending_session, PENDING_SESSIONS


class AuthService:
    """Service responsible for user authentication, token persistence, and Amazon login flow."""

    def __init__(self, db: Session):
        self.db = db

    def is_authenticated(self) -> bool:
        """Returns True if there is an active valid user token stored in database."""
        user = self.db.query(User).first()
        if not user:
            return False

        token = self.db.query(Token).filter(Token.user_id == user.id).first()
        if not token or not token.access_token:
            return False

        # Check if expiration timestamp is past
        if token.expires_at:
            try:
                exp = token.expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp <= datetime.now(timezone.utc):
                    # Try refreshing token
                    if token.refresh_token:
                        try:
                            client = AudibleAuthManager.get_client_from_encrypted_tokens(token, user.marketplace)
                            client.auth.refresh_access_token()
                            from app.security import encrypt_data
                            token.access_token = encrypt_data(client.auth.access_token)
                            if client.auth.expires:
                                token.expires_at = datetime.fromtimestamp(client.auth.expires, timezone.utc)
                            self.db.commit()
                            return True
                        except Exception:
                            self.logout_user()
                            return False
                    else:
                        self.logout_user()
                        return False
            except Exception:
                pass

        return True

    def get_auth_status(self) -> Dict[str, Any]:
        """Returns status of stored tokens for active user."""
        has_auth = self.is_authenticated()
        user = self.db.query(User).first()
        if not user or not has_auth:
            return {
                "user_id": 0,
                "email": "nenhum",
                "marketplace": "br",
                "has_active_token": False,
                "expires_at": None
            }

        token = self.db.query(Token).filter(Token.user_id == user.id).first()
        return {
            "user_id": user.id,
            "email": user.email,
            "marketplace": user.marketplace,
            "has_active_token": True,
            "expires_at": token.expires_at if token else None
        }

    def process_manual_callback(
        self,
        response_url: str,
        session_id: Optional[str] = None,
        email_fallback: Optional[str] = "user@audible.com.br"
    ) -> Dict[str, Any]:
        """Processes redirected Amazon response URL and registers device tokens."""
        session_info = PENDING_SESSIONS.get(session_id) if session_id else get_latest_pending_session()
        if not session_info:
            raise ValueError("Nenhuma sessão de autorização pendente encontrada. Acesse /auth/login novamente.")

        auth_code = AudibleAuthManager.extract_code_from_redirect_url(response_url)
        token_data = AudibleAuthManager.register_device_and_get_tokens(
            authorization_code=auth_code,
            code_verifier=session_info["code_verifier"],
            domain=session_info["domain"],
            serial=session_info["serial"]
        )

        customer_info = token_data.get("raw_customer_info", {})
        user_email = customer_info.get("email") or email_fallback or "user@audible.com.br"

        user = self.db.query(User).filter(User.email == user_email).first()
        if not user:
            user = User(email=user_email, marketplace=session_info["marketplace"])
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

        token_record = self.db.query(Token).filter(Token.user_id == user.id).first()
        if not token_record:
            token_record = Token(user_id=user.id)
            self.db.add(token_record)

        token_record.access_token = token_data["access_token"]
        token_record.refresh_token = token_data["refresh_token"]
        token_record.adp_token = token_data["adp_token"]
        token_record.device_private_key = token_data["device_private_key"]
        token_record.website_cookies = token_data["website_cookies"]
        token_record.device_info = token_data.get("device_info")
        token_record.customer_info = token_data.get("customer_info")

        exp = token_data.get("expires")
        if exp:
            if isinstance(exp, (int, float)):
                token_record.expires_at = datetime.fromtimestamp(exp, timezone.utc)
            elif isinstance(exp, datetime):
                token_record.expires_at = exp

        self.db.commit()

        if session_id in PENDING_SESSIONS:
            del PENDING_SESSIONS[session_id]

        user_name = customer_info.get("given_name", "Usuário")
        return {
            "user_name": user_name,
            "user_email": user_email
        }

    def logout_user(self) -> None:
        """Deletes stored authentication tokens and user records."""
        try:
            self.db.query(Token).delete()
            self.db.query(User).delete()
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
