# 🇮🇳 Indian Trade Intelligence Engine

> AI-powered import/export compliance platform for Indian SME exporters

[![CI](https://github.com/Gnaneswar-S/ind-trade-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Gnaneswar-S/ind-trade-engine/actions)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-Cloud-red)](https://streamlit.io)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-green)](https://supabase.com)

**Live Demo:** [https://your-app.streamlit.app](https://your-app.streamlit.app)

---

## What it does

Indian SME exporters spend hours manually researching HS codes, tariff rates, and trade
compliance rules for every shipment — or pay ₹5,000–₹20,000 per consultation. This platform
automates that research across 13 AI-powered modules in under 10 seconds per query.

### Key modules

| Module | What it does |
|--------|-------------|
| 🔢 HS Code Engine | Classifies products to 8-digit HS codes with duty rates |
| ⚠️ Risk Analyzer | Geopolitical and compliance risk scoring per trade lane |
| 💰 Price Intelligence | Market price benchmarking and margin analysis |
| 🌍 Market Recommendations | Top import/export markets ranked by opportunity |
| 📄 Document Scanner | OCR + AI extraction from Bills of Lading, invoices, certificates |
| 🤖 TradeGPT | Conversational assistant for trade queries |
| 🔗 Supplier Finder | Verified supplier search by HS code and country |
| 🚢 Shipment Calculator | Landed cost including customs, freight, insurance |
| 📊 AI Reports | Full trade feasibility reports as PDF/Excel |
| 🥊 Competitor Intel | Market share and pricing analysis |
| 💡 Smart Trade Ideas | AI-generated product-market opportunity ideas |
| 🔮 Future Trends | Forecasting based on historical trade flow data |
| 🔎 Country Lookup | Bilateral trade stats between India and any country |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     Streamlit Frontend (app.py)                   │
│          Sidebar navigation → 13 page modules → Sidebar stats    │
└────────────┬──────────────────┬────────────────┬─────────────────┘
             │                  │                │
    ┌────────▼──────┐  ┌────────▼──────┐  ┌─────▼────────┐
    │ nvidia_service │  │ supabase_     │  │ query_       │
    │ (LLM calls)   │  │ service (auth)│  │ limiter      │
    │ Llama 3.3 70B  │  │ PKCE / RBAC  │  │ rate control │
    └────────┬──────┘  └────────┬──────┘  └─────┬────────┘
             │                  │                │
             └──────────────────▼────────────────┘
                         Supabase (PostgreSQL)
              profiles | trade_usage_logs | query_limits
```

**Auth flow:**
```
Register → supabase_auth.sign_up() → Confirmation email sent
         → User clicks link → ?code= redirect → PKCE exchange
         → Session set → Auto-logged in → Dashboard
```

**Rate limit flow:**
```
Page load → rate_guard(user) → get_limit_status()
          → [session cache] → [Postgres RPC] → [log count fallback]
          → Show remaining quota → User submits
          → AI call → consume_query(cost=0.5 or 1.0 or 2.0)
          → DB updated atomically → Sidebar refreshes
```

---

## Tech stack

| Layer | Technology |
|-------|-----------|
| Frontend | Python + Streamlit |
| AI / LLM | Llama 3.3 70B via NVIDIA NIM API |
| Database | Supabase (PostgreSQL) with Row Level Security |
| Auth | Supabase Auth — PKCE flow, RBAC, OTP, 2FA |
| Rate limiting | PostgreSQL RPC (atomic) + table upsert + session fallback |
| OCR | pdfplumber → PyMuPDF → Tesseract (4-strategy cascade) |
| Deployment | Streamlit Community Cloud |
| CI/CD | GitHub Actions (lint → test → deploy) |

---

## Local setup

### 1. Clone the repository

```bash
git clone https://github.com/Gnaneswar-S/ind-trade-engine.git
cd ind-trade-engine
```

### 2. Create virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Tesseract (for OCR)

**Windows:** Download installer from https://github.com/UB-Mannheim/tesseract/wiki
**macOS:** `brew install tesseract`
**Linux:** `sudo apt install tesseract-ocr`

### 5. Create .env file

Copy `.env.example` to `.env` and fill in your credentials:

```env
NVIDIA_API_KEY=nvapi-your-key-here
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...your-service-role-key...
SUPABASE_ANON_KEY=eyJ...your-anon-key...
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASS=xxxx xxxx xxxx xxxx
SMTP_FROM=your@gmail.com
ADMIN_EMAIL=your@gmail.com
ADMIN_EMAILS=your@gmail.com
APP_URL=http://localhost:8501
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### 6. Run the database schema

Open Supabase Dashboard → SQL Editor → paste and run `sql_schema_v3.sql`

### 7. Configure Supabase auth settings

Go to Supabase Dashboard → Authentication → URL Configuration:
- **Site URL:** `http://localhost:8501` (change to your app URL in production)
- **Redirect URLs:** `http://localhost:8501/**`

### 8. Start the app

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501)

---

## Screenshots

> Add screenshots here after running the app locally.
> Suggested screenshots:
> 1. `screenshots/01_dashboard.png` — main dashboard with trade stats
> 2. `screenshots/02_hs_engine.png` — HS code classification result
> 3. `screenshots/03_risk_analyzer.png` — risk scoring output
> 4. `screenshots/04_document_scan.png` — OCR extraction from PDF
> 5. `screenshots/05_tradegpt.png` — TradeGPT conversation

```markdown
![Dashboard](screenshots/01_dashboard.png)
![HS Engine](screenshots/02_hs_engine.png)
```

---

## Deployment to Streamlit Cloud

### Step 1 — Push to GitHub

```bash
git add .
git commit -m "deploy: production ready"
git push origin main
```

### Step 2 — Connect to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **New app**
3. Select your GitHub repo and `app.py`
4. Click **Advanced settings** → paste all your `.env` values into the **Secrets** box:

```toml
NVIDIA_API_KEY = "nvapi-..."
SUPABASE_URL = "https://..."
SUPABASE_SERVICE_KEY = "eyJ..."
SUPABASE_ANON_KEY = "eyJ..."
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = "587"
SMTP_USER = "your@gmail.com"
SMTP_PASS = "xxxx xxxx xxxx xxxx"
APP_URL = "https://your-app.streamlit.app"
ADMIN_EMAILS = "your@gmail.com"
```

### Step 3 — Update Supabase redirect URL

Go to Supabase Dashboard → Authentication → URL Configuration:
- **Site URL:** `https://your-app.streamlit.app`
- **Redirect URLs:** `https://your-app.streamlit.app/**`

### Step 4 — Add GitHub Actions secrets

Go to your repo → Settings → Secrets and variables → Actions → New repository secret.
Add: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `NVIDIA_API_KEY`, `STREAMLIT_APP_URL`

---

## Subscription tiers

| Plan | Daily Queries | Price |
|------|--------------|-------|
| Free | 15 | ₹0 |
| Standard | 60 | ₹299/month |
| Analyst | 200 | ₹699/month |
| Pro | 600 | ₹1,999/month |
| Admin | Unlimited | Internal |

---

## Project structure

```
ind-trade-engine/
├── app.py                  # Main Streamlit app — all 13 page modules
├── nvidia_service.py       # All LLM calls to Llama 3.3 70B
├── supabase_service.py     # Auth, profiles, usage logging
├── query_limiter.py        # Rate limiting (3-mode fallback)
├── email_confirmation.py   # PKCE confirmation flow handler
├── document_scanner.py     # 4-strategy OCR pipeline
├── trade_advisor.py        # Trade analysis functions
├── hs_engine.py            # HS code classification
├── trade_data_services.py  # Dataset loading and market data
├── otp_service.py          # OTP for password reset
├── report_service.py       # PDF and Excel export
├── admin_dashboard.py      # Admin user management panel
├── config_settings.py      # Centralised configuration
├── sql_schema_v3.sql       # Full database schema with RPCs
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variable template
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions CI/CD pipeline
└── tests/
    ├── test_query_limiter.py
    ├── test_supabase_service.py
    └── test_email_confirmation.py
```

---

## Git workflow

### First time pushing to GitHub

```bash
# Initialise git (if not done)
git init

# Add remote (replace with your repo URL)
git remote add origin https://github.com/Gnaneswar-S/ind-trade-engine.git

# Stage all files
git add .

# Check what will be committed (ALWAYS check this before committing)
git status

# Commit
git commit -m "feat: initial production release v3.0"

# Push to GitHub
git push -u origin main
```

### Day-to-day workflow

```bash
# Before starting work — pull latest changes
git pull origin main

# After making changes — stage specific files
git add app.py query_limiter.py email_confirmation.py

# Or stage everything
git add .

# Check what you're committing
git status

# Commit with a meaningful message
git commit -m "fix: blank page after email confirmation"

# Push
git push origin main
```

### Commit message format (use this for JPMC — they check git history)

```
feat:  new feature or module
fix:   bug fix
chore: dependency update, config change
docs:  README, comments
test:  adding or fixing tests
```

### If you accidentally committed a secret

```bash
# Remove a file from git history (DANGEROUS — only if needed)
git rm --cached .env
echo ".env" >> .gitignore
git commit -m "chore: remove .env from tracking"
git push
```

---

## Environment variables reference

| Variable | Where to get it | Required |
|----------|----------------|----------|
| `NVIDIA_API_KEY` | [build.nvidia.com](https://build.nvidia.com) | Yes |
| `SUPABASE_URL` | Supabase → Project Settings → API | Yes |
| `SUPABASE_SERVICE_KEY` | Supabase → Project Settings → API → service_role | Yes |
| `SUPABASE_ANON_KEY` | Supabase → Project Settings → API → anon | Yes |
| `SMTP_HOST` | Your email provider | For OTP emails |
| `SMTP_PASS` | Gmail: Settings → App passwords | For OTP emails |
| `APP_URL` | Your Streamlit app URL | For auth redirects |
| `ADMIN_EMAILS` | Your email | For admin access |
| `TESSERACT_CMD` | Tesseract install path | For OCR |

---

## License

MIT — free to use, modify, and distribute.

---

*Built by [Gnaneswar Somisetty](https://linkedin.com/in/gnaneswars) — B.Tech CSE, KL University*