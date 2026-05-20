"""FastAPI dependencies for auth + admin checks.

We delegate JWT verification to Supabase itself via `supabase.auth.get_user(token)`.
This is more robust than verifying signatures locally — it works regardless of
whether Supabase uses the legacy HS256 shared secret or the newer asymmetric
(ES256/RS256) JWT signing keys.
"""
import logging
from fastapi import HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import settings
from services.supabase_client import supabase

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    """Verify the user's JWT by calling Supabase's /auth/v1/user endpoint.

    We don't decode the JWT locally because Supabase now signs with asymmetric
    keys (ES256) — verifying remotely is simpler and stays correct across
    Supabase's key rotations.
    """
    if not creds or not creds.credentials:
        raise HTTPException(401, "Missing authorization token")

    import httpx
    try:
        res = httpx.get(
            f"{settings.SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {creds.credentials}",
                "apikey": settings.SUPABASE_ANON_KEY,
            },
            timeout=10,
        )
    except Exception as e:
        logger.warning("Supabase /auth/v1/user request failed: %s", e)
        raise HTTPException(401, "Auth verify failed")

    if res.status_code != 200:
        raise HTTPException(401, "Invalid token")

    user = res.json()
    if not user.get("id"):
        raise HTTPException(401, "Invalid token")

    return {
        "sub":   user["id"],
        "email": user.get("email"),
        "role":  user.get("role"),
    }


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Portal super-admin = pattanachok (config). Only this email can approve/reject."""
    email = (user.get("email") or "").lower()
    if email != settings.ADMIN_EMAIL.lower():
        raise HTTPException(403, "Admin access required")
    return user
