"""
nvidia_service.py
Indian Trade Intelligence Engine — Llama 3.3 70B via NVIDIA API
────────────────────────────────────────────────────────────────
v3.3 changes:
  - All prompts now extract Indian STATE from product description
    and give state-specific duty rates, clusters, schemes, ports
  - Results include plain English summaries (not just JSON fields)
  - Document analyzer: improved field extraction from any document
  - Price intelligence: returns both numeric fields AND English summary
  - World context: competitor analysis covers global landscape
────────────────────────────────────────────────────────────────
"""

import os, re, json, time, hashlib, logging, requests

logger = logging.getLogger("nvidia_service")

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import streamlit as st
    API_KEY = st.secrets.get("NVIDIA_API_KEY", "") or os.getenv("NVIDIA_API_KEY", "").strip()
except Exception:
    API_KEY = os.getenv("NVIDIA_API_KEY", "").strip()

if not API_KEY:
    raise ValueError("NVIDIA_API_KEY not found in Streamlit secrets or .env")

API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
MODEL   = "meta/llama-3.3-70b-instruct"

_RESPONSE_CACHE: dict = {}
_CACHE_MAX_SIZE = 200

def _cache_key(p): return hashlib.sha256(p.encode()).hexdigest()[:16]
def _cache_get(p): return _RESPONSE_CACHE.get(_cache_key(p))
def _cache_set(p, r):
    if len(_RESPONSE_CACHE) >= _CACHE_MAX_SIZE:
        del _RESPONSE_CACHE[next(iter(_RESPONSE_CACHE))]
    _RESPONSE_CACHE[_cache_key(p)] = r
def clear_response_cache(): _RESPONSE_CACHE.clear()


# ── Indian state → trade details ─────────────────────────────────
# Used to inject state-specific context into every prompt
INDIA_STATES = {
    "gujarat":      {"cluster":"Surat textiles, Ahmedabad pharma, Rajkot engineering, Morbi ceramics",  "main_port":"Mundra / Kandla", "key_schemes":"GIFT City, NSEZ Kandla, Surat Textile Park"},
    "maharashtra":  {"cluster":"Mumbai finance, Pune auto, Nashik grapes/wine, Aurangabad manufacturing","main_port":"JNPT Mumbai",     "key_schemes":"SEEPZ Mumbai, Maharashtra Industrial Dev Corp"},
    "tamil_nadu":   {"cluster":"Coimbatore textiles/pumps, Chennai auto, Tirupur garments",              "main_port":"Chennai / Ennore","key_schemes":"Madras Export Processing Zone, Tirupur cluster"},
    "karnataka":    {"cluster":"Bengaluru IT/electronics, Hubli agri, Mysuru silk",                      "main_port":"New Mangalore",   "key_schemes":"KIADB, Bengaluru Tech exports"},
    "andhra_pradesh":{"cluster":"Visakhapatnam pharma, Krishna spices, East Godavari aquaculture",       "main_port":"Visakhapatnam",   "key_schemes":"APIIC SEZ, Kakinada Port SEZ"},
    "telangana":    {"cluster":"Hyderabad pharma/biotech, IT exports, Nizamabad turmeric",               "main_port":"Hyderabad ICD",   "key_schemes":"Hyderabad Pharma City, TSIIC"},
    "west_bengal":  {"cluster":"Kolkata jute/leather, Darjeeling tea, Siliguri border trade",            "main_port":"Kolkata / Haldia","key_schemes":"Falta SEZ, Kolkata ICD"},
    "kerala":       {"cluster":"Kochi spices/seafood, Calicut timber, Thiruvananthapuram IT",            "main_port":"Cochin",          "key_schemes":"Cochin SEZ, KINFRA parks"},
    "rajasthan":    {"cluster":"Jaipur gems/jewellery, Jodhpur handicrafts, Bhilwara textiles",          "main_port":"Delhi ICD / Mundra via rail","key_schemes":"Jaipur Gems Cluster, Bhilwara Textile Park"},
    "uttar_pradesh":{"cluster":"Agra leather/footwear, Varanasi silk, Moradabad brassware, Noida electronics","main_port":"Delhi ICD / Kanpur ICD","key_schemes":"UP Exports Promotion, Noida SEZ"},
    "punjab":       {"cluster":"Ludhiana hosiery/cycles, Jalandhar sports goods, Amritsar food processing","main_port":"Delhi ICD",    "key_schemes":"Punjab Industrial Policy, Apparel Park Ludhiana"},
    "haryana":      {"cluster":"Gurugram auto parts, Panipat textiles, Faridabad engineering",           "main_port":"Delhi ICD",       "key_schemes":"IMT Manesar, Haryana Industrial Policy"},
    "madhya_pradesh":{"cluster":"Bhopal pharma, Indore food processing, Sagar diamonds",                "main_port":"Mundra via rail / Delhi ICD","key_schemes":"MPIDC, Pithampur Industrial Area"},
    "odisha":       {"cluster":"Bhubaneswar IT, Kalahandi tribal crafts, Berhampur silk",                "main_port":"Paradip / Visakhapatnam","key_schemes":"Paradeep SEZ, Odisha Industrial Policy"},
    "assam":        {"cluster":"Assam/Dibrugarh tea, Guwahati silk/bamboo, NE border trade",             "main_port":"Kolkata / Guwahati ICD","key_schemes":"NE Industrial Policy, AEZ Guwahati"},
}

def _detect_state(text: str) -> dict | None:
    """Extract Indian state from product description or return None."""
    text_lower = text.lower()
    state_aliases = {
        "gujarat": ["gujarat","surat","ahmedabad","rajkot","vadodara","morbi"],
        "maharashtra": ["maharashtra","mumbai","pune","nashik","aurangabad","nagpur"],
        "tamil_nadu": ["tamil","coimbatore","chennai","tirupur","madurai","salem"],
        "karnataka": ["karnataka","bangalore","bengaluru","mysore","hubli"],
        "andhra_pradesh": ["andhra","vizag","visakhapatnam","vijayawada","guntur","krishna","kakinada"],
        "telangana": ["telangana","hyderabad","nizamabad","warangal"],
        "west_bengal": ["bengal","kolkata","calcutta","darjeeling","siliguri"],
        "kerala": ["kerala","kochi","calicut","kozhikode","trivandrum"],
        "rajasthan": ["rajasthan","jaipur","jodhpur","udaipur","bhilwara"],
        "uttar_pradesh": ["uttar pradesh","up","agra","varanasi","noida","lucknow","kanpur","moradabad"],
        "punjab": ["punjab","ludhiana","amritsar","jalandhar"],
        "haryana": ["haryana","gurugram","faridabad","panipat"],
        "madhya_pradesh": ["madhya pradesh","mp","bhopal","indore","jabalpur"],
        "odisha": ["odisha","bhubaneswar","cuttack","paradip"],
        "assam": ["assam","guwahati","dibrugarh","jorhat"],
    }
    for state_key, aliases in state_aliases.items():
        if any(alias in text_lower for alias in aliases):
            return {"state": state_key, **INDIA_STATES.get(state_key, {})}
    return None


SYSTEM_PROMPT = (
    "You are a precise Indian trade compliance expert with deep knowledge of "
    "Indian state-wise industry clusters, ports, and schemes. "
    "Return ONLY valid JSON — no markdown fences, no explanation, no preamble. "
    "Start with '{' end with '}'. "
    "Always include a 'plain_summary' field with 2-3 sentences in simple English "
    "explaining the key takeaway for a non-expert trader."
)


# ════════════════════════════════════════════════════════════════════
# CORE LLM CALL
# ════════════════════════════════════════════════════════════════════

def _call_llama(prompt, max_tokens=2000, temperature=0.2, retries=3, use_cache=True):
    if use_cache:
        cached = _cache_get(prompt)
        if cached: return cached
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL,
        "messages": [
            {"role":"system","content": SYSTEM_PROMPT},
            {"role":"user",  "content": prompt},
        ],
        "max_tokens": max_tokens, "temperature": temperature, "top_p": 0.95, "stream": False,
    }
    raw = ""
    for attempt in range(retries):
        try:
            r = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"].strip()
            clean = re.sub(r"^```(?:json)?\s*","",raw,flags=re.IGNORECASE)
            clean = re.sub(r"\s*```$","",clean).strip()
            s = clean.find("{"); e = clean.rfind("}")
            if s != -1 and e != -1: clean = clean[s:e+1]
            result = json.loads(clean)
            if use_cache: _cache_set(prompt, result)
            return result
        except json.JSONDecodeError:
            if attempt == retries-1:
                return {"error":"AI returned invalid JSON — please retry","raw":raw[:300]}
        except requests.exceptions.Timeout:
            if attempt == retries-1: return {"error":"Request timed out (120s). Try again."}
        except requests.exceptions.HTTPError as ex:
            sc = getattr(ex.response,"status_code",0)
            if sc == 429: time.sleep(2**(attempt+1))
            elif sc == 401: return {"error":"Invalid NVIDIA_API_KEY"}
            else:
                if attempt == retries-1: return {"error":f"API HTTP {sc}"}
        except Exception as ex:
            if attempt == retries-1: return {"error":str(ex)}
        time.sleep(1.5*(attempt+1))
    return {"error":"All retries failed"}


# ════════════════════════════════════════════════════════════════════
# IMPORT / EXPORT / KNOWLEDGE — state-aware prompts
# ════════════════════════════════════════════════════════════════════

IMPORT_CONTEXT = """Indian Import Rules (2024):
- BCD: 0% pharma/APIs, 5% chemicals/capital goods, 10% electronics, 15-30% agriculture, 30-150% spices
- IGST: only 5%, 12%, 18%, or 28%
- SWS = 10% of BCD always
- Import Policy: Free / Restricted / Prohibited
- SCOMET: dual-use, defence, nuclear, OPCW chemicals"""

EXPORT_CONTEXT = """Indian Export Policy (2024 DGFT FTP):
- Default: Free for most goods
- RoDTEP: most manufactured goods (replaced MEIS 2021)
- RoSCTL: ONLY apparel and made-up textiles
- Export Duty: 0% most goods; exceptions: iron ore, rice, raw hides
- Prohibited: beef, some wildlife, antiquities, sand"""

KNOWLEDGE_CONTEXT = """Indian GST (2024):
- 0%: fresh food, milk, books, healthcare
- 5%: packed food, edible oils, coal, essential medicines
- 12%: processed food, computers, business medicines
- 18%: most manufactured goods, electronics, chemicals
- 28%: luxury cars, tobacco, aerated drinks, cement"""


def trade_intelligence_engine(product: str, mode: str) -> dict:
    if not product.strip():
        return {"error": "Product description cannot be empty"}
    if mode == "Import":   return _import_analysis(product)
    elif mode == "Export": return _export_analysis(product)
    else:                  return _knowledge_analysis(product)


def _state_context_block(product: str) -> str:
    state = _detect_state(product)
    if not state:
        return "No specific Indian state detected — provide general India-wide analysis."
    return (
        f"STATE DETECTED: {state['state'].replace('_',' ').title()}\n"
        f"Key industry clusters: {state.get('cluster','')}\n"
        f"Primary export port: {state.get('main_port','')}\n"
        f"Relevant schemes: {state.get('key_schemes','')}\n"
        f"Use this state context to give state-specific duty rates, port charges, and scheme benefits."
    )


def _import_analysis(product: str) -> dict:
    state_ctx = _state_context_block(product)
    prompt = f"""{IMPORT_CONTEXT}

{state_ctx}

Product being imported INTO INDIA: {product}

Return ONLY this JSON with real values specific to this product and state:
{{
  "hs_code": "8-digit ITC-HS",
  "product_description": "brief description",
  "basic_customs_duty_percent": "X%",
  "social_welfare_surcharge_percent": "X% (10% of BCD)",
  "igst_percent": "X% (5/12/18/28 only)",
  "total_landed_cost_percent": "approx % above CIF",
  "import_policy_status": "Free",
  "license_required": false,
  "scomet_applicable": false,
  "special_conditions": "any conditions or empty string",
  "state_specific_note": "state-specific port/scheme/cluster info if state detected, else India-general",
  "data_confidence": "high",
  "validation_warning": null,
  "plain_summary": "2-3 sentence plain English explanation of the key import duties and restrictions for this product, mentioning total cost burden and any licence/restriction flags"
}}"""
    r = _call_llama(prompt, max_tokens=1400)
    if "error" not in r: r = _validate_hs(r)
    return r


def _export_analysis(product: str) -> dict:
    state_ctx = _state_context_block(product)
    prompt = f"""{EXPORT_CONTEXT}

{state_ctx}

Product being EXPORTED FROM INDIA: {product}

Return ONLY this JSON:
{{
  "hs_code": "8-digit ITC-HS",
  "product_description": "brief description",
  "export_policy_status": "Free",
  "export_duty_percent": "0%",
  "rodtep_applicable": true,
  "rodtep_rate_percent": "X%",
  "rosctl_applicable": false,
  "export_incentive_notes": "applicable incentives including state schemes",
  "documentation_required": "key documents",
  "restricted_countries": "none or list",
  "state_specific_note": "which port to use, state cluster benefits, APEDA/EPC relevant to this state",
  "data_confidence": "high",
  "validation_warning": null,
  "plain_summary": "2-3 sentence plain English summary of export opportunity: incentives available, policy status, and state-specific advantages like port or cluster"
}}"""
    r = _call_llama(prompt, max_tokens=1400)
    if "error" not in r: r = _validate_hs(r)
    return r


def _knowledge_analysis(product: str) -> dict:
    state_ctx = _state_context_block(product)
    prompt = f"""{KNOWLEDGE_CONTEXT}

{state_ctx}

Product: {product}

Return ONLY this JSON:
{{
  "hs_code": "8-digit ITC-HS",
  "product_description": "brief description",
  "gst_percent": "X%",
  "gst_category": "Exempt / Zero-rated / Reduced / Standard",
  "itc_available": true,
  "itc_conditions": "eligibility details",
  "compliance_requirements": "FSSAI/BIS/other requirements",
  "fssai_required": false,
  "bis_required": false,
  "other_regulatory": "other requirements or none",
  "risk_flags": null,
  "state_specific_note": "any state-specific GST or compliance note",
  "data_confidence": "high",
  "validation_warning": null,
  "plain_summary": "2-3 sentence plain English summary of GST rate, ITC eligibility, and key compliance requirements for this product"
}}"""
    r = _call_llama(prompt, max_tokens=1400)
    if "error" not in r: r = _validate_hs(r)
    return r


def _validate_hs(result: dict) -> dict:
    hs = str(result.get("hs_code","")).strip()
    if not hs.isdigit() or len(hs) not in (6,8):
        result["validation_warning"] = (
            f"HS code '{hs}' may be incorrect — ITC-HS codes are 8 digits. Verify at icegate.gov.in")
    return result


# ════════════════════════════════════════════════════════════════════
# TRADEGPT CHAT
# ════════════════════════════════════════════════════════════════════

def chat_with_tradegpt(history: list, user_message: str) -> dict:
    state = _detect_state(user_message)
    state_note = (
        f"\nUser appears to be from {state['state'].replace('_',' ').title()} "
        f"— mention relevant ports ({state.get('main_port','')}), "
        f"clusters ({state.get('cluster','')[:60]}), and schemes ({state.get('key_schemes','')[:60]}) "
        f"where applicable."
    ) if state else ""

    messages = [{"role":"system","content":(
        "You are TradeGPT, an expert Indian trade advisor covering imports, exports, customs, "
        "GST, DGFT policy, state-wise industry clusters, FTAs, Incoterms, trade finance, and global trade. "
        "Give practical, actionable answers in plain English. "
        "Include state-specific port, cluster, and scheme information when the state is mentioned. "
        "Also cover global trade context — not just India."
        + state_note +
        "\nReturn JSON: {\"reply\": \"answer in plain English\", \"follow_up_questions\": [\"q1\",\"q2\"], \"relevant_links\": []}"
    )}]
    for m in (history or [])[-6:]:
        if isinstance(m,dict) and m.get("role") in ("user","assistant"):
            messages.append({"role":m["role"],"content":m["content"]})
    messages.append({"role":"user","content":user_message})

    headers = {"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"}
    payload = {"model":MODEL,"messages":messages,"max_tokens":1500,"temperature":0.3,"stream":False}
    for attempt in range(3):
        try:
            r = requests.post(API_URL, headers=headers, json=payload, timeout=120)
            r.raise_for_status()
            raw = r.json()["choices"][0]["message"]["content"].strip()
            clean = re.sub(r"^```(?:json)?\s*","",raw,flags=re.IGNORECASE)
            clean = re.sub(r"\s*```$","",clean).strip()
            s = clean.find("{"); e = clean.rfind("}")
            if s != -1 and e != -1: clean = clean[s:e+1]
            try:   return json.loads(clean)
            except: return {"reply":raw,"follow_up_questions":[],"relevant_links":[]}
        except Exception as ex:
            if attempt == 2: return {"error":str(ex),"reply":f"Error: {ex}","follow_up_questions":[]}
            time.sleep(1.5*(attempt+1))
    return {"reply":"Request failed. Please try again.","follow_up_questions":[]}


# ════════════════════════════════════════════════════════════════════
# RISK ANALYZER — state-aware, geopolitical
# ════════════════════════════════════════════════════════════════════

def analyze_trade_risk(product, origin_country, supplying_country, buyer_countries,
                       direction="Export", value_usd="50,000"):
    state = _detect_state(product + " " + origin_country)
    state_note = (
        f"Origin state detected: {state['state'].replace('_',' ').title()}. "
        f"Primary port: {state.get('main_port','')}. "
        f"Key schemes: {state.get('key_schemes','')}."
    ) if state else "No specific Indian state detected."

    prompt = (
        "You are a senior Indian trade risk analyst with global expertise.\n\n"
        f"Product: {product}\n"
        f"Origin: {origin_country} | Supplying: {supplying_country} | Buyers: {buyer_countries}\n"
        f"Direction: {direction} | Value: USD {value_usd}\n"
        f"{state_note}\n\n"
        "Consider: UN/US/EU sanctions, current geopolitical tensions (Russia-Ukraine, Red Sea, "
        "India-Pakistan, China-Taiwan), India FTAs, currency risk, port disruptions, "
        "anti-dumping orders, payment risk. Also consider global trade routes and insurance.\n\n"
        "Return ONLY this JSON:\n"
        "{\n"
        '  "overall_risk_score": 65,\n'
        '  "risk_level": "Medium",\n'
        '  "executive_summary": "3-sentence plain English risk summary",\n'
        '  "geopolitical_alert": "current concern or null",\n'
        '  "origin_supplying_mismatch_risk": "mismatch risk or null",\n'
        '  "risk_categories": [\n'
        '    {"category":"Regulatory & Sanctions","score":45,"level":"Medium","details":"plain English details","mitigation":"plain English action"},\n'
        '    {"category":"Geopolitical Risk","score":30,"level":"Low","details":"details","mitigation":"action"},\n'
        '    {"category":"Currency & Payment","score":40,"level":"Medium","details":"details","mitigation":"action"},\n'
        '    {"category":"Logistics & Routing","score":35,"level":"Low","details":"details","mitigation":"action"},\n'
        '    {"category":"Market & Demand","score":50,"level":"Medium","details":"details","mitigation":"action"},\n'
        '    {"category":"Compliance & Documentation","score":25,"level":"Low","details":"details","mitigation":"action"}\n'
        '  ],\n'
        '  "key_recommendations": ["action 1 in plain English","action 2","action 3"],\n'
        '  "payment_terms_advice": "recommended payment method and reason",\n'
        '  "insurance_suggestion": "insurance type and why",\n'
        '  "state_port_advice": "which Indian port and why, considering detected state",\n'
        '  "fta_applicable": false,\n'
        '  "fta_detail": null,\n'
        '  "plain_summary": "2-3 sentence plain English bottom line for a trader",\n'
        '  "data_confidence": "medium"\n'
        "}"
    )
    return _call_llama(prompt, max_tokens=2500, use_cache=False)


# ════════════════════════════════════════════════════════════════════
# PRICE INTELLIGENCE — flat numeric + English summary
# ════════════════════════════════════════════════════════════════════

def get_price_intelligence(product: str, quantity: str, market: str) -> dict:
    state = _detect_state(product)
    state_note = (
        f"Seller/origin state: {state['state'].replace('_',' ').title()}. "
        f"Export port: {state.get('main_port','')}. "
        f"Note any state-specific price advantage or cluster."
    ) if state else "No specific Indian state mentioned."

    prompt = f"""You are a global commodity price analyst specializing in Indian exports.

Product: {product}
Quantity: {quantity}
Target Market: {market}
{state_note}

Provide REALISTIC 2024 price data. All numeric fields must be actual numbers (NOT strings or zero).

Return ONLY this JSON:
{{
  "product": "{product}",
  "fob_usd": 1100,
  "dom_inr": 82000,
  "landed_usd": 1500,
  "margin_min_pct": 12,
  "margin_max_pct": 22,
  "price_unit": "per MT",
  "india_fob_price_usd": {{"min": 900, "max": 1400, "typical": 1100, "unit": "per MT"}},
  "india_domestic_price_inr": {{"min": 70000, "max": 100000, "typical": 82000, "unit": "per MT"}},
  "target_market_landed_usd": {{"min": 1200, "max": 1800, "typical": 1500, "unit": "per MT"}},
  "gross_margin_pct": {{"min": 12, "max": 22}},
  "global_price_trend": "Rising",
  "trend_reason": "specific reason for {product} price trend",
  "india_price_advantage": "India's specific pricing advantage for {product}",
  "state_advantage": "state-specific cluster or quality advantage if applicable",
  "competitor_prices": [
    {{"country": "top competitor country", "price_usd_per_unit": 950, "quality_note": "note"}},
    {{"country": "second competitor", "price_usd_per_unit": 1050, "quality_note": "note"}}
  ],
  "pricing_strategy": "recommended strategy for {market}",
  "key_price_drivers": ["driver 1", "seasonal factor", "global demand factor"],
  "data_note": "Indicative 2024 estimates. Verify with real quotes before trading.",
  "plain_summary": "2-3 sentence plain English summary: what is the typical export price, margin potential, and India's competitive position in {market}",
  "data_confidence": "medium"
}}

CRITICAL: fob_usd, dom_inr, landed_usd = actual NUMBERS for {product}. Never use 0."""
    return _call_llama(prompt, max_tokens=2000, use_cache=False)


# ════════════════════════════════════════════════════════════════════
# COMPETITOR INTELLIGENCE — global + state context
# ════════════════════════════════════════════════════════════════════

def get_competitor_intelligence(product: str, market: str) -> dict:
    state = _detect_state(product)
    state_note = (
        f"Indian origin cluster: {state['state'].replace('_',' ').title()} "
        f"({state.get('cluster','')[:80]}). "
        f"Mention this cluster's specific advantages vs global competitors."
    ) if state else "Provide India-wide competitive analysis."

    prompt = f"""You are a trade intelligence analyst with global market expertise.

Product: {product}
Target Market: {market}
{state_note}

Identify ACTUAL competing countries. Do NOT use generic placeholders.

Return ONLY this JSON:
{{
  "product": "{product}",
  "market": "{market}",
  "india_market_share_pct": 15,
  "india_rank": 3,
  "market_total_imports_usd_m": 500,
  "market_entry_difficulty": "Medium",
  "india_strengths": ["specific strength 1","specific strength 2","specific strength 3"],
  "india_weaknesses": ["specific weakness 1","specific weakness 2"],
  "top_competitors": [
    {{"country":"ACTUAL #1 exporter","rank":1,"share_pct":32,"market_share_pct":32,
      "price_level":"X% cheaper/pricier than India","quality_position":"description",
      "india_vs_this_competitor":"how India can beat them specifically"}},
    {{"country":"ACTUAL #2 exporter","rank":2,"share_pct":20,"market_share_pct":20,
      "price_level":"comparison","quality_position":"description",
      "india_vs_this_competitor":"India advantage"}},
    {{"country":"ACTUAL #3 exporter","rank":4,"share_pct":10,"market_share_pct":10,
      "price_level":"comparison","quality_position":"description",
      "india_vs_this_competitor":"India advantage"}}
  ],
  "differentiation_strategy": "2-3 sentence specific strategy for India to gain share in {market} — pricing, certification, branding",
  "market_entry_barriers": ["barrier 1","barrier 2"],
  "quick_win_opportunities": ["opportunity 1","opportunity 2"],
  "global_trade_context": "1-2 sentences on global supply chain trends affecting {product} in {market}",
  "plain_summary": "2-3 sentence plain English summary of India's competitive position and recommended action",
  "data_confidence": "medium"
}}

CRITICAL: india_market_share_pct and india_rank = NUMBERS not strings."""
    return _call_llama(prompt, max_tokens=2400, use_cache=False)


# ════════════════════════════════════════════════════════════════════
# SMART TRADE IDEAS — state-specific
# ════════════════════════════════════════════════════════════════════

def generate_smart_trade_ideas(profile: str, budget: str, direction: str, industry: str) -> dict:
    state = _detect_state(profile + " " + industry)
    state_note = (
        f"Trader's state: {state['state'].replace('_',' ').title()}. "
        f"Local clusters: {state.get('cluster','')}. "
        f"Port: {state.get('main_port','')}. "
        f"Schemes: {state.get('key_schemes','')}. "
        f"Prioritize products that leverage this state's existing industry clusters."
    ) if state else "No specific state detected — provide India-wide ideas."

    ctx = f"Profile: {profile}. Budget: {budget}. Direction: {direction}. Industry: {industry}. {state_note}"

    def _schema(rank):
        return (
            f'{{"rank":{rank},"title":"title","product":"product name",'
            f'"hs_code_range":"HS Chapter XX","target_markets":["Country1","Country2"],'
            f'"initial_investment_inr":"X lakhs","monthly_revenue_potential_inr":"X lakhs",'
            f'"typical_margin_pct":"X-Y%","difficulty_level":"Easy/Medium/Hard",'
            f'"why_now":"one sentence","india_advantage":"one sentence",'
            f'"state_cluster_link":"how this links to detected state cluster",'
            f'"relevant_schemes":["RoDTEP"],"key_challenge":"one sentence","first_step":"one sentence"}}'
        )

    p1 = (
        "You are a senior Indian trade consultant. Generate 3 specific business ideas.\n\n"
        f"{ctx}\n\nUse real INR figures, fit budget, focus on stated industry.\n\n"
        "Return ONLY JSON:\n"
        '{"profile_analysis":"2-sentence assessment","most_recommended":1,"ideas":['
        f"{_schema(1)},{_schema(2)},{_schema(3)}]}}"
    )
    r1 = _call_llama(p1, max_tokens=2400)
    if "error" in r1: return r1

    p2 = (
        "Generate 2 MORE niche/value-added trade ideas (ideas 4 and 5).\n\n"
        f"{ctx}\n\nReturn ONLY JSON:\n"
        f'{{"ideas":[{_schema(4)},{_schema(5)}]}}'
    )
    r2 = _call_llama(p2, max_tokens=1600)
    ideas2 = r2.get("ideas",[]) if "error" not in r2 else []
    all_ideas = r1.get("ideas",[]) + ideas2
    for i, idea in enumerate(all_ideas): idea["rank"] = i+1
    return {
        "profile_analysis": r1.get("profile_analysis",""),
        "most_recommended":  r1.get("most_recommended",1),
        "ideas": all_ideas,
    }


# ════════════════════════════════════════════════════════════════════
# SUPPLIER FINDER — dynamic, world context
# ════════════════════════════════════════════════════════════════════

def find_global_suppliers(product: str, quantity: str, quality: str, origin: str) -> dict:
    origin_clause = (
        f"Preferred origin: {origin}. Prioritize {origin} suppliers."
        if origin and origin.lower() not in ("any","") else
        "No origin preference — rank by price, quality, lead time, and FTA benefit with India."
    )
    prompt = f"""You are a global sourcing expert for Indian importers.

Product to import into India: {product}
Quantity: {quantity} | Quality: {quality}
{origin_clause}

Identify the ACTUAL top 3 source countries for {product}. Use real trade knowledge.

Return ONLY this JSON:
{{
  "product": "{product}",
  "global_supply_overview": "2-sentence factual overview of global supply for {product}",
  "recommended_origin": "best country with brief reason",
  "top_supply_origins": [
    {{
      "country": "ACTUAL #1 global exporter of {product}",
      "fob_price_range_usd": "realistic FOB range for {quantity}",
      "min_order_qty": "typical MOQ",
      "lead_time_weeks": 4,
      "quality_level": "{quality}",
      "bcd_pct": "India BCD for {product} from this country",
      "igst_pct": "18%",
      "total_landed_markup_pct": "estimated % above FOB after India duties",
      "fta_with_india": false,
      "fta_saving": null,
      "concerns": ["real concern for {product} from this country"],
      "recommended_incoterm": "FOB",
      "why_recommended": "specific reason this country is best for {product}",
      "plain_assessment": "1-2 sentence plain English assessment"
    }},
    {{
      "country": "ACTUAL #2 exporter",
      "fob_price_range_usd": "range",
      "min_order_qty": "MOQ",
      "lead_time_weeks": 6,
      "quality_level": "Standard",
      "bcd_pct": "India BCD",
      "igst_pct": "18%",
      "total_landed_markup_pct": "X%",
      "fta_with_india": false,
      "fta_saving": null,
      "concerns": ["concern"],
      "recommended_incoterm": "CIF",
      "why_recommended": "reason",
      "plain_assessment": "1-2 sentence plain English"
    }},
    {{
      "country": "ACTUAL #3 option",
      "fob_price_range_usd": "range",
      "min_order_qty": "MOQ",
      "lead_time_weeks": 8,
      "quality_level": "Budget",
      "bcd_pct": "India BCD",
      "igst_pct": "18%",
      "total_landed_markup_pct": "X%",
      "fta_with_india": false,
      "fta_saving": null,
      "concerns": ["concern 1","quality risk"],
      "recommended_incoterm": "FOB",
      "why_recommended": "reason",
      "plain_assessment": "1-2 sentence plain English"
    }}
  ],
  "verification_tips": ["tip 1","tip 2","tip 3"],
  "plain_summary": "2-3 sentence plain English recommendation on where to source and why",
  "data_confidence": "medium"
}}"""
    return _call_llama(prompt, max_tokens=3000, use_cache=False)


# ════════════════════════════════════════════════════════════════════
# AI TRADE REPORT
# ════════════════════════════════════════════════════════════════════

def generate_ai_trade_report(product: str, direction: str, countries: list) -> dict:
    countries_str = ", ".join(countries) if countries else "USA, UAE, Germany"
    first_country = countries[0] if countries else "USA"
    state = _detect_state(product)
    state_note = (
        f"Indian origin: {state['state'].replace('_',' ').title()} "
        f"(port: {state.get('main_port','')}, schemes: {state.get('key_schemes','')})."
    ) if state else ""

    market_entries = []
    for c in (countries or ["USA","UAE","Germany"]):
        market_entries.append(
            f'{{"country":"{c}","import_size_usd_m":500,"india_share_pct":8,'
            f'"growth_rate_pct":10,"opportunity_score":70,"entry_difficulty":"Medium",'
            f'"tariff_pct":5,"fta_benefit":"Check applicable FTA",'
            f'"key_buyers":["Importers","Distributors"],'
            f'"entry_strategy":"Direct export via trade portal",'
            f'"plain_note":"1 sentence on this market opportunity"}}'
        )

    prompt = f"""You are a senior Indian trade consultant. Write a comprehensive trade report.

Product: {product}
Direction: {direction}
Target Countries: {countries_str}
{state_note}

Return ONLY this JSON. executive_summary MUST be a JSON object.

{{
  "report_title": "Trade Opportunity Report: {product}",
  "executive_summary": {{
    "headline_finding": "Most important finding about {product} {direction.lower()} opportunity",
    "market_opportunity": "Quantified opportunity: market size, growth, India current share",
    "top_recommendation": "Single most actionable recommendation",
    "key_risks": ["main risk 1","main risk 2"],
    "plain_verdict": "1-2 sentence plain English verdict for a trader deciding whether to proceed"
  }},
  "market_opportunity_score": 72,
  "india_export_value_2023_usd": "approximate annual value",
  "global_market_size_usd": "global market size",
  "growth_rate_pct": "X%",
  "market_analysis": [{",".join(market_entries)}],
  "regulatory_snapshot": {{
    "hs_code": "8-digit HS code",
    "export_policy": "Free",
    "key_certifications": ["cert 1","cert 2"],
    "documentation": ["Shipping Bill","Commercial Invoice","Packing List","Certificate of Origin"]
  }},
  "financial_projection": {{
    "estimated_fob_price_usd": "USD X per MT/unit",
    "container_load_value_usd": "USD X per 20ft container",
    "rodtep_benefit_pct": "X%",
    "estimated_net_margin_pct": "X-Y%"
  }},
  "action_plan": [
    {{"week":"1-2","action":"Obtain IEC from DGFT portal","output":"IEC Certificate"}},
    {{"week":"3-4","action":"Get certifications for {first_country}","output":"Certificates"}},
    {{"week":"5-8","action":"Register on India Trade Portal and find {first_country} buyers","output":"Qualified leads"}},
    {{"week":"9-12","action":"Finalise first export order and arrange logistics","output":"First shipment"}}
  ],
  "risks": ["risk specific to {product}","currency risk","quality/compliance risk"],
  "plain_summary": "3-4 sentence plain English report summary for a non-expert trader",
  "data_confidence": "medium"
}}

CRITICAL: executive_summary = JSON object. All numeric fields = NUMBERS."""
    return _call_llama(prompt, max_tokens=4000, use_cache=False)


# ════════════════════════════════════════════════════════════════════
# DOCUMENT ANALYZER — robust field extraction
# ════════════════════════════════════════════════════════════════════

def analyze_trade_document(document_text: str) -> dict:
    truncated = document_text[:4500]
    prompt = f"""You are an expert Indian trade document analyst. Read this document carefully.

DOCUMENT:
{truncated}

Extract every field you can find. If a field is genuinely absent, use null.
DO NOT use placeholder text like "number or null" — extract real values or null.

Field extraction hints:
- document_number: look for Invoice No, PO No, Order No, BL No, Ref No
- document_date: look for Date, Dated, Invoice Date, PO Date (format: YYYY-MM-DD)
- incoterm: look for FOB, CIF, EXW, DAP, CPT, DDP in terms or conditions
- total_invoice_value.amount: look for Total Amount, Grand Total, Invoice Total (as a number)
- exporter.name: look for Seller, Shipper, Exporter, From
- importer.name: look for Buyer, Consignee, Importer, To
- products: extract each line item

Return ONLY this JSON:
{{
  "document_type": "Commercial Invoice or Packing List or Bill of Lading or Purchase Order or Certificate of Origin or Letter of Credit or Other — identify from content",
  "compliance_status": "OK if complete and valid, Review Needed if missing key fields",
  "document_number": "actual number from doc or null",
  "document_date": "YYYY-MM-DD or null",
  "incoterm": "FOB/CIF/EXW/etc or null",
  "exporter": {{
    "name": "actual exporter name from doc or null",
    "iec_code": "IEC code if present or null",
    "address": "address if present or null"
  }},
  "importer": {{
    "name": "actual importer/buyer name from doc or null",
    "country": "destination country or null",
    "address": "address if present or null"
  }},
  "total_invoice_value": {{
    "amount": 0.0,
    "currency": "USD"
  }},
  "products": [
    {{
      "line_no": "1",
      "description": "actual product description from doc",
      "hs_code": "HS code if present or null",
      "hs_code_valid": true,
      "quantity": "actual quantity",
      "unit": "MT/KG/PCS/etc",
      "unit_price_usd": 0.0,
      "total_value_usd": 0.0
    }}
  ],
  "flags": [],
  "missing_critical_fields": [],
  "compliance_notes": "2-3 sentence plain English assessment: is this document complete and trade-ready? What is present and what is missing?",
  "data_confidence": "high"
}}

IMPORTANT: Extract REAL values from the document above. Never fill placeholder text."""
    return _call_llama(prompt, max_tokens=2500, use_cache=False)


# ════════════════════════════════════════════════════════════════════
# COMPLIANCE CHECKER
# ════════════════════════════════════════════════════════════════════

def check_trade_compliance(product, origin, destination, value_usd=50000.0):
    state = _detect_state(product + " " + origin)
    state_note = (
        f"Indian origin state: {state['state'].replace('_',' ').title()}. "
        f"Use port {state.get('main_port','')} and mention relevant state schemes."
    ) if state else ""

    prompt = f"""You are an Indian trade compliance officer.

Product: {product}
Origin: {origin} → Destination: {destination} | Value: USD {value_usd:,.0f}
{state_note}

Return ONLY this JSON. checks MUST be a JSON OBJECT (not an array).

{{
  "overall_compliance_status": "CLEAR",
  "compliance_summary": "Plain English: is this trade clear to proceed, any restrictions?",
  "checks": {{
    "scomet_control": {{"status": "CLEAR", "detail": "plain English SCOMET assessment"}},
    "dgft_policy": {{"status": "CLEAR", "detail": "plain English DGFT policy status"}},
    "un_sanctions": {{"status": "CLEAR", "detail": "plain English sanctions check for {destination}"}},
    "prohibited_items": {{"status": "CLEAR", "detail": "plain English prohibited goods check"}},
    "licence_required": {{"status": "NOT REQUIRED", "detail": "plain English licence requirement"}},
    "quality_standards": {{"status": "OK", "detail": "plain English quality/cert requirements for {destination}"}}
  }},
  "required_documents": [
    "Shipping Bill / Bill of Entry",
    "Commercial Invoice",
    "Packing List",
    "Certificate of Origin",
    "product-specific certificate if required"
  ],
  "recommended_next_steps": [
    "Step 1: specific action for {product} to {destination}",
    "Step 2: documentation preparation",
    "Step 3: regulatory filing"
  ],
  "state_port_recommendation": "which port to use and why based on origin state",
  "duties_estimate": {{
    "bcd_pct": "X%",
    "igst_pct": "X%",
    "total_duty_usd": "USD estimate"
  }},
  "plain_summary": "2-3 sentence plain English bottom line: can this trade proceed, what to watch out for?",
  "data_confidence": "medium"
}}

CRITICAL: checks = JSON OBJECT with 6 keys. overall_compliance_status = CLEAR/CONDITIONAL/BLOCKED."""
    return _call_llama(prompt, max_tokens=2000, use_cache=False)


# ════════════════════════════════════════════════════════════════════
# HS CODE ENGINE
# ════════════════════════════════════════════════════════════════════

def classify_hs_code(product: str) -> dict:
    state = _detect_state(product)
    state_note = (
        f"Product likely from {state['state'].replace('_',' ').title()} — "
        f"classify using state-typical product specifications."
    ) if state else ""

    prompt = f"""You are an ITC-HS 2022 classification expert.

Product: {product}
{state_note}

Return ONLY valid JSON:
{{
  "hs_code": "8-digit ITC-HS 2022 code",
  "hs_description": "official ITC-HS description",
  "chapter_no": "XX",
  "chapter_name": "chapter name",
  "bcd": "X%",
  "igst": "X%",
  "total_import_burden_pct": "X%",
  "rodtep_rate": "X% or N/A",
  "scomet_restricted": false,
  "confidence": 0.92,
  "classification_rationale": "plain English explanation of why this HS code applies",
  "validation_warning": null
}}"""
    return _call_llama(prompt, max_tokens=1000)


# ════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ════════════════════════════════════════════════════════════════════

def health_check() -> dict:
    try:
        r = _call_llama('{"status":"ok"}', retries=1, use_cache=False)
        return {"status":"ok","model":MODEL} if "error" not in r else {"status":"error","message":r["error"]}
    except Exception as e:
        return {"status":"error","message":str(e)}