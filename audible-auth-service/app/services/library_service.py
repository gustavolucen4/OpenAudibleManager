import os
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models import User, Token, Book
from app.audible_client import AudibleAuthManager


class LibraryService:
    """Service responsible for managing audiobook library metadata, database synchronization, and status checks."""

    def __init__(self, db: Session):
        self.db = db

    def get_stored_books(self) -> List[Book]:
        """Fetches stored books from local database with dynamic file verification."""
        user = self.db.query(User).first()
        if not user:
            return []

        books = self.db.query(Book).filter(Book.user_id == user.id).all()
        updated = False

        for book in books:
            if book.download_status == "downloaded":
                if not book.local_path or not os.path.exists(book.local_path):
                    # Check if converted from .aax to .m4b automatically
                    if book.local_path and book.local_path.lower().endswith(".aax"):
                        m4b_path = book.local_path[:-4] + ".m4b"
                        if os.path.exists(m4b_path):
                            book.local_path = os.path.abspath(m4b_path)
                            updated = True
                            continue

                    # File deleted externally -> reset status
                    book.download_status = "not_downloaded"
                    book.download_progress = 0
                    book.local_path = None
                    updated = True

        if updated:
            self.db.commit()

        return books

    def sync_user_library(self) -> Dict[str, Any]:
        """Synchronizes local database library with Audible API."""
        user = self.db.query(User).first()
        if not user:
            raise ValueError("Nenhum usuário cadastrado. Realize o login em /auth/login primeiro.")

        token_record = self.db.query(Token).filter(Token.user_id == user.id).first()
        if not token_record or not token_record.access_token:
            raise ValueError("Token de acesso inválido ou expirado. Faça login novamente.")

        client = AudibleAuthManager.get_client_from_encrypted_tokens(
            token_record=token_record,
            marketplace=user.marketplace
        )

        try:
            audible_books = AudibleAuthManager.fetch_full_library(client)
        except Exception as e:
            err_str = str(e)
            if "401" in err_str or "Invalid" in err_str or "token" in err_str.lower() or "unauthorized" in err_str.lower() or "expire" in err_str.lower():
                from app.services.auth_service import AuthService
                AuthService(self.db).logout_user()
                raise ValueError("Token de acesso expirado ou inválido. A sessão foi encerrada. Faça o login novamente em /auth/login.")
            raise

        added_count = 0
        updated_count = 0

        for item in audible_books:
            asin = item["asin"]
            existing = self.db.query(Book).filter(Book.user_id == user.id, Book.asin == asin).first()

            if existing:
                existing.title = item["title"]
                existing.subtitle = item["subtitle"]
                existing.authors = item["authors"]
                existing.narrators = item["narrators"]
                existing.duration_ms = item["duration_ms"]
                existing.cover_url = item["cover_url"]
                existing.release_date = item["release_date"]
                updated_count += 1
            else:
                new_book = Book(
                    user_id=user.id,
                    asin=asin,
                    title=item["title"],
                    subtitle=item["subtitle"],
                    authors=item["authors"],
                    narrators=item["narrators"],
                    duration_ms=item["duration_ms"],
                    cover_url=item["cover_url"],
                    release_date=item["release_date"],
                    download_status="not_downloaded",
                    download_progress=0
                )
                self.db.add(new_book)
                added_count += 1

        self.db.commit()

        total_books = self.db.query(Book).filter(Book.user_id == user.id).count()

        return {
            "status": "success",
            "added_count": added_count,
            "updated_count": updated_count,
            "total_books": total_books
        }

    def get_user_profile(self) -> Dict[str, Any]:
        """Fetches active user profile info."""
        user = self.db.query(User).first()
        if not user:
            return {
                "name": "Nenhum Usuário",
                "email": "",
                "marketplace": "br",
                "user_id": "0"
            }

        token_record = self.db.query(Token).filter(Token.user_id == user.id).first()
        if not token_record or not token_record.access_token:
            return {
                "name": user.email,
                "email": user.email,
                "marketplace": user.marketplace,
                "user_id": str(user.id)
            }

        try:
            client = AudibleAuthManager.get_client_from_encrypted_tokens(token_record, user.marketplace)
            profile = AudibleAuthManager.fetch_user_profile(client)
            return {
                "name": profile.get("given_name", user.email),
                "email": profile.get("email", user.email),
                "marketplace": user.marketplace,
                "user_id": str(user.id),
                "given_name": profile.get("given_name")
            }
        except Exception:
            return {
                "name": user.email,
                "email": user.email,
                "marketplace": user.marketplace,
                "user_id": str(user.id)
            }
