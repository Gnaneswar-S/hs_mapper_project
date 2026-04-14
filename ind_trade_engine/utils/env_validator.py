"""
env_validator.py
Validates required environment variables at startup.
Fails fast on missing critical vars; warns on optional ones.
"""

import os
import logging

logger = logging.getLogger(__name__)

# ── Required vars — app will NOT start without these ────────────────
REQUIRED_VARS = [
    ("NVIDIA_API_KEY",       "NVIDIA NIM API key for Llama 3.3 70B"),
    ("SUPABASE_URL",         "Supabase project URL"),
    ("SUPABASE_SERVICE_KEY", "Supabase service role key (DB operations)"),
    ("SUPABASE_ANON_KEY",    "Supabase anon key (auth operations)"),
]

# ── Optional vars — app works without these but warns ───────────────
OPTIONAL_VARS = [
    ("SMTP_HOST",   "Email SMTP host (default: smtp.gmail.com)"),
    ("SMTP_PORT",   "Email SMTP port (default: 587)"),
    ("SMTP_USER",   "Email SMTP username"),
    ("SMTP_PASS",   "Email SMTP password (app password)"),   # ← SMTP_PASS not SMTP_PASSWORD
    ("SMTP_FROM",   "Sender email address"),
    ("ADMIN_EMAIL", "Admin notification email"),
    ("APP_URL",     "Deployed app URL for email links"),
]


def validate_environment() -> dict:
    """
    Check all env vars. Returns:
      {"status": "ok"}  — all required vars present
      {"status": "warning", "warnings": [...]}  — required ok, optional missing
      {"status": "error", "missing": [...]}  — required vars absent
    """
    # Load .env file if present (development mode)
    _load_dotenv()

    missing_required = []
    missing_optional = []

    for var, description in REQUIRED_VARS:
        if not os.environ.get(var, "").strip():
            missing_required.append(f"• {var}: {description}")

    for var, description in OPTIONAL_VARS:
        if not os.environ.get(var, "").strip():
            missing_optional.append(f"• {var}: {description}")

    if missing_required:
        logger.error(f"Missing required env vars: {[v for v, _ in REQUIRED_VARS if not os.environ.get(v)]}")
        return {
            "status":  "error",
            "missing": missing_required,
        }

    warnings = []
    if missing_optional:
        # Only warn if SMTP vars are missing — email features won't work
        smtp_missing = [m for m in missing_optional if "SMTP" in m]
        if smtp_missing:
            warnings.append(
                "⚠️ Some SMTP variables are not set — email confirmations and OTP will not work. "
                "Add SMTP_HOST, SMTP_USER, SMTP_PASS, SMTP_FROM to your .env file."
            )

    return {
        "status":   "warning" if warnings else "ok",
        "warnings": warnings,
    }


def assert_environment_ready() -> None:
    """
    Hard-fail version used in CI / startup scripts.
    Raises SystemExit if required vars are missing.
    """
    result = validate_environment()
    if result["status"] == "error":
        for item in result["missing"]:
            print(f"MISSING ENV VAR: {item}")
        raise SystemExit(
            "Application cannot start: required environment variables are missing. "
            "Copy .env.example to .env and fill in the values."
        )


def _load_dotenv() -> None:
    """
    Minimal .env loader — no dependency on python-dotenv.
    Reads KEY=VALUE lines, skips comments and blanks.
    Does NOT overwrite vars already set in the environment.
    """
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key   = key.strip()
                value = value.strip().strip('"').strip("'")
                # Never overwrite a var that's already set (e.g. from CI/cloud)
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as e:
        logger.warning(f"Could not load .env file: {e}")