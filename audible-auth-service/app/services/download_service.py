import os
import asyncio
import httpx
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import User, Token, Book
from app.audible_client import AudibleAuthManager
from app.services.storage_service import StorageService


class DownloadService:
    """Service responsible for audiobook file downloads, streaming, cancellation, decryption, and FFmpeg conversions."""

    @staticmethod
    def extract_aaxc_credentials(client: Any, license_info: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Decrypts the AAXC license voucher using python-audible's decrypt_voucher_from_licenserequest."""
        try:
            from audible.aescipher import decrypt_voucher_from_licenserequest
            raw_res = license_info.get("raw_response")
            if not raw_res:
                return None

            auth = getattr(client, "auth", None)
            if not auth:
                return None

            if not getattr(auth, "customer_info", None):
                allowed_users = raw_res.get("content_license", {}).get("allowed_users", [])
                if allowed_users:
                    auth.customer_info = {"user_id": allowed_users[0]}

            if not getattr(auth, "device_info", None):
                auth.device_info = {
                    "device_type": "A2CZJZGLK2JJVM",
                    "device_name": "Audible for iPhone",
                    "device_serial_number": "Mg=="
                }

            voucher = decrypt_voucher_from_licenserequest(auth, raw_res)
            key = voucher.get("key")
            iv = voucher.get("iv")
            if key and iv:
                return {"key": key, "iv": iv}
        except Exception as e:
            print(f"AAXC voucher decryption note: {e}")

        return None

    @classmethod
    async def execute_audiobook_download(cls, asin: str, db_factory: Any) -> None:
        """Background task executing real download, streaming progress, and conversion."""
        db = db_factory()
        try:
            book = db.query(Book).filter(Book.asin == asin).first()
            if not book:
                return

            user = db.query(User).filter(User.id == book.user_id).first()
            token_record = db.query(Token).filter(Token.user_id == user.id).first() if user else None
            if not user or not token_record or not token_record.access_token:
                book.download_status = "error"
                db.commit()
                return

            client = AudibleAuthManager.get_client_from_encrypted_tokens(
                token_record=token_record,
                marketplace=user.marketplace
            )

            license_info = AudibleAuthManager.get_download_license(client, asin)
            offline_url = license_info["offline_url"]

            conf = StorageService.get_configured_settings(db)
            base_dir = conf["download_dir"]
            activation_bytes = conf["activation_bytes"]

            clean_author = StorageService.sanitize_folder_name(book.authors or "Audible")
            clean_title = StorageService.sanitize_folder_name(book.title or asin)
            output_dir = os.path.join(base_dir, clean_author, clean_title)
            os.makedirs(output_dir, exist_ok=True)

            aax_file_path = os.path.join(output_dir, f"{clean_title}.aax")
            part_file_path = os.path.join(output_dir, f"{clean_title}.aax.part")
            m4b_file_path = os.path.join(output_dir, f"{clean_title}.m4b")

            headers = {
                "User-Agent": "Audible/3.58.0 (iPhone; iOS 16.0; Scale/3.00)"
            }

            async with httpx.AsyncClient(timeout=600.0, follow_redirects=True, headers=headers) as http_client:
                async with http_client.stream("GET", offline_url) as response:
                    response.raise_for_status()
                    total_bytes = int(response.headers.get("content-length", 0))
                    bytes_downloaded = 0

                    with open(part_file_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=1048576):
                            f.write(chunk)
                            bytes_downloaded += len(chunk)

                            if total_bytes > 0:
                                calc_progress = min(99, max(1, int((bytes_downloaded / total_bytes) * 100)))
                                if abs(calc_progress - book.download_progress) >= 1:
                                    db.refresh(book)
                                    if book.download_status != "downloading":
                                        break
                                    book.download_progress = calc_progress
                                    db.commit()

            db.refresh(book)
            if book.download_status != "downloading":
                if os.path.exists(part_file_path):
                    try: os.remove(part_file_path)
                    except Exception: pass
                return

            if os.path.exists(part_file_path):
                if os.path.exists(aax_file_path):
                    try: os.remove(aax_file_path)
                    except Exception: pass
                os.rename(part_file_path, aax_file_path)

            ffmpeg_bin = StorageService.find_ffmpeg()
            final_saved_path = aax_file_path
            aaxc_creds = None

            if ffmpeg_bin:
                aaxc_creds = cls.extract_aaxc_credentials(client, license_info)
                try:
                    if aaxc_creds:
                        cmd = [
                            ffmpeg_bin, "-y",
                            "-audible_key", aaxc_creds["key"],
                            "-audible_iv",  aaxc_creds["iv"],
                            "-i", aax_file_path,
                            "-c", "copy",
                            m4b_file_path
                        ]
                    elif activation_bytes:
                        cmd = [
                            ffmpeg_bin, "-y",
                            "-activation_bytes", activation_bytes,
                            "-i", aax_file_path,
                            "-c", "copy",
                            m4b_file_path
                        ]
                    else:
                        cmd = None

                    if cmd:
                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        await proc.communicate()
                        if proc.returncode == 0 and os.path.exists(m4b_file_path) and os.path.getsize(m4b_file_path) > 0:
                            os.remove(aax_file_path)
                            final_saved_path = m4b_file_path
                except Exception:
                    pass

            is_legacy_aax_unconverted = (
                final_saved_path == aax_file_path
                and aaxc_creds is None
                and not activation_bytes
                and ffmpeg_bin is not None
            )

            book.download_status = "needs_activation" if is_legacy_aax_unconverted else "downloaded"
            book.download_progress = 100
            book.local_path = os.path.abspath(final_saved_path)
            db.commit()

        except Exception as e:
            try:
                db.rollback()
                book = db.query(Book).filter(Book.asin == asin).first()
                if book:
                    book.download_status = "error"
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()

    @classmethod
    async def execute_aax_conversion(cls, asin: str, db_factory: Any) -> None:
        """Background task: converts an already-downloaded .aax to .m4b using activation_bytes."""
        db = db_factory()
        try:
            book = db.query(Book).filter(Book.asin == asin).first()
            if not book or not book.local_path or not os.path.exists(book.local_path):
                return

            conf = StorageService.get_configured_settings(db)
            activation_bytes = conf["activation_bytes"]
            if not activation_bytes:
                return

            ffmpeg_bin = StorageService.find_ffmpeg()
            if not ffmpeg_bin:
                return

            aax_path = book.local_path
            m4b_path = aax_path.replace(".aax", ".m4b") if aax_path.lower().endswith(".aax") else aax_path + ".m4b"

            book.download_status = "downloading"
            book.download_progress = 99
            db.commit()

            cmd = [
                ffmpeg_bin, "-y",
                "-activation_bytes", activation_bytes,
                "-i", aax_path,
                "-c", "copy",
                m4b_path
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            if proc.returncode == 0 and os.path.exists(m4b_path) and os.path.getsize(m4b_path) > 0:
                os.remove(aax_path)
                book.local_path = os.path.abspath(m4b_path)
                book.download_status = "downloaded"
            else:
                book.download_status = "needs_activation"

            book.download_progress = 100
            db.commit()
        except Exception:
            pass
        finally:
            db.close()

    @staticmethod
    def cancel_download(asin: str, db: Session) -> Dict[str, str]:
        """Cancels an in-progress download and cleans up temporary partial files."""
        book = db.query(Book).filter(Book.asin == asin).first()
        if not book:
            raise ValueError("Audiolivro não encontrado.")

        local_p = book.local_path
        book.download_status = "not_downloaded"
        book.download_progress = 0
        book.local_path = None
        db.commit()

        if local_p and os.path.exists(local_p):
            StorageService.remove_file_and_empty_parents(local_p)

        return {"status": "cancelled", "asin": asin}

    @staticmethod
    def delete_download_file(asin: str, db: Session) -> Dict[str, str]:
        """Deletes the downloaded audiobook file from disk and resets book status."""
        book = db.query(Book).filter(Book.asin == asin).first()
        if not book:
            raise ValueError("Audiolivro não encontrado.")

        file_path = book.local_path
        if file_path and os.path.exists(file_path):
            StorageService.remove_file_and_empty_parents(file_path)

        book.download_status = "not_downloaded"
        book.download_progress = 0
        book.local_path = None
        db.commit()

        return {"status": "deleted", "asin": asin}
