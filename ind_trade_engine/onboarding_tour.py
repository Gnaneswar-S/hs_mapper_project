# onboarding_tour.py
# First-login walkthrough for new users.
# Shows a step-by-step guide the first time a user logs in after confirming email.
# State is stored in session so it only shows once per session.

import streamlit as st

_TOUR_KEY = "_onboarding_shown"

TOUR_STEPS = [
    {
        "icon":  "🔍",
        "title": "Trade Analysis",
        "body":  "Enter any product and choose Import, Export, or Knowledge mode. "
                 "Llama 3.3 70B returns duty rates, HS code, policy status in seconds.",
    },
    {
        "icon":  "🔢",
        "title": "HS Code Engine",
        "body":  "Paste a product description to get its 8-digit ITC-HS 2022 code "
                 "with BCD, IGST, RoDTEP rate, and SCOMET flag — all in one click.",
    },
    {
        "icon":  "⚠️",
        "title": "Risk Analyzer",
        "body":  "Get a 6-dimension risk score covering sanctions, geopolitical tensions, "
                 "currency, logistics, compliance, and payment risk.",
    },
    {
        "icon":  "🤖",
        "title": "TradeGPT",
        "body":  "Ask anything about Indian trade — DGFT policy, FTA benefits, "
                 "ECGC, Incoterms, IEC registration — in plain language.",
    },
    {
        "icon":  "📊",
        "title": "AI Reports",
        "body":  "Generate a full trade feasibility report for any product and market "
                 "with a 90-day action plan. Export as Excel or PDF.",
    },
]


def should_show_tour() -> bool:
    """Returns True if the onboarding tour should be shown this session."""
    return not st.session_state.get(_TOUR_KEY, False)


def mark_tour_shown() -> None:
    """Mark tour as seen for this session."""
    st.session_state[_TOUR_KEY] = True


def render_onboarding_tour() -> None:
    """
    Render the onboarding tour as a collapsible card.
    Call from page_dashboard() when should_show_tour() is True.
    """
    with st.expander("👋 Welcome! Here's what you can do — click to hide", expanded=True):
        st.markdown("""
        <div style="background:linear-gradient(135deg,#0d1627,#111827);
                    border:1px solid #1e2d45;border-radius:12px;padding:20px;">
          <h3 style="color:#63b3ed;margin:0 0 16px;">🇮🇳 Indian Trade Intelligence Engine</h3>
          <p style="color:#a0aec0;font-size:0.88rem;margin:0 0 20px;">
            Powered by Llama 3.3 70B — 13 AI modules for Indian import/export compliance.
          </p>
        </div>
        """, unsafe_allow_html=True)

        cols = st.columns(len(TOUR_STEPS))
        for col, step in zip(cols, TOUR_STEPS):
            with col:
                st.markdown(f"""
                <div style="background:#0d1627;border:1px solid #1e2d45;border-radius:10px;
                            padding:14px;text-align:center;height:160px;">
                  <div style="font-size:1.8rem;">{step['icon']}</div>
                  <div style="color:#e2e8f0;font-weight:600;font-size:0.82rem;margin:6px 0;">
                    {step['title']}
                  </div>
                  <div style="color:#6b7a99;font-size:0.72rem;line-height:1.4;">
                    {step['body']}
                  </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✅ Got it, hide this guide", key="dismiss_tour", use_container_width=False):
            mark_tour_shown()
            st.rerun()