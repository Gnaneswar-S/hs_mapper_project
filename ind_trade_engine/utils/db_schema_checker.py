"""
db_schema_checker.py
════════════════════════════════════════════════════════════════════
Database schema validation at startup.
Ensures all required tables and RPC functions exist before app runs.
════════════════════════════════════════════════════════════════════
"""

import logging
from supabase import Client

logger = logging.getLogger("db_schema_checker")

# Required tables in profiles schema
REQUIRED_TABLES = [
    "profiles",           # User profiles and roles
    "trade_usage_logs",   # Rate limiting / audit trail
    "query_limits",       # Daily query counts per user
    "audit_logs",         # Security audit log
    "email_delivery",     # Email delivery tracking
    "api_responses_cache", # Cached API responses
    "draft_Forms",        # Form auto-save drafts
]

# Required RPC functions
REQUIRED_RPCS = [
    "consume_query",      # Atomic query consumption
    "get_query_status",   # Get remaining queries
    "check_user_exists",  # Pre-check before auth
]

def check_schema_exists(supabase: Client):
    """
    Check if database schema is properly initialized.
    Returns: {"status": "ok"} or {"status": "warning"/"error", "missing": [...]}
    """
    missing_tables = []
    missing_rpcs = []

    # Check tables
    for table in REQUIRED_TABLES:
        try:
            result = supabase.table(table).select("count", count="exact").execute()
            logger.debug(f"✓ Table '{table}' exists")
        except Exception as e:
            if "does not exist" in str(e).lower() or "404" in str(e):
                missing_tables.append(table)
                logger.warning(f"✗ Table '{table}' not found")
            else:
                logger.debug(f"Table check for '{table}': {e}")

    # Check RPC functions
    for rpc in REQUIRED_RPCS:
        try:
            # Just test if the RPC exists by calling it with dummy params
            # Most will fail with validation error if params are wrong,
            # but won't fail with "function not found" if it exists
            result = supabase.rpc(rpc, {"user_id": "test"}).execute()
            logger.debug(f"✓ RPC '{rpc}' exists")
        except Exception as e:
            if "does not exist" in str(e).lower() or "not found" in str(e).lower():
                missing_rpcs.append(rpc)
                logger.warning(f"✗ RPC '{rpc}' not found")
            else:
                # Other errors (like auth) are OK — means RPC exists
                logger.debug(f"RPC '{rpc}' exists (auth error is expected)")

    if missing_tables or missing_rpcs:
        msg = ""
        if missing_tables:
            msg += f"Missing tables: {', '.join(missing_tables)}. "
        if missing_rpcs:
            msg += f"Missing RPCs: {', '.join(missing_rpcs)}. "
        msg += "Run 'sql_schema_v3.sql' in Supabase SQL editor."

        return {
            "status": "warning",
            "missing_tables": missing_tables,
            "missing_rpcs": missing_rpcs,
            "message": msg,
        }

    logger.info("✅ Database schema validation passed")
    return {"status": "ok"}


def assert_schema_ready(supabase: Client):
    """
    Check schema and log warnings but don't block app startup.
    This allows app to start and fallback gracefully if schema is incomplete.
    """
    result = check_schema_exists(supabase)
    if result["status"] == "warning":
        logger.warning(f"⚠️  Database schema incomplete: {result['message']}")
        logger.warning("App will continue with degraded functionality until schema is deployed.")
    return result
