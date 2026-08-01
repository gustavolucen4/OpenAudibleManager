import uuid
import audible
import audible.login
import audible.localization
from typing import Dict, Any, Tuple, Optional

# In-memory store for pending PKCE authorization sessions
PENDING_SESSIONS: Dict[str, Dict[str, Any]] = {}


def create_auth_session(marketplace: str = "br") -> Tuple[str, str, Dict[str, Any]]:
    """
    Generates an official Amazon/Audible device authorization URL for the specified marketplace
    along with PKCE verifier and device serial.
    
    Returns:
        (session_id, auth_url, session_info)
    """
    mp = marketplace.lower()
    try:
        loc = audible.localization.Locale(mp)
    except Exception:
        loc = audible.localization.Locale("br")

    code_verifier = audible.login.create_code_verifier()
    auth_url, serial = audible.login.build_oauth_url(
        country_code=loc.country_code,
        domain=loc.domain,
        market_place_id=loc.market_place_id,
        code_verifier=code_verifier
    )

    session_id = str(uuid.uuid4())
    session_info = {
        "session_id": session_id,
        "marketplace": mp,
        "country_code": loc.country_code,
        "domain": loc.domain,
        "market_place_id": loc.market_place_id,
        "code_verifier": code_verifier,
        "serial": serial,
        "auth_url": auth_url
    }
    
    PENDING_SESSIONS[session_id] = session_info
    return session_id, auth_url, session_info


def get_latest_pending_session(marketplace: str = "br") -> Optional[Dict[str, Any]]:
    """Retrieve the most recent pending session if session_id is not specified."""
    if not PENDING_SESSIONS:
        return None
    # Return the last added session
    return list(PENDING_SESSIONS.values())[-1]
