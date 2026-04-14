# trade_advisor.py
# High-level trade advisory wrappers used by app.py.
# All functions are stateless — no DB calls, no session state.
# DB logging and rate-limit consumption happen in app.py after each call.

import logging
from utils.input_sanitizer import (
    sanitize_prompt_input,
    sanitize_product_name,
    validate_country_code,
    validate_and_sanitize_trade_inputs,
)

logger = logging.getLogger("trade_advisor")

from services.nvidia_service import (
    _call_llama,
    chat_with_tradegpt as _chat,
    analyze_trade_risk as _risk,
    get_price_intelligence as _price,
    analyze_trade_document as _doc,
    check_trade_compliance as _compliance,
    get_competitor_intelligence as _competitor,
    generate_smart_trade_ideas as _ideas,
    find_global_suppliers as _suppliers,
    generate_ai_trade_report as _report,
)


def chat_with_tradegpt(user_message: str, history: list, context: dict = None) -> dict:
    """
    Multi-turn trade Q&A.
    history: list of {"role": "user"|"assistant", "content": "..."}
    Returns: {"reply": "...", "follow_up_questions": [...], "relevant_links": [...]}
    """
    safe_message = sanitize_prompt_input(user_message, max_length=2000)
    if safe_message != user_message:
        logger.warning("User message sanitized before LLM call")
    return _chat(history, safe_message)


def analyze_trade_risk(
    product: str,
    origin_country: str,
    supplying_country: str,
    buyer_countries: str,
    direction: str = "Export",
    value_usd: str = "50,000",
) -> dict:
    """6-dimension risk score with geopolitical context."""
    validation = validate_and_sanitize_trade_inputs({
        "product":     product,
        "origin":      origin_country,
        "destination": buyer_countries,
        "direction":   direction,
    })
    if not validation["valid"]:
        logger.warning(f"Trade risk input validation errors: {validation['errors']}")
    safe = validation["data"]
    return _risk(
        safe.get("product", product),
        safe.get("origin", origin_country),
        supplying_country,
        safe.get("destination", buyer_countries),
        safe.get("direction", direction),
        value_usd,
    )


def get_price_intelligence(product: str, quantity: str, market: str) -> dict:
    """Global price benchmarking."""
    return _price(sanitize_product_name(product), quantity, market)


def analyze_trade_document(document_text: str, doc_type: str = "auto") -> dict:
    """Extract and validate fields from a trade document."""
    safe_text = sanitize_prompt_input(document_text, max_length=5000)
    if doc_type and doc_type != "auto":
        enriched = f"Document Type (if known): {doc_type}\n\n{safe_text}"
    else:
        enriched = safe_text
    return _doc(enriched)


def check_trade_compliance(
    product: str,
    hs_code: str,
    origin: str,
    destination: str,
    direction: str = "Export",
) -> dict:
    """SCOMET, DGFT, UN sanctions, and documentation check."""
    return _compliance(product, origin, destination, 50000.0)


def get_competitor_intelligence(product: str, market: str) -> dict:
    """Market share, competitor pricing, India's strengths/weaknesses."""
    return _competitor(product, market)


def generate_smart_trade_ideas(profile: str, budget: str, direction: str, industry: str) -> dict:
    """5 tailored import/export business opportunities (2 LLM calls)."""
    return _ideas(profile, budget, direction, industry)


def find_global_suppliers(product: str, quantity: str, quality: str, origin: str) -> dict:
    """Top 3 global supply origins with pricing, duties, and FTA savings."""
    return _suppliers(product, quantity, quality, origin)


def generate_ai_trade_report(product: str, direction: str, countries: list) -> dict:
    """Full trade feasibility report with 90-day action plan."""
    return _report(product, direction, countries)