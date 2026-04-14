"""
idempotency_manager.py
Prevents duplicate AI calls when a user double-clicks a submit button.
Uses Streamlit session_state to track in-flight request keys.

Usage (via alias _idem in app.py):
    key = _idem.make_key("register", email)
    if _idem.is_duplicate(key):
        st.warning("Request already in progress...")
    else:
        _idem.mark_in_flight(key)
        try:
            result = call_ai(...)
        finally:
            _idem.clear(key)
"""

import hashlib
import time
import logging

logger = logging.getLogger("idempotency_manager")

_PREFIX  = "_idem_"
_TTL_SEC = 30   # auto-expire after 30 s even if clear() was never called


def _ss() -> dict:
    """Safe accessor for st.session_state."""
    try:
        import streamlit as st
        return st.session_state
    except Exception:
        return {}


def make_key(*parts) -> str:
    """Create a stable short hash key from request parameters.

    Examples:
        make_key("register", email)  ->  "a3f8c1d2e9b0"
        make_key("trade_analysis", product, mode)
    """
    combined = "|".join(str(p) for p in parts)
    return hashlib.md5(combined.encode("utf-8")).hexdigest()[:12]


def is_duplicate(key: str) -> bool:
    """Return True if this exact request is already in-flight."""
    ss = _ss()
    entry = ss.get(f"{_PREFIX}{key}")
    if not entry:
        return False
    try:
        elapsed = time.monotonic() - entry.get("ts", 0)
        if elapsed > _TTL_SEC:
            clear(key)
            return False
    except Exception:
        clear(key)
        return False
    return True


def mark_in_flight(key: str) -> None:
    """Mark a request as in-flight. Call BEFORE the AI/DB operation."""
    ss = _ss()
    try:
        ss[f"{_PREFIX}{key}"] = {"ts": time.monotonic()}
    except Exception:
        pass


def clear(key: str) -> None:
    """Mark request as complete. Always call in a finally block."""
    ss = _ss()
    try:
        ss.pop(f"{_PREFIX}{key}", None)
    except Exception:
        pass


def clear_all() -> None:
    """Clear all idempotency locks (useful on logout)."""
    ss = _ss()
    try:
        keys = [k for k in list(ss.keys()) if k.startswith(_PREFIX)]
        for k in keys:
            try:
                del ss[k]
            except Exception:
                pass
    except Exception:
        pass