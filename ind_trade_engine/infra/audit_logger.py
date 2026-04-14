# audit_logger.py
# Security audit trail. Logs auth events, data access, and admin actions
# to the Supabase audit_logs table.
#
# Required Supabase table:
#   CREATE TABLE audit_logs (
#       id          BIGSERIAL PRIMARY KEY,
#       user_id     UUID,
#       email       TEXT,
#       event_type  TEXT NOT NULL,
#       details     JSONB DEFAULT '{}',
#       ip_address  TEXT,
#       created_at  TIMESTAMPTZ DEFAULT NOW()
#   );
#   CREATE INDEX ON audit_logs (user_id);
#   CREATE INDEX ON audit_logs (event_type);
#   CREATE INDEX ON audit_logs (created_at);

import logging
from datetime import datetime, timezone

logger = logging.getLogger("audit_logger")

# Event type constants
AUTH_LOGIN          = "AUTH_LOGIN"
AUTH_LOGOUT         = "AUTH_LOGOUT"
AUTH_REGISTER       = "AUTH_REGISTER"
AUTH_FAILED         = "AUTH_FAILED"
AUTH_CONFIRMED      = "AUTH_EMAIL_CONFIRMED"
PASSWORD_RESET      = "PASSWORD_RESET"
ROLE_CHANGED        = "ROLE_CHANGED"
QUERY_LIMIT_HIT     = "QUERY_LIMIT_HIT"
ADMIN_ACTION        = "ADMIN_ACTION"
DATA_EXPORT         = "DATA_EXPORT"


def log_event(
    event_type: str,
    user_id: str = None,
    email: str = None,
    details: dict = None,
    ip_address: str = None,
) -> None:
    """
    Write a security event to Supabase audit_logs.
    Fails silently — never blocks the main application flow.
    """
    try:
        from supabase_service import supabase
        supabase.table("audit_logs").insert({
            "user_id":    user_id,
            "email":      (email or "")[:254],
            "event_type": event_type[:50],
            "details":    details or {},
            "ip_address": ip_address,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
        logger.debug(f"Audit: {event_type} — {email or user_id}")
    except Exception as e:
        logger.warning(f"audit_logger failed (non-fatal): {type(e).__name__}")


def log_auth_event(event_type: str, user_id: str, email: str, details: dict = None) -> None:
    log_event(event_type, user_id=user_id, email=email, details=details)


def log_admin_action(admin_email: str, action: str, target_user_id: str = None, details: dict = None) -> None:
    log_event(ADMIN_ACTION, email=admin_email,
              details={"action": action, "target_user_id": target_user_id, **(details or {})})


def log_role_change(admin_email: str, target_user_id: str, old_role: str, new_role: str) -> None:
    log_event(ROLE_CHANGED, email=admin_email,
              details={"target_user_id": target_user_id, "old_role": old_role, "new_role": new_role})