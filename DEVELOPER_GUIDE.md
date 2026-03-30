# 🎯 Quick Reference Guide - Using Production Hardening Modules

## For Developers: How to Use the New Protective Utilities

---

## 1️⃣ ENVIRONMENT VALIDATION
**Use When:** App startup

```python
# In app.py (at very top, before service imports)
from env_validator import assert_environment_ready
assert_environment_ready()  # Fails fast if env vars missing
```

**What it checks:**
- SUPABASE_URL ✓
- SUPABASE_SERVICE_KEY ✓
- SUPABASE_ANON_KEY ✓
- NVIDIA_API_KEY ✓
- SMTP_USER, SMTP_PASSWORD ✓

---

## 2️⃣ DATABASE SCHEMA VERIFICATION
**Use When:** App initialization

```python
# In app.py (after environment validation)
from db_schema_checker import assert_schema_ready
from supabase_service import supabase

assert_schema_ready(supabase)  # Logs warnings if schema incomplete
```

**What it checks:**
- ✓ Tables exist: profiles, audit_logs, query_limits, etc.
- ✓ RPC functions available: consume_query, get_query_status
- ⚠️ Logs if missing but allows app to continue

---

## 3️⃣ TOKEN & SESSION MANAGEMENT
**Use When:** Every page render with logged-in user

```python
# In protected pages
from auth_token_manager import check_and_refresh_token
from supabase_service import supabase_auth

result = check_and_refresh_token(supabase_auth)
if not result["token_valid"]:
    st.error("Please sign in again")
    st.stop()

# Or require valid token at page top:
from auth_token_manager import require_valid_token
require_valid_token()  # Blocks page if no valid token
```

---

## 4️⃣ FORM AUTO-SAVE (Prevent Data Loss)
**Use When:** Multi-field forms

```python
import streamlit as st
from form_state_manager import (
    save_form_state,
    show_resume_draft_button,
    create_auto_saving_text_input,
)

# Show resume button if draft exists
show_resume_draft_button("registration_form", "Registration")

with st.form("register_form"):
    email = st.text_input("Email")
    name = st.text_input("Name")
    
    # Auto-save form state
    save_form_state("registration_form", {
        "email": email,
        "name": name,
    })

# After successful submission:
from form_state_manager import clear_form_state
clear_form_state("registration_form")
```

---

## 5️⃣ XSS PROTECTION (Prevent Injection)
**Use When:** Displaying user-submitted content

```python
from input_sanitizer import sanitize_html

# Extraction from PDF/image
extracted_text = get_text_from_upload(file)

# Safe for Streamlit
safe_text = sanitize_html(extracted_text)
st.markdown(f"```\n{safe_text}\n```")  # Now safe!
```

---

## 6️⃣ INPUT VALIDATION
**Use When:** Before sending user inputs to LLM or DB

```python
from input_sanitizer import (
    validate_and_sanitize_trade_inputs,
    validate_country_code,
    sanitize_prompt_input,
)

# Validate trade query
validation = validate_and_sanitize_trade_inputs({
    "product": user_product,
    "origin": user_origin,
    "destination": user_dest,
})

if not validation["valid"]:
    st.error("Invalid inputs: " + ", ".join(validation["errors"]))
else:
    safe_data = validation["data"]
    result = analyze_trade(safe_data)

# Or sanitize individual field
safe_message = sanitize_prompt_input(user_message)
result = call_llama(safe_message)
```

---

## 7️⃣ AUDIT LOGGING
**Use When:** Important user actions (registration, API calls, security events)

```python
from audit_logger import (
    audit_log,
    audit_api_call,
    audit_security_violation,
)
from supabase_service import supabase

# Log user action
audit_log(
    supabase,
    user_id="user_123",
    event_type="api_call",
    resource="trade_analysis",
    details={"product": "Cotton"},
    status="success"
)

# Log API usage with timing
audit_api_call(
    supabase,
    user_id="user_123",
    api_name="nvidia_llama",
    parameters={"prompt_length": 500},
    response_time_ms=1234,
    tokens_consumed=150,
)

# Log security violation
audit_security_violation(
    supabase,
    violation_type="xss_attempt",
    user_id="user_456",
    details={"input": "<script>alert('xss')</script>"},
)
```

---

## 8️⃣ REQUEST IDEMPOTENCY
**Use When:** Forms that might be double-submitted

```python
from idempotency_manager import IdempotentRequest, idempotent_call

# Method 1: Context manager
user_id = st.session_state.user["id"]
with IdempotentRequest(user_id, "register_form") as req:
    if req.is_duplicate:
        st.warning("Registration already submitted. Please wait...")
        st.stop()
    
    # Perform registration
    result = sign_up_user(email, password)

# Method 2: Decorator
def expensive_function(x):
    return x ** 2

result = idempotent_call(
    user_id="user_123",
    function=expensive_function,
    x=10
)
# Second call within 5min returns cached result
```

---

## 9️⃣ PERFORMANCE MONITORING
**Use When:** Timing sensitive operations

```python
from performance_monitor import (
    measure_time,
    record_api_call,
    get_performance_summary,
)

# Decorator approach
@measure_time
def extract_pdf_text(file_bytes):
    # ...extraction logic...
    return text

# Manual timing
import time
start = time.time()
result = some_operation()
duration_ms = (time.time() - start) * 1000

record_api_call(
    "nvidia_api",
    "/chat/completions",
    "POST",
    duration_ms=duration_ms,
    status_code=200,
    response_size_bytes=len(str(result)),
)

# Get summary
summary = get_performance_summary()
st.write(f"API avg: {summary['api_avg_duration_ms']}ms")
```

---

## 🔟 CIRCUIT BREAKER
**Use When:** Wrapping unreliable external API calls

```python
from circuit_breaker import NVIDIA_API_BREAKER

# Automatically used in nvidia_service._call_llama()
# But you can use it for other APIs too:

from circuit_breaker import CircuitBreaker

breaker = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
)

try:
    result = breaker.call(unreliable_api_call, param1, param2)
except Exception as e:
    st.error(f"API down: {e}")
    # Returns cached response instead

# Check status
status = NVIDIA_API_BREAKER.get_status()
st.write(f"Circuit: {status['state']} ({status['failure_count']} failures)")
```

---

## 1️⃣1️⃣ GRACEFUL SHUTDOWN
**Use When:** Setting up app lifecycle

```python
from graceful_shutdown import (
    register_cleanup,
    setup_shutdown_handlers,
)

# Register cleanup functions
def flush_pending_data():
    logger.info("Flushing pending operations...")
    # Save state, close connections, etc.

register_cleanup(flush_pending_data, "flush_data")

# Install signal handlers (SIGTERM, SIGINT, atexit)
setup_shutdown_handlers()

# App will now gracefully shutdown:
# - Handle Ctrl+C cleanly
# - Handle docker/k8s SIGTERM
# - Execute all registered cleanups
```

---

## 📋 COMMON PATTERNS

### Pattern 1: Protecting an AI Analysis Function
```python
@measure_time
def analyze_trade(product: str, origin: str):
    # 1. Validate inputs
    validation = validate_and_sanitize_trade_inputs({
        "product": product, "origin": origin
    })
    if not validation["valid"]:
        return {"error": "Invalid inputs"}
    
    # 2. Check for duplicates (idempotency)
    user_id = st.session_state.user["id"]
    result = idempotent_call(
        user_id,
        _analyze_trade_impl,
        product=product,
        origin=origin,
    )
    
    # 3. Log the API call
    audit_api_call(supabase, user_id, "analyze_trade", ...)
    
    return result
```

### Pattern 2: Protected Page with Session Check
```python
# Top of page
from auth_token_manager import require_valid_token
require_valid_token()

st.title("Trade Analysis")
st.write(f"Welcome {st.session_state.user['email']}")

# Form with auto-save
from form_state_manager import show_resume_draft_button
show_resume_draft_button("trade_form", "Trade Analysis Form")

with st.form("trade_form"):
    product = st.text_input("Product")
    # ...more fields...
    submitted = st.form_submit_button("Analyze")

if submitted:
    # Perform analysis with all protections
    result = analyze_trade(product)
    clear_form_state("trade_form")
```

### Pattern 3: File Upload with Safety
```python
from document_scanner import scan_document
from input_sanitizer import sanitize_html

file = st.file_uploader("Upload PDF")
if file:
    # Automatically checks size limit (50MB)
    result = scan_document(
        file.read(),
        file.name,
    )
    
    if result["status"] == "success":
        # Text already sanitized for XSS
        st.write(result["text"])
        
        # Log the upload
        audit_log(
            supabase,
            st.session_state.user["id"],
            "document_upload",
            f"pdf_{file.name}",
        )
```

---

## 🚨 ERROR HANDLING

### When Environment Validation Fails
```
❌ ENVIRONMENT VALIDATION FAILED
Missing required environment variables:
• SUPABASE_URL: Supabase project URL
• SUPABASE_SERVICE_KEY: Supabase service role key

Add these to your .env file or environment
```
**Fix:** Add all vars to `.env`, restart app

### When Database Schema is Incomplete
```
⚠️ Database schema incomplete: Missing tables: activity_logs. Missing RPCs: consume_query.
Run 'sql_schema_v3.sql' in Supabase SQL editor.
App will continue with degraded functionality until schema is deployed.
```
**Fix:** Execute `sql_schema_v3.sql` in Supabase

### When Circuit Breaker is Open
```
CSV Circuit breaker is OPEN, returning cached response
```
**Expected:** This is normal during API outages. Continue using cached results.

### When Token Expires
```
❌ Your session has expired. Please sign in again.
```
**Wait:** System tries to auto-refresh. If this appears, user needs to re-login.

---

## 📊 TESTING THESE FEATURES

### Test Environment Validation
```bash
# Remove NVIDIA_API_KEY from .env
streamlit run app.py
# Should fail immediately with clear error
```

### Test Token Refresh
```python
# In browser console
# Wait > 55 minutes (token 1hr - 5min threshold)
# Should see automatic refresh without logout
```

### Test Form Auto-Save
```python
# Fill registration form partially
# Close browser tab
# Reopen app
# Should see "Resume draft?" button
```

### Test XSS Protection
```python
# Upload PDF with "<script>alert('xss')</script>" text
# Should display safely without executing
```

### Test Audit Logging
```python
# In Supabase
select * from audit_logs order by timestamp desc limit 10;
# Should see all user actions logged
```

---

**Ready to build production-safe features!** 🚀
