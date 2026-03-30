# input_sanitizer.py
# Input sanitization and validation for all user-supplied trade data.
# Called by trade_advisor.py before passing anything to the LLM.
#
# Functions:
#   sanitize_prompt_input(text, max_length)       — strip injection patterns, truncate
#   sanitize_product_name(product)                — clean product name
#   validate_country_code(country)                — basic country string check
#   validate_and_sanitize_trade_inputs(data)      — validate a dict of trade fields

import re
import logging

logger = logging.getLogger("input_sanitizer")

# Patterns that indicate prompt injection attempts
_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+instructions?",
    r"disregard\s+(previous|all)\s+",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"act\s+as\s+(a|an)\s+",
    r"pretend\s+(you\s+are|to\s+be)\s+",
    r"system\s*:\s*",
    r"<\s*system\s*>",
    r"\[INST\]",
    r"\[\[/INST\]\]",
    r"###\s*instruction",
]

_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)

# Valid trade direction values
_VALID_DIRECTIONS = {"Export", "Import", "Both", "Knowledge"}

# Max lengths for each field type
_MAX_PRODUCT_LEN  = 500
_MAX_COUNTRY_LEN  = 100
_MAX_PROMPT_LEN   = 5000


def sanitize_prompt_input(text: str, max_length: int = _MAX_PROMPT_LEN) -> str:
    """
    Remove prompt injection patterns and truncate to max_length.
    Returns cleaned string safe to include in LLM prompts.
    """
    if not text or not isinstance(text, str):
        return ""

    cleaned = text.strip()

    # Detect and warn on injection attempts
    if _INJECTION_RE.search(cleaned):
        logger.warning("Potential prompt injection detected in user input — patterns removed")
        cleaned = _INJECTION_RE.sub("[REMOVED]", cleaned)

    # Remove null bytes and control characters (except newline/tab)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)

    # Truncate
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
        logger.debug(f"Input truncated to {max_length} chars")

    return cleaned


def sanitize_product_name(product: str) -> str:
    """
    Clean a product name for use in trade queries.
    Strips injection patterns, removes excessive special chars, truncates.
    """
    if not product or not isinstance(product, str):
        return ""

    cleaned = sanitize_prompt_input(product, max_length=_MAX_PRODUCT_LEN)

    # Allow alphanumeric, spaces, hyphens, commas, dots, parentheses, %
    cleaned = re.sub(r"[^\w\s\-,.()/:%]", " ", cleaned)

    # Collapse multiple spaces
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    return cleaned


def validate_country_code(country: str) -> bool:
    """
    Basic validation for a country name/code string.
    Returns True if the string looks like a valid country reference.
    """
    if not country or not isinstance(country, str):
        return False

    stripped = country.strip()

    if len(stripped) < 2 or len(stripped) > _MAX_COUNTRY_LEN:
        return False

    # Country names should only contain letters, spaces, hyphens, commas, dots
    if not re.match(r"^[\w\s\-,.()']+$", stripped):
        return False

    return True


def validate_and_sanitize_trade_inputs(data: dict) -> dict:
    """
    Validate and sanitize a dict of trade input fields.

    Expected keys (all optional): product, origin, destination, direction, value_usd

    Returns:
      {
        "valid": True/False,
        "errors": ["error message 1", ...],
        "data":   {"product": "...", "origin": "...", ...}   # sanitized values
      }
    """
    errors = []
    sanitized = {}

    # Product
    product = data.get("product", "")
    if product:
        clean_product = sanitize_product_name(str(product))
        if len(clean_product) < 2:
            errors.append("Product description is too short (min 2 characters).")
        else:
            sanitized["product"] = clean_product
    else:
        sanitized["product"] = ""

    # Origin country
    origin = data.get("origin", "")
    if origin:
        if not validate_country_code(str(origin)):
            errors.append(f"Invalid origin country: '{origin}'")
        else:
            sanitized["origin"] = str(origin).strip()[:_MAX_COUNTRY_LEN]

    # Destination country
    destination = data.get("destination", "")
    if destination:
        if not validate_country_code(str(destination)):
            errors.append(f"Invalid destination country: '{destination}'")
        else:
            sanitized["destination"] = str(destination).strip()[:_MAX_COUNTRY_LEN]

    # Trade direction
    direction = data.get("direction", "Export")
    if direction and str(direction) not in _VALID_DIRECTIONS:
        errors.append(f"Invalid direction '{direction}'. Must be one of: {', '.join(_VALID_DIRECTIONS)}")
    else:
        sanitized["direction"] = str(direction) if direction else "Export"

    # Shipment value
    value_usd = data.get("value_usd", "")
    if value_usd:
        # Strip currency symbols and commas, keep digits and decimal
        cleaned_val = re.sub(r"[^\d.,]", "", str(value_usd)).replace(",", "")
        try:
            float(cleaned_val)
            sanitized["value_usd"] = cleaned_val
        except ValueError:
            errors.append(f"Invalid shipment value: '{value_usd}'. Expected a number.")

    # Any remaining keys — sanitize as plain strings
    for key in data:
        if key not in sanitized and key not in ("product", "origin", "destination", "direction", "value_usd"):
            sanitized[key] = sanitize_prompt_input(str(data[key]), max_length=200)

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "data": sanitized,
    }