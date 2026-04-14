# auth_token_manager.py
# Access token validation and session helpers.
# Wraps Supabase token operations so the rest of the app doesn't
# depend directly on supabase-py internals.

import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger("auth_token_manager")


def is_token_expired(access_token: str) -> bool:
    """
    Decode the JWT payload and check if exp has passed.
    Returns True if expired or if token cannot be decoded.
    Does NOT verify signature — that is Supabase's job.
    """
    if not access_token:
        return True
    try:
        import base64, json
        parts  = access_token.split(".")
        if len(parts) < 2:
            return True
        pad    = parts[1] + "=" * (4 - len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(pad).decode("utf-8"))
        exp    = claims.get("exp", 0)
        return datetime.now(timezone.utc).timestamp() > exp
    except Exception as e:
        logger.warning(f"Token decode failed: {type(e).__name__}")
        return True


def get_token_email(access_token: str) -> str | None:
    """Extract email claim from JWT payload without signature verification."""
    if not access_token:
        return None
    try:
        import base64, json
        parts  = access_token.split(".")
        pad    = parts[1] + "=" * (4 - len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(pad).decode("utf-8"))
        return claims.get("email") or claims.get("sub")
    except Exception:
        return None


def refresh_session(refresh_token: str) -> dict:
    """
    Attempt to refresh an expired session using the refresh token.
    Returns {"status": "success", "access_token": "...", "refresh_token": "..."}
    or {"status": "error", "message": "..."}
    """
    if not refresh_token:
        return {"status": "error", "message": "No refresh token provided."}
    try:
        from supabase_service import supabase_auth
        resp = supabase_auth.auth.refresh_session(refresh_token)
        if resp and resp.session:
            return {
                "status":        "success",
                "access_token":  resp.session.access_token,
                "refresh_token": resp.session.refresh_token or refresh_token,
            }
        return {"status": "error", "message": "Session refresh returned no session."}
    except Exception as e:
        logger.warning(f"Session refresh failed: {type(e).__name__}")
        return {"status": "error", "message": f"Session refresh failed: {type(e).__name__}"}


def validate_session(user: dict) -> bool:
    """
    Check whether the user's current session token is still valid.
    Returns True if valid, False if expired or missing.
    """
    if not user:
        return False
    token = user.get("access_token", "")
    if not token:
        return False
    return not is_token_expired(token)