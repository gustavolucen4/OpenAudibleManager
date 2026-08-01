import os
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models import User, Token, Book
from app.audible_client import AudibleAuthManager


class LibraryService:
    """Service responsible for managing audiobook library metadata, database synchronization, and status checks."""

    def __init__(self, db: Session):
        self.db = db

    def sync_local_disk_status(self) -> None:
        """
        Scans the currently configured download directory and matches existing audio files (.m4b, .aax, .aaxc)
        against stored books by ASIN, Title, and Author folder structure.
        """
        user = self.db.query(User).first()
        if not user:
            return

        from app.services.storage_service import StorageService
        conf = StorageService.get_configured_settings(self.db)
        base_dir = conf.get("download_dir")
        if not base_dir or not os.path.exists(base_dir):
            return

        books = self.db.query(Book).filter(Book.user_id == user.id).all()
        if not books:
            return

        updated = False

        # Build lookup set of existing audio files in base_dir
        existing_files = set()
        try:
            for root, _, files in os.walk(base_dir):
                for f in files:
                    if f.lower().endswith(('.m4b', '.aax', '.aaxc', '.mp3')):
                        existing_files.add(os.path.abspath(os.path.join(root, f)))
        except Exception:
            pass

        for book in books:
            # 1. Check if current local_path exists on disk
            if book.local_path and os.path.exists(book.local_path):
                # If file is .aax but converted .m4b exists, upgrade to .m4b
                if book.local_path.lower().endswith(".aax"):
                    m4b_path = book.local_path[:-4] + ".m4b"
                    if os.path.exists(m4b_path):
                        book.local_path = os.path.abspath(m4b_path)
                        book.download_status = "downloaded"
                        updated = True
                        continue

                book.download_status = "downloaded"
                continue

            # 2. Candidate paths in base_dir
            clean_author = StorageService.sanitize_folder_name(book.authors or "Audible")
            clean_title = StorageService.sanitize_folder_name(book.title or book.asin)
            clean_asin = (book.asin or "").strip()

            candidate_paths = [
                os.path.join(base_dir, clean_author, clean_title, f"{clean_title}.m4b"),
                os.path.join(base_dir, clean_author, clean_title, f"{clean_title}.aax"),
                os.path.join(base_dir, clean_title, f"{clean_title}.m4b"),
                os.path.join(base_dir, clean_title, f"{clean_title}.aax"),
                os.path.join(base_dir, f"{clean_title}.m4b"),
                os.path.join(base_dir, f"{clean_title}.aax"),
                os.path.join(base_dir, f"{clean_asin}.m4b"),
                os.path.join(base_dir, f"{clean_asin}.aax"),
            ]

            found_file = None
            for cp in candidate_paths:
                abs_cp = os.path.abspath(cp)
                if abs_cp in existing_files or os.path.exists(abs_cp):
                    found_file = abs_cp
                    break

            # 3. Fuzzy search in existing_files
            if not found_file and existing_files:
                for ef in existing_files:
                    ef_lower = ef.lower()
                    if (clean_asin and clean_asin.lower() in ef_lower) or (clean_title and len(clean_title) > 3 and clean_title.lower() in ef_lower):
                        found_file = ef
                        break

            if found_file:
                book.local_path = found_file
                book.download_status = "downloaded"
                book.download_progress = 100
                updated = True
            else:
                if book.download_status == "downloaded":
                    book.download_status = "not_downloaded"
                    book.download_progress = 0
                    book.local_path = None
                    updated = True

        if updated:
            try:
                self.db.commit()
            except Exception:
                self.db.rollback()

    def get_stored_books(self) -> List[Book]:
        """Fetches stored books from local database with dynamic file verification."""
        self.sync_local_disk_status()
        user = self.db.query(User).first()
        if not user:
            return []
        return self.db.query(Book).filter(Book.user_id == user.id).all()

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
