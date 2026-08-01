import json
import urllib.parse
import os
import time
from datetime import datetime, timezone
import httpx
import audible
import audible.register
from typing import Dict, Any, List, Optional

from app.security import encrypt_data, decrypt_data


# Safe monkey-patch for python-audible Authenticator.access_token_expired
# Prevents any 'No expires timestamp found' exception across the entire application
def _safe_access_token_expired(self) -> bool:
    expires_val = getattr(self, "_expires", None) or getattr(self, "expires", None)
    if expires_val is None:
        new_expires = time.time() + (86400 * 365)
        self.expires = new_expires
        return False
    try:
        return datetime.fromtimestamp(expires_val, timezone.utc) <= datetime.now(timezone.utc)
    except Exception:
        new_expires = time.time() + (86400 * 365)
        self.expires = new_expires
        return False

audible.auth.Authenticator.access_token_expired = property(_safe_access_token_expired)


class AudibleAuthManager:
    """Manages Audible API client authentication, PKCE registration, and API requests."""

    @staticmethod
    def extract_code_from_redirect_url(url_str: str) -> str:
        """Extract authorization code from full redirected URL or return string directly if already a code."""
        url_str = url_str.strip()
        if "openid.oa2.authorization_code=" in url_str or "?" in url_str:
            parsed = urllib.parse.urlparse(url_str)
            qs = urllib.parse.parse_qs(parsed.query)
            if "openid.oa2.authorization_code" in qs:
                return qs["openid.oa2.authorization_code"][0]
        return url_str

    @staticmethod
    def register_device_and_get_tokens(
        authorization_code: str,
        code_verifier: bytes,
        domain: str,
        serial: str
    ) -> Dict[str, Any]:
        """Exchanges authorization_code + code_verifier for device tokens with Amazon/Audible."""
        reg_result = audible.register.register(
            authorization_code=authorization_code,
            code_verifier=code_verifier,
            domain=domain,
            serial=serial
        )

        raw_cust_info = reg_result.get("customer_info", {})
        raw_dev_info = reg_result.get("device_info", {})

        return {
            "access_token": encrypt_data(reg_result.get("access_token", "")),
            "refresh_token": encrypt_data(reg_result.get("refresh_token", "")),
            "adp_token": encrypt_data(reg_result.get("adp_token", "")),
            "device_private_key": encrypt_data(reg_result.get("device_private_key", "")),
            "website_cookies": encrypt_data(json.dumps(reg_result.get("website_cookies", {}))),
            "device_info": encrypt_data(json.dumps(raw_dev_info)),
            "customer_info": encrypt_data(json.dumps(raw_cust_info)),
            "raw_customer_info": raw_cust_info if isinstance(raw_cust_info, dict) else {},
            "raw_device_info": raw_dev_info if isinstance(raw_dev_info, dict) else {},
            "expires": reg_result.get("expires")
        }

    @staticmethod
    def get_client_from_encrypted_tokens(token_record, marketplace: str = "br") -> audible.Client:
        """Instantiates an active Audible Client using decrypted stored tokens."""
        expires_ts = None
        if token_record and token_record.expires_at:
            try:
                expires_ts = float(token_record.expires_at.timestamp())
            except Exception:
                pass

        if not expires_ts:
            expires_ts = float(time.time() + (86400 * 365))

        raw_dict: Dict[str, Any] = {
            "locale_code": marketplace,
            "expires": expires_ts
        }

        if token_record:
            acc_token = decrypt_data(token_record.access_token) if token_record.access_token else ""
            ref_token = decrypt_data(token_record.refresh_token) if token_record.refresh_token else ""
            adp_tok = decrypt_data(token_record.adp_token) if token_record.adp_token else ""
            priv_key = decrypt_data(token_record.device_private_key) if token_record.device_private_key else ""

            if acc_token:
                raw_dict["access_token"] = acc_token
            if ref_token:
                raw_dict["refresh_token"] = ref_token
            if adp_tok:
                raw_dict["adp_token"] = adp_tok
            if priv_key:
                raw_dict["device_private_key"] = priv_key

            cookies_str = decrypt_data(token_record.website_cookies) if token_record.website_cookies else ""
            if cookies_str:
                try:
                    cookies_json = json.loads(cookies_str)
                    if isinstance(cookies_json, dict) and cookies_json:
                        raw_dict["website_cookies"] = cookies_json
                except Exception:
                    pass

            dev_info_str = decrypt_data(token_record.device_info) if getattr(token_record, "device_info", None) else ""
            if dev_info_str:
                try:
                    raw_dict["device_info"] = json.loads(dev_info_str)
                except Exception:
                    pass

            cust_info_str = decrypt_data(token_record.customer_info) if getattr(token_record, "customer_info", None) else ""
            if cust_info_str:
                try:
                    raw_dict["customer_info"] = json.loads(cust_info_str)
                except Exception:
                    pass

        auth = audible.Authenticator.from_dict(raw_dict, locale=marketplace)
        auth.expires = expires_ts

        return audible.Client(auth=auth)

    @staticmethod
    def fetch_user_profile(client: audible.Client) -> Dict[str, Any]:
        """Fetch user profile information from Audible API."""
        try:
            res = client.get("1.0/customer/information", params={"response_groups": "user_id,given_name,email"})
            customer_info = res.get("customer_information", {})
            return {
                "user_id": customer_info.get("user_id", "audible_user"),
                "given_name": customer_info.get("given_name", "Usuário Audible"),
                "email": customer_info.get("email", ""),
                "marketplace": client.auth.locale.country_code if client.auth.locale else "br"
            }
        except Exception as e:
            return {
                "user_id": "audible_user",
                "given_name": "Usuário Audible",
                "email": "",
                "marketplace": "br",
                "note": f"Perfil carregado via token. API info: {str(e)}"
            }

    @staticmethod
    def fetch_full_library(client: audible.Client) -> List[Dict[str, Any]]:
        """Fetch full user library from Audible API and format book metadata."""
        try:
            res = client.get(
                "1.0/library",
                params={
                    "num_results": 100,
                    "response_groups": "product_desc,contributors,media,product_attrs"
                }
            )
            items = res.get("items", [])
            formatted_books = []

            for item in items:
                asin = item.get("asin", "")
                if not asin:
                    continue

                title = item.get("title", "Título Desconhecido")
                subtitle = item.get("subtitle", "")

                # Authors
                authors_list = item.get("authors", [])
                authors = ", ".join([a.get("name", "") for a in authors_list if a.get("name")])

                # Narrators
                narrators_list = item.get("narrators", [])
                narrators = ", ".join([n.get("name", "") for n in narrators_list if n.get("name")])

                # Duration
                runtime_ms = item.get("runtime_length_min", 0) * 60 * 1000

                # Cover URL
                images = item.get("product_images", {})
                cover_url = images.get("500") or images.get("252") or images.get("121") or ""

                formatted_books.append({
                    "asin": asin,
                    "title": title,
                    "subtitle": subtitle,
                    "authors": authors or "Autor Desconhecido",
                    "narrators": narrators or "Narrador Desconhecido",
                    "duration_ms": runtime_ms,
                    "cover_url": cover_url,
                    "release_date": item.get("release_date", "")
                })

            return formatted_books

        except Exception as e:
            raise RuntimeError(f"Erro ao consultar API da Audible Brasil: {str(e)}")

    @staticmethod
    def get_download_license(client: audible.Client, asin: str) -> Dict[str, Any]:
        """Requests official download license and signed CloudFront URL from Audible API."""
        try:
            res = client.post(
                f"1.0/content/{asin}/licenserequest",
                body={
                    "drm_type": "Adrm",
                    "consumption_type": "Download",
                    "quality": "High"
                }
            )
            content_license = res.get("content_license", {})
            content_metadata = content_license.get("content_metadata", {})
            content_url_data = content_metadata.get("content_url", {})
            offline_url = content_url_data.get("offline_url", "")

            if not offline_url:
                raise ValueError("Licença obtida, mas a URL de download (CloudFront) veio vazia.")

            return {
                "asin": asin,
                "offline_url": offline_url,
                "license_response": content_license.get("license_response", ""),
                "raw_response": res,
                "license_id": content_license.get("license_id", ""),
                "acr": content_license.get("acr", "")
            }
        except Exception as e:
            raise RuntimeError(f"Erro ao solicitar licença de download para {asin}: {str(e)}")
