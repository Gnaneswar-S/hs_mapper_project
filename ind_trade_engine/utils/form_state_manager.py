# form_state_manager.py
# Auto-save and restore form input state across Streamlit reruns.
# Prevents users losing their typed data when the page refreshes.
#
# Usage:
#   form_state_manager.save("trade_analysis", {"product": product, "mode": mode})
#   saved = form_state_manager.load("trade_analysis")

import streamlit as st
import logging

logger = logging.getLogger("form_state_manager")

_PREFIX = "_form_state_"


def save(form_id: str, data: dict) -> None:
    """Persist form data to Streamlit session state."""
    if not form_id or not isinstance(data, dict):
        return
    st.session_state[f"{_PREFIX}{form_id}"] = {
        k: v for k, v in data.items() if v is not None
    }


def load(form_id: str, default: dict = None) -> dict:
    """Retrieve saved form data from session state."""
    key = f"{_PREFIX}{form_id}"
    return st.session_state.get(key, default or {})


def clear(form_id: str) -> None:
    """Remove saved form data for a specific form."""
    key = f"{_PREFIX}{form_id}"
    st.session_state.pop(key, None)


def clear_all() -> None:
    """Remove all saved form states (call on logout)."""
    keys = [k for k in st.session_state if k.startswith(_PREFIX)]
    for k in keys:
        del st.session_state[k]


def get(form_id: str, field: str, default=None):
    """Get a single field from saved form state."""
    return load(form_id).get(field, default)