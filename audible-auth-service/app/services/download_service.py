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
    def _normalize_to_hex(val: Any) -> Optional[str]:
        """
        Normalize a key or IV value to lowercase hex string for FFmpeg.
        The Audible voucher returns key/iv as BASE64 strings.
        FFmpeg's -audible_key and -audible_iv flags REQUIRE HEX strings.
        This function handles: base64 str, already-hex str, or raw bytes.
        """
        import base64 as _b64
        if not val:
            return None
        if isinstance(val, bytes):
            return val.hex()
        if isinstance(val, str):
            val_clean = val.strip()
            # Check if already hex (only 0-9a-fA-F, even length, at least 16 chars)
            if len(val_clean) >= 16 and len(val_clean) % 2 == 0:
                try:
                    int(val_clean, 16)
                    return val_clean.lower()
                except ValueError:
                    pass
            # Try base64 decode
            try:
                decoded = _b64.b64decode(val_clean + "==")  # pad for safety
                if len(decoded) >= 8:
                    return decoded.hex()
            except Exception:
                pass
        return str(val)

    @staticmethod
    def extract_aaxc_credentials(client: Any, license_info: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Decrypts the AAXC license voucher using python-audible's decrypt_voucher_from_licenserequest.
        Returns {'key': '<hex>', 'iv': '<hex>'} for use with FFmpeg -audible_key / -audible_iv.
        The voucher key/iv are BASE64-encoded — must be converted to HEX for FFmpeg.
        """
        try:
            from audible.aescipher import decrypt_voucher_from_licenserequest
            raw_res = license_info.get("raw_response")
            if not raw_res:
                print("AAXC: No raw_response in license_info")
                return None

            content_license = raw_res.get("content_license", {})
            license_response_str = content_license.get("license_response", "")
            if not license_response_str:
                print("AAXC: license_response field is empty — legacy AAX DRM (needs activation_bytes)")
                return None

            auth = getattr(client, "auth", None)
            if not auth:
                print("AAXC: No auth on client")
                return None

            if not getattr(auth, "customer_info", None):
                allowed_users = content_license.get("allowed_users", [])
                if allowed_users:
                    auth.customer_info = {"user_id": allowed_users[0]}
                else:
                    print("AAXC: customer_info missing and no allowed_users found")

            if not getattr(auth, "device_info", None):
                auth.device_info = {
                    "device_type": "A2CZJZGLK2JJVM",
                    "device_name": "Audible for iPhone",
                    "device_serial_number": "Mg=="
                }

            voucher = decrypt_voucher_from_licenserequest(auth, raw_res)
            raw_key = voucher.get("key")
            raw_iv = voucher.get("iv")

            # CRITICAL: voucher returns key/iv as BASE64. FFmpeg needs HEX.
            key_hex = DownloadService._normalize_to_hex(raw_key)
            iv_hex = DownloadService._normalize_to_hex(raw_iv)

            if key_hex and iv_hex:
                print(f"AAXC: key/iv extracted and converted to hex (key_len={len(key_hex)}, iv_len={len(iv_hex)})")
                return {"key": key_hex, "iv": iv_hex}
            else:
                print(f"AAXC: Voucher decrypted but key/iv normalization failed. raw_key={raw_key!r}, raw_iv={raw_iv!r}")
        except Exception as e:
            print(f"AAXC voucher decryption note: {e}")

        return None

    @staticmethod
    def get_or_fetch_activation_bytes(db: Session, client: Any) -> Optional[str]:
        """Gets stored activation bytes or automatically fetches them from Audible API using client.auth."""
        conf = StorageService.get_configured_settings(db)
        act_bytes = conf.get("activation_bytes")
        if act_bytes:
            return act_bytes

        try:
            from audible.activation_bytes import get_activation_bytes
            auth = getattr(client, "auth", None)
            if auth:
                fetched_bytes = get_activation_bytes(auth)
                if fetched_bytes:
                    act_str = str(fetched_bytes).strip()
                    from app.models import Setting
                    setting_bytes = db.query(Setting).filter(Setting.key == "activation_bytes").first()
                    if not setting_bytes:
                        setting_bytes = Setting(key="activation_bytes", value=act_str)
                        db.add(setting_bytes)
                    else:
                        setting_bytes.value = act_str
                    db.commit()
                    return act_str
        except Exception as e:
            print(f"Auto-fetch activation_bytes note: {e}")

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
                                calc_progress = min(98, max(1, int((bytes_downloaded / total_bytes) * 98)))
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

            # Keep status as 'downloading' with progress 99% during conversion phase
            book.download_progress = 99
            db.commit()

            ffmpeg_bin = StorageService.find_ffmpeg()
            final_saved_path = aax_file_path
            aaxc_creds = None
            conversion_success = False

            if not activation_bytes and client:
                activation_bytes = cls.get_or_fetch_activation_bytes(db, client)

            if ffmpeg_bin and os.path.exists(aax_file_path) and os.path.getsize(aax_file_path) > 0:
                aaxc_creds = cls.extract_aaxc_credentials(client, license_info)
                m4b_tmp_path = m4b_file_path + ".tmp"
                try:
                    if aaxc_creds and aaxc_creds.get("key") and aaxc_creds.get("iv"):
                        cmd = [
                            ffmpeg_bin, "-y",
                            "-audible_key", str(aaxc_creds["key"]),
                            "-audible_iv",  str(aaxc_creds["iv"]),
                            "-i", aax_file_path,
                            "-c", "copy",
                            "-f", "mp4",
                            m4b_tmp_path
                        ]
                    elif activation_bytes:
                        cmd = [
                            ffmpeg_bin, "-y",
                            "-activation_bytes", str(activation_bytes).strip(),
                            "-i", aax_file_path,
                            "-c", "copy",
                            "-f", "mp4",
                            m4b_tmp_path
                        ]
                    else:
                        cmd = None

                    if cmd:
                        proc = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await proc.communicate()
                        if proc.returncode == 0 and os.path.exists(m4b_tmp_path) and os.path.getsize(m4b_tmp_path) > 0:
                            if os.path.exists(m4b_file_path):
                                try: os.remove(m4b_file_path)
                                except Exception: pass
                            os.rename(m4b_tmp_path, m4b_file_path)
                            if os.path.exists(aax_file_path):
                                try: os.remove(aax_file_path)
                                except Exception: pass
                            final_saved_path = m4b_file_path
                            conversion_success = True
                        else:
                            err_msg = stderr.decode('utf-8', 'replace') if stderr else 'Unknown error'
                            print(f"FFmpeg conversion note (code {proc.returncode}): {err_msg}")
                            if os.path.exists(m4b_tmp_path):
                                try: os.remove(m4b_tmp_path)
                                except Exception: pass
                except Exception as ex:
                    print(f"FFmpeg conversion exception: {ex}")
                    if os.path.exists(m4b_tmp_path):
                        try: os.remove(m4b_tmp_path)
                        except Exception: pass

            had_conversion_attempt = bool(
                ffmpeg_bin
                and os.path.exists(aax_file_path)
                and (aaxc_creds or activation_bytes)
            )

            # Determine final status:
            # - converted successfully → downloaded (m4b)
            # - no ffmpeg → downloaded (aax, can't convert)
            # - had credentials but conversion failed → needs_activation
            # - no credentials at all → needs_activation
            if conversion_success:
                final_status = "downloaded"
            elif not ffmpeg_bin:
                # Can't convert without ffmpeg, save .aax as is
                final_status = "downloaded"
            else:
                # ffmpeg available but conversion failed (bad key, wrong bytes, etc.)
                final_status = "needs_activation"

            # ONLY NOW (after download AND conversion are done) update status to completed!
            book.download_status = final_status
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
        """
        Background task: converts an already-downloaded .aax/.aaxc file to .m4b.
        Strategy:
          1. Re-fetch the license from Audible API to get AAXC key/iv (most books).
          2. If AAXC fails, fall back to activation_bytes (legacy AAX DRM).
        """
        db = db_factory()
        try:
            book = db.query(Book).filter(Book.asin == asin).first()
            if not book or not book.local_path or not os.path.exists(book.local_path):
                print(f"execute_aax_conversion: book not found or file missing for {asin}")
                return

            ffmpeg_bin = StorageService.find_ffmpeg()
            if not ffmpeg_bin:
                print("execute_aax_conversion: ffmpeg not found")
                return

            aax_path = book.local_path
            m4b_path = aax_path.rsplit(".", 1)[0] + ".m4b"
            m4b_tmp_path = m4b_path + ".tmp"

            book.download_status = "downloading"
            book.download_progress = 99
            db.commit()

            # --- Strategy 1: AAXC via fresh license (re-fetch key/iv from API) ---
            aaxc_creds = None
            try:
                user = db.query(User).filter(User.id == book.user_id).first()
                token_record = db.query(Token).filter(Token.user_id == user.id).first() if user else None
                if user and token_record and token_record.access_token:
                    client = AudibleAuthManager.get_client_from_encrypted_tokens(
                        token_record=token_record, marketplace=user.marketplace
                    )
                    license_info = AudibleAuthManager.get_download_license(client, asin)
                    aaxc_creds = cls.extract_aaxc_credentials(client, license_info)
            except Exception as e:
                print(f"execute_aax_conversion: Could not re-fetch AAXC license: {e}")

            cmd = None
            if aaxc_creds and aaxc_creds.get("key") and aaxc_creds.get("iv"):
                cmd = [
                    ffmpeg_bin, "-y",
                    "-audible_key", aaxc_creds["key"],
                    "-audible_iv",  aaxc_creds["iv"],
                    "-i", aax_path,
                    "-c", "copy",
                    "-f", "mp4",
                    m4b_tmp_path
                ]
                print(f"execute_aax_conversion: Using AAXC key/iv for {asin}")

            # --- Strategy 2: Activation bytes (legacy AAX DRM) ---
            if not cmd:
                conf = StorageService.get_configured_settings(db)
                activation_bytes = conf.get("activation_bytes", "")
                if not activation_bytes:
                    # Try auto-fetch
                    try:
                        user = db.query(User).filter(User.id == book.user_id).first()
                        token_record = db.query(Token).filter(Token.user_id == user.id).first() if user else None
                        if user and token_record and token_record.access_token:
                            client = AudibleAuthManager.get_client_from_encrypted_tokens(
                                token_record=token_record, marketplace=user.marketplace
                            )
                            activation_bytes = cls.get_or_fetch_activation_bytes(db, client) or ""
                    except Exception as e:
                        print(f"execute_aax_conversion: Could not fetch activation_bytes: {e}")

                if activation_bytes:
                    cmd = [
                        ffmpeg_bin, "-y",
                        "-activation_bytes", activation_bytes.strip(),
                        "-i", aax_path,
                        "-c", "copy",
                        "-f", "mp4",
                        m4b_tmp_path
                    ]
                    print(f"execute_aax_conversion: Using activation_bytes fallback for {asin}")

            if not cmd:
                print(f"execute_aax_conversion: No credentials available for {asin}")
                book.download_status = "needs_activation"
                book.download_progress = 100
                db.commit()
                return

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0 and os.path.exists(m4b_tmp_path) and os.path.getsize(m4b_tmp_path) > 0:
                if os.path.exists(m4b_path):
                    try: os.remove(m4b_path)
                    except Exception: pass
                os.rename(m4b_tmp_path, m4b_path)
                if os.path.exists(aax_path) and aax_path != m4b_path:
                    try: os.remove(aax_path)
                    except Exception: pass
                book.local_path = os.path.abspath(m4b_path)
                book.download_status = "downloaded"
                print(f"execute_aax_conversion: Conversion succeeded for {asin}")
            else:
                err_msg = stderr.decode("utf-8", "replace") if stderr else "Unknown error"
                print(f"execute_aax_conversion: FFmpeg failed (code {proc.returncode}): {err_msg[:500]}")
                if os.path.exists(m4b_tmp_path):
                    try: os.remove(m4b_tmp_path)
                    except Exception: pass
                book.download_status = "needs_activation"

            book.download_progress = 100
            db.commit()
        except Exception as e:
            print(f"Error in execute_aax_conversion: {e}")
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
