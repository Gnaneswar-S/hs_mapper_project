# admin_dashboard.py
# Standalone admin dashboard — called from app.py render_admin_dashboard().
#
# Fixes v3.1:
#   - _fetch_user_activity: also checks auth_logs for last activity (PRO users
#     who haven't run a trade query still show last login as "Last Active")
#   - Robust count: uses len(data) fallback when .count is None (RLS issue)
#   - Revenue section shows all roles, not just pro/free

import streamlit as st
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta, timezone

from services.supabase_service import (
    supabase,
    get_all_users,
    get_all_queries,
    get_platform_stats,
    update_user_role,
)
from services.support_service import (
    get_all_tickets,
    get_ticket_stats,
    update_ticket_status,
    STATUS_LABELS,
    TICKET_TYPES,
    PRIORITY_LABELS,
)


# ── Data layer — cached 60s ───────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def _fetch_total_logins() -> int:
    try:
        r = supabase.table("auth_logs").select("id", count="exact").eq("action", "LOGIN").execute()
        return r.count or len(r.data or [])
    except Exception:
        return 0


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_top_products(limit: int = 10) -> list:
    try:
        r = supabase.table("trade_usage_logs").select("product").not_.is_("product", "null").execute()
        counts: dict = {}
        for row in r.data or []:
            p = (row.get("product") or "").strip()[:80]
            if p:
                counts[p] = counts.get(p, 0) + 1
        return sorted(
            [{"product": k, "searches": v} for k, v in counts.items()],
            key=lambda x: x["searches"], reverse=True,
        )[:limit]
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_top_hs_codes(limit: int = 10) -> list:
    try:
        r = supabase.table("trade_usage_logs").select("hs_code").not_.is_("hs_code", "null").execute()
        counts: dict = {}
        for row in r.data or []:
            hs = (row.get("hs_code") or "").strip()
            if hs and hs.isdigit():
                counts[hs] = counts.get(hs, 0) + 1
        return sorted(
            [{"hs_code": k, "occurrences": v} for k, v in counts.items()],
            key=lambda x: x["occurrences"], reverse=True,
        )[:limit]
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_daily_trend(days: int = 14) -> list:
    try:
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        r = supabase.table("trade_usage_logs").select("timestamp").gte("timestamp", since).execute()
        counts: dict = {}
        for row in r.data or []:
            day = (row.get("timestamp") or "")[:10]
            if day:
                counts[day] = counts.get(day, 0) + 1
        result = []
        for i in range(days):
            day = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
            result.append({"Date": day, "Queries": counts.get(day, 0)})
        return result
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _fetch_user_activity() -> list:
    """
    Build user activity table.

    Fix v3.1: PRO user last_active now checks BOTH trade_usage_logs AND
    auth_logs so users who have logged in but not run a query still show
    activity. Uses len(data) as fallback when .count returns None (RLS).
    """
    try:
        profiles = supabase.table("profiles").select("user_id,email,role").execute()
        rows = []
        for p in profiles.data or []:
            uid = p.get("user_id") or p.get("id")
            if not uid:
                continue

            # ── Query count (fallback to len when .count is None) ──
            try:
                q = supabase.table("trade_usage_logs").select("id", count="exact").eq("user_id", uid).execute()
                query_count = q.count if q.count is not None else len(q.data or [])
            except Exception:
                query_count = 0

            # ── Login count ──────────────────────────────────────
            try:
                l = supabase.table("auth_logs").select("id", count="exact").eq("user_id", uid).eq("action", "LOGIN").execute()
                login_count = l.count if l.count is not None else len(l.data or [])
            except Exception:
                login_count = 0

            # ── Last active: check BOTH trade_usage_logs and auth_logs ──
            # This ensures PRO/paid users who logged in but ran no query
            # still show "Last Active" rather than "Never".
            last_query_ts = ""
            last_login_ts = ""

            try:
                lq = (
                    supabase.table("trade_usage_logs")
                    .select("timestamp")
                    .eq("user_id", uid)
                    .order("timestamp", desc=True)
                    .limit(1)
                    .execute()
                )
                last_query_ts = (lq.data[0].get("timestamp") or "")[:10] if lq.data else ""
            except Exception:
                pass

            try:
                ll = (
                    supabase.table("auth_logs")
                    .select("created_at")
                    .eq("user_id", uid)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if ll.data:
                    ts_raw = ll.data[0].get("created_at") or ll.data[0].get("timestamp") or ""
                    last_login_ts = ts_raw[:10]
            except Exception:
                pass

            # Pick whichever is more recent
            if last_query_ts and last_login_ts:
                last_active = max(last_query_ts, last_login_ts)
            else:
                last_active = last_query_ts or last_login_ts or "Never"

            rows.append({
                "Email":       p.get("email", ""),
                "Role":        (p.get("role") or "free").upper(),
                "Queries":     query_count,
                "Logins":      login_count,
                "Last Active": last_active,
                "_uid":        uid,
            })

        return sorted(rows, key=lambda x: x["Queries"], reverse=True)

    except Exception as e:
        return []


# ── Chart helper ─────────────────────────────────────────────────

_DARK_BG = "rgba(0,0,0,0)"
_GRID    = "#2d3748"

def _chart_layout(fig, height=320):
    fig.update_layout(
        height=height, margin=dict(t=24, b=12, l=0, r=0),
        paper_bgcolor=_DARK_BG, plot_bgcolor=_DARK_BG,
        font=dict(color="#c9d1d9", size=11),
        xaxis=dict(showgrid=False, color="#c9d1d9"),
        yaxis=dict(showgrid=True, gridcolor=_GRID, color="#c9d1d9"),
    )
    return fig


# ── Main render ──────────────────────────────────────────────────

def render_admin_dashboard() -> None:
    """Entry point — called from app.py. Admin guard is in app.py main()."""

    st.markdown("""
    <div style="background:linear-gradient(135deg,#1a3a5c 0%,#1a6fa8 100%);
                border-radius:12px;padding:20px 26px;margin-bottom:18px;">
      <h2 style="color:#ffffff;margin:0;font-size:1.35rem;font-weight:700;">🛡️ Admin Dashboard</h2>
      <p style="color:#a8d4f5;margin:5px 0 0;font-size:0.82rem;">
        Platform-wide metrics · Live Supabase data · Cache refreshes every 60 s
      </p>
    </div>
    """, unsafe_allow_html=True)

    _, refresh_col = st.columns([6, 1])
    with refresh_col:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # ── KPI row ──────────────────────────────────────────────────
    st.markdown("#### 📊 Platform Overview")
    stats = get_platform_stats()
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("👥 Total Users",   stats.get("total_users", 0))
    k2.metric("🔍 Total Queries", stats.get("total_queries", 0))
    k3.metric("📅 Queries Today", stats.get("queries_today", 0))
    k4.metric("🔑 Total Logins",  _fetch_total_logins())
    by_mode = stats.get("by_mode") or {}
    k5.metric("🏆 Top Mode", max(by_mode, key=by_mode.get) if by_mode else "—")

    if stats.get("_errors"):
        with st.expander("⚠️ Data errors — click to diagnose", expanded=True):
            for err in stats["_errors"]:
                st.error(f"❌ {err}")
            st.code("""-- Run in Supabase SQL Editor to fix RLS blocking service_role:
DROP POLICY IF EXISTS "Service role full access to usage" ON trade_usage_logs;
CREATE POLICY "Service role full access to usage" ON trade_usage_logs FOR ALL USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "Service role full access to auth_logs" ON auth_logs;
CREATE POLICY "Service role full access to auth_logs" ON auth_logs FOR ALL USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "Service role full access to profiles" ON profiles;
CREATE POLICY "Service role full access to profiles" ON profiles FOR ALL USING (true) WITH CHECK (true);
""", language="sql")

    st.markdown("---")

    # ── Queries by mode + daily trend ───────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Queries by Mode")
        if by_mode:
            fig = px.pie(values=list(by_mode.values()), names=list(by_mode.keys()),
                         color_discrete_sequence=["#1A6FA8","#27AE60","#E67E22","#8E44AD"], hole=0.42)
            fig.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
            fig.update_layout(height=300, margin=dict(t=10,b=10,l=0,r=0), showlegend=True,
                              legend=dict(orientation="h", y=-0.12, font=dict(color="#c9d1d9")),
                              paper_bgcolor=_DARK_BG)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No query data yet.")

    with col2:
        st.markdown("##### Daily Query Volume — Last 14 Days")
        trend = _fetch_daily_trend(14)
        if trend:
            df_t = pd.DataFrame(trend)
            fig2 = px.area(df_t, x="Date", y="Queries", color_discrete_sequence=["#1A6FA8"])
            fig2.update_traces(fill="tozeroy", line=dict(color="#1A6FA8", width=2),
                               fillcolor="rgba(26,111,168,0.25)")
            _chart_layout(fig2, height=300)
            fig2.update_xaxes(tickangle=-30, nticks=7)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No trend data yet.")

    st.markdown("---")

    # ── Top products + top HS codes ──────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### 🔎 Most Searched Products")
        products = _fetch_top_products(10)
        if products:
            df_p = pd.DataFrame(products)
            fig3 = px.bar(df_p, x="searches", y="product", orientation="h",
                          color="searches", color_continuous_scale="Blues",
                          labels={"searches": "Searches", "product": "Product"})
            fig3.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
            _chart_layout(fig3, height=340)
            st.plotly_chart(fig3, use_container_width=True)
            with st.expander("📋 Full Product Table"):
                st.dataframe(df_p, use_container_width=True, hide_index=True)
        else:
            st.info("No product data yet.")

    with col2:
        st.markdown("##### 📦 Top HS Codes Returned")
        hs_data = _fetch_top_hs_codes(10)
        if hs_data:
            df_hs = pd.DataFrame(hs_data)
            fig4 = px.bar(df_hs, x="occurrences", y="hs_code", orientation="h",
                          color="occurrences", color_continuous_scale="Greens",
                          labels={"occurrences": "Count", "hs_code": "HS Code"})
            fig4.update_layout(yaxis={"categoryorder": "total ascending"}, coloraxis_showscale=False)
            _chart_layout(fig4, height=340)
            st.plotly_chart(fig4, use_container_width=True)
            with st.expander("📋 Full HS Code Table"):
                st.dataframe(df_hs, use_container_width=True, hide_index=True)
        else:
            st.info("No HS code data yet.")

    st.markdown("---")

    # ── User activity table ──────────────────────────────────────
    st.markdown("#### 👥 User Activity")
    st.caption("Last Active = most recent of: last trade query OR last login (whichever is newer)")
    activity = _fetch_user_activity()
    if activity:
        df_act = pd.DataFrame(activity)[["Email", "Role", "Queries", "Logins", "Last Active"]]
        # Colour-code the Role column
        st.dataframe(df_act, use_container_width=True, hide_index=True)

        # Per-role breakdown
        role_counts = {}
        for row in activity:
            r = row.get("Role", "FREE")
            role_counts[r] = role_counts.get(r, 0) + 1
        if role_counts:
            st.markdown("**Users by Role:**  " + "  ·  ".join(
                f"`{r}` = **{c}**" for r, c in sorted(role_counts.items())))
    else:
        st.info("No user data yet. Check RLS policies in Supabase if you expect users.")

    st.markdown("---")

    # ── Role management ──────────────────────────────────────────
    st.markdown("#### 🔧 User Role Management")
    users = get_all_users()
    if users:
        role_options = ["free", "user", "analyst", "pro", "admin"]
        emails = [u.get("email", "") for u in users]
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            sel_email = st.selectbox("Select User", emails, key="adm_sel_email")
        with c2:
            curr = next((u.get("role", "free") for u in users if u.get("email") == sel_email), "free")
            new_role = st.selectbox("New Role", role_options,
                                    index=role_options.index(curr) if curr in role_options else 0,
                                    key="adm_new_role")
        with c3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✅ Apply Role", type="primary", use_container_width=True, key="adm_apply"):
                uid = next((u.get("user_id") or u.get("id") for u in users if u.get("email") == sel_email), None)
                if uid:
                    res = update_user_role(uid, new_role)
                    if res["status"] == "success":
                        st.success(f"✅ **{sel_email}** → **{new_role.upper()}**")
                        st.cache_data.clear()
                    else:
                        st.error(f"❌ {res['message']}")
        st.caption("Role daily query limits — Free: 15 · User: 60 · Analyst: 200 · Pro: 600 · Admin: Unlimited")
    else:
        st.info("No users found.")

    st.markdown("---")

    # ── Recent queries ───────────────────────────────────────────
    st.markdown("#### 📋 Recent Queries — All Users")
    limit_n = st.slider("Show last N queries", 10, 200, 50, step=10, key="adm_q_limit")
    queries, _q_err = get_all_queries(limit=limit_n)
    if _q_err:
        st.error(f"❌ Cannot read trade_usage_logs: {_q_err}")
        st.code("-- Fix: run the RLS patch SQL shown in the Data Errors section above", language="sql")
    elif queries:
        df_q = pd.DataFrame([{
            "Time":    (q.get("timestamp") or "")[:19].replace("T", " "),
            "Email":   q.get("email", ""),
            "Role":    q.get("role", "").upper() if q.get("role") else "—",
            "Mode":    q.get("mode", ""),
            "Product": (q.get("product") or "")[:72] + ("…" if len(q.get("product") or "") > 72 else ""),
        } for q in queries])
        st.dataframe(df_q, use_container_width=True, hide_index=True)
    else:
        st.info("No queries yet.")

    st.markdown("---")

    # ── Support tickets ──────────────────────────────────────────
    st.markdown("#### 🎫 Support Tickets")
    tstats = get_ticket_stats()
    if tstats.get("_error"):
        st.warning(f"⚠️ Support tickets table not found: `{tstats['_error']}`\nRun `sql_schema_v3.sql` in Supabase SQL Editor.")
    else:
        tk1, tk2, tk3, tk4, tk5 = st.columns(5)
        tk1.metric("🎫 Total",     tstats.get("total", 0))
        tk2.metric("🟡 Open",      tstats.get("open", 0))
        tk3.metric("🔵 In Review", tstats.get("in_review", 0))
        tk4.metric("🟢 Resolved",  tstats.get("resolved", 0))
        tk5.metric("⚫ Closed",    tstats.get("closed", 0))

    filt_col1, filt_col2 = st.columns(2)
    with filt_col1:
        _filter_status = st.selectbox("Filter by Status",
            ["All", "open", "in_review", "resolved", "closed"], key="adm_ticket_status_filter",
            format_func=lambda x: "All Statuses" if x == "All" else STATUS_LABELS.get(x, x))
    with filt_col2:
        _filter_type = st.selectbox("Filter by Type",
            ["All"] + list(TICKET_TYPES.keys()), key="adm_ticket_type_filter",
            format_func=lambda x: "All Types" if x == "All" else TICKET_TYPES[x])

    if not tstats.get("_error") and tstats.get("by_type"):
        type_data = [{"Type": TICKET_TYPES.get(k, k), "Count": v} for k, v in tstats["by_type"].items()]
        fig_t = px.bar(pd.DataFrame(type_data), x="Type", y="Count", color="Type",
                       color_discrete_sequence=["#1A6FA8","#E67E22","#27AE60"], title="Tickets by Category")
        fig_t.update_layout(height=240, showlegend=False, margin=dict(t=32,b=8,l=0,r=0),
                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#c9d1d9"))
        st.plotly_chart(fig_t, use_container_width=True)

    _s_arg = None if _filter_status == "All" else _filter_status
    _t_arg = None if _filter_type   == "All" else _filter_type
    all_tickets, _tkt_err = get_all_tickets(status=_s_arg, ticket_type=_t_arg, limit=100)

    if _tkt_err:
        st.error(f"❌ Could not load tickets: {_tkt_err}")
    elif all_tickets:
        for tkt in all_tickets:
            _tid    = tkt.get("id")
            _status = tkt.get("status", "open")
            _prio   = tkt.get("priority", "medium")
            _type   = TICKET_TYPES.get(tkt.get("ticket_type",""), tkt.get("ticket_type",""))
            _subj   = tkt.get("subject", "")
            _email  = tkt.get("email", "")
            _ts     = (tkt.get("created_at") or "")[:10]
            _note   = tkt.get("admin_note", "") or ""
            with st.expander(
                f"{STATUS_LABELS.get(_status,_status)} · {PRIORITY_LABELS.get(_prio,_prio)} · **{_subj[:60]}** — {_email} ({_ts})",
                expanded=False,
            ):
                col_info, col_action = st.columns([3, 1])
                with col_info:
                    st.markdown(f"**Type:** {_type}")
                    st.markdown("<b>Description:</b>", unsafe_allow_html=True)
                    st.markdown(
                        f"<div style='background:#0d1117;border:1px solid #30363d;border-radius:8px;"
                        f"padding:12px;font-size:0.85rem;color:#c9d1d9;'>{tkt.get('description','')}</div>",
                        unsafe_allow_html=True)
                    if _note:
                        st.markdown(
                            f"<div style='background:#1a2a1a;border:1px solid #27ae60;border-radius:8px;"
                            f"padding:10px;margin-top:8px;font-size:0.82rem;color:#48bb78;'>"
                            f"📝 <strong>Admin Note:</strong> {_note}</div>", unsafe_allow_html=True)
                with col_action:
                    st.markdown("**Update Status**")
                    _new_status = st.selectbox("Status", list(STATUS_LABELS.keys()),
                        index=list(STATUS_LABELS.keys()).index(_status) if _status in STATUS_LABELS else 0,
                        key=f"tkt_status_{_tid}", format_func=lambda x: STATUS_LABELS[x])
                    _admin_note_input = st.text_area("Add Note", value="", height=80,
                        placeholder="Optional note to user…", key=f"tkt_note_{_tid}")
                    if st.button("✅ Save", key=f"tkt_save_{_tid}", use_container_width=True, type="primary"):
                        res = update_ticket_status(_tid, _new_status, _admin_note_input.strip())
                        if res["status"] == "success":
                            st.success("Updated!")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(res["message"])
    else:
        st.info("No tickets found matching the current filters.")

    st.markdown("---")

    # ── Revenue analytics placeholder ────────────────────────────
    st.markdown("#### 💰 Revenue Analytics")
    all_u = get_all_users() or []
    role_breakdown = {}
    for u in all_u:
        r = (u.get("role") or "free").lower()
        role_breakdown[r] = role_breakdown.get(r, 0) + 1
    breakdown_str = "  ·  ".join(
        f"{r.upper()}: **{c}**" for r, c in sorted(role_breakdown.items()))
    st.markdown(f"""
    <div style="background:#161b22;border:1px dashed #30363d;border-radius:12px;padding:32px;text-align:center;">
      <div style="font-size:2.5rem;margin-bottom:12px;">📊</div>
      <h3 style="color:#e2e8f0;margin:0 0 8px;font-size:1.1rem;">Coming Soon — Razorpay Integration</h3>
      <p style="color:#8b949e;font-size:0.88rem;margin:0 0 12px;">{breakdown_str}</p>
      <p style="color:#484f58;font-size:0.75rem;margin-top:16px;">
        Integrate Razorpay to unlock MRR tracking, plan conversions, and user lifetime value
      </p>
    </div>
    """, unsafe_allow_html=True)