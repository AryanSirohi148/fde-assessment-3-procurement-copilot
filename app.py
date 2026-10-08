"""
Procurement Request Copilot — Executive Streamlit Dashboard
=============================================================
Interactive UI for evaluating, inspecting, and comparing procurement decisions
under Architecture A (Single-Agent Baseline) and Architecture B (Staged 2-Agent Pipeline).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import streamlit as st

from src.contracts import ProcurementDecision
from src.solution import handle_request

# Page configuration
st.set_page_config(
    page_title="AI Procurement Copilot",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent
REQUESTS = json.loads((ROOT / "data" / "requests.json").read_text(encoding="utf-8"))
BY_ID = {r["request_id"]: r for r in REQUESTS}

# Custom CSS for executive aesthetics
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 12px 16px;
        border-left: 4px solid #1f77b4;
        margin-bottom: 10px;
    }
    .risk-badge {
        display: inline-block;
        padding: 4px 10px;
        margin: 2px 4px;
        border-radius: 12px;
        font-size: 0.82rem;
        font-weight: 600;
    }
    .risk-high { background-color: #ffebe9; color: #cf222e; border: 1px solid #ff8182; }
    .risk-med { background-color: #fff8c5; color: #9a6700; border: 1px solid #d4a72c; }
    .risk-low { background-color: #dafbe1; color: #1a7f37; border: 1px solid #4ac26b; }
    .approval-pill {
        display: inline-block;
        background-color: #e8f0fe;
        color: #1a73e8;
        padding: 6px 12px;
        margin: 4px 6px 4px 0;
        border-radius: 16px;
        font-weight: 600;
        border: 1px solid #aecbfa;
    }
    .recommendation-box {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        padding: 18px 22px;
        border-radius: 10px;
        margin-bottom: 16px;
    }
    .recommendation-box h4 {
        color: #e0e7ff !important;
        margin-bottom: 6px;
    }
    .next-step-box {
        background-color: #f0fdf4;
        border: 1px solid #bbf7d0;
        color: #166534;
        padding: 12px 16px;
        border-radius: 8px;
        margin-bottom: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# App Header
st.title("Enterprise Procurement Copilot")
st.caption(
    "Policy Reference: **2026.09 (Snapshot: 2026-09-30)** &nbsp;|&nbsp; "
    "Advisory Mode: **Human Authority Reserved (§11)** &nbsp;|&nbsp; "
    "Deterministic Policy Enforcement"
)
st.divider()

# ──────────────────────────────────────────────
# Sidebar Controls
# ──────────────────────────────────────────────
st.sidebar.header("Configuration")

request_id = st.sidebar.selectbox(
    "Select Purchase Request",
    list(BY_ID.keys()),
    format_func=lambda rid: f"{rid}: {BY_ID[rid].get('product_name', 'Unknown')}",
)

arch_mode = st.sidebar.radio(
    "Evaluation Architecture",
    ["single", "staged", "compare"],
    format_func=lambda m: {
        "single": "Architecture A: Single-Agent Baseline",
        "staged": "Architecture B: Staged (2-Agent Pipeline)",
        "compare": "Side-by-Side Comparison",
    }[m],
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    **Architecture Overview:**
    - **Single-Agent**: One LLM coordinator executes all deterministic tools and writes synthesis.
    - **Staged (2-Agent)**: 
      - *Stage 1*: Procurement Analyst Agent (evidence gathering)
      - *Stage 2*: Risk Reviewer Agent (policy audit)
    - **Deterministic Engine**: Dollar tiers, security triggers, and injection defenses are guaranteed by code.
    """
)

req = BY_ID[request_id]

# ──────────────────────────────────────────────
# Main Layout: Request Details & Decision
# ──────────────────────────────────────────────
left_col, right_col = st.columns([1.1, 1.4], gap="large")

with left_col:
    st.subheader("Request Details")

    # Header metrics
    cost_val = req.get("annual_cost_usd")
    cost_disp = f"${cost_val:,.2f}" if cost_val is not None else "Unknown / Not specified"
    users_val = req.get("user_count")
    users_disp = f"{users_val} users" if users_val is not None else "Unknown"

    m1, m2 = st.columns(2)
    m1.metric("Annual Cost", cost_disp)
    m2.metric("License Count", users_disp)

    # Details table
    st.markdown(
        f"""
        | Field | Value |
        |---|---|
        | **Request ID** | `{req.get('request_id')}` |
        | **Product Name** | **{req.get('product_name')}** |
        | **Vendor Name** | {req.get('vendor_name')} |
        | **Category** | {req.get('category')} |
        | **Requester ID** | `{req.get('requester_id')}` |
        | **Data Access Level** | `{req.get('data_access_level')}` |
        | **Integrations** | {', '.join(req.get('requested_integrations') or ['None'])} |
        | **Urgency** | `{req.get('urgency')}` |
        """
    )

    st.markdown("**Business Justification:**")
    st.info(f"“{req.get('business_justification')}”")

    with st.expander("View Raw Request JSON"):
        st.json(req)


def display_decision_panel(decision: ProcurementDecision, label: str = ""):
    if label:
        st.subheader(f"Copilot Output ({label})")
    else:
        st.subheader("Recommendation & Policy Analysis")

    # 1. Recommendation Banner
    st.markdown(
        f"""
        <div class="recommendation-box">
            <h4 style="margin:0 0 6px 0;">Recommendation</h4>
            <div style="font-size:1.05rem; line-height:1.4;">{decision.recommendation}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. Next Step Box
    st.markdown(
        f"""
        <div class="next-step-box">
            <strong>Next Action:</strong> {decision.next_step}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 3. Missing Information Alert
    if decision.missing_information:
        st.error(
            f"**Incomplete Request (§1)**: The following mandatory information is missing before approval can proceed: "
            f"**{', '.join(decision.missing_information)}**"
        )

    # 4. Required Approvals Pipeline
    st.markdown("##### Required Approvals")
    if decision.required_approvals:
        pills_html = "".join([f'<span class="approval-pill">✓ {app}</span>' for app in decision.required_approvals])
        st.markdown(pills_html, unsafe_allow_html=True)
    else:
        st.write("None required.")

    st.write("")

    # 5. Risk Flags
    st.markdown("##### Policy Risk Flags")
    if decision.risk_flags:
        badges_html = ""
        for flag in decision.risk_flags:
            flag_lower = flag.lower()
            if any(k in flag_lower for k in ("prompt_injection", "insufficient", "unavailable", "expired")):
                cls = "risk-high"
            elif any(k in flag_lower for k in ("security", "privacy", "legal", "overlap")):
                cls = "risk-med"
            else:
                cls = "risk-low"
            badges_html += f'<span class="risk-badge {cls}">{flag}</span> '
        st.markdown(badges_html, unsafe_allow_html=True)
    else:
        st.success("No policy risk flags triggered.")

    st.write("")

    # 6. Telemetry Metrics
    if decision.telemetry:
        tel = decision.telemetry
        t1, t2, t3 = st.columns(3)
        t1.metric("LLM Invocations", tel.llm_calls)
        t2.metric("Tool Invocations", tel.tool_calls)
        t3.metric("Human Authority", "Enforced (§11)" if decision.human_review_required else "Autonomous")

    # 7. Audit Evidence Trail
    with st.expander(f"Audit Evidence Trail ({len(decision.evidence)} verified findings)"):
        for i, ev in enumerate(decision.evidence, 1):
            st.markdown(
                f"""
                **{i}. Source:** `{ev.source}` &nbsp;|&nbsp; **Reference:** `{ev.reference or 'N/A'}`  
                {ev.finding}
                ---
                """
            )


with right_col:
    if arch_mode == "compare":
        st.subheader("Side-by-Side Comparison")
        if st.button("Run Both Architectures", type="primary", use_container_width=True):
            with st.spinner("Executing Architecture A & Architecture B..."):
                t0 = time.perf_counter()
                dec_single = handle_request(request_id, architecture="single")
                lat_single = (time.perf_counter() - t0) * 1000

                t1 = time.perf_counter()
                dec_staged = handle_request(request_id, architecture="staged")
                lat_staged = (time.perf_counter() - t1) * 1000

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"### Architecture A (Single)\n**Latency:** `{lat_single:.1f} ms`")
                display_decision_panel(dec_single, "Single-Agent")
            with c2:
                st.markdown(f"### Architecture B (Staged)\n**Latency:** `{lat_staged:.1f} ms`")
                display_decision_panel(dec_staged, "Staged 2-Agent")
        else:
            st.info("Click **Run Both Architectures** to compare outputs and telemetry side-by-side.")

    else:
        arch_title = "Single-Agent Baseline" if arch_mode == "single" else "Staged 2-Agent Pipeline"
        if st.button(f"Analyze with {arch_title}", type="primary", use_container_width=True):
            with st.spinner(f"Analyzing {request_id} using {arch_title}..."):
                start_time = time.perf_counter()
                decision = handle_request(request_id, architecture=arch_mode)
                latency = (time.perf_counter() - start_time) * 1000

            display_decision_panel(decision)
            st.caption(f"Total Execution Latency: **{latency:.1f} ms**")
        else:
            st.info(f"Click the button above to run evaluation using **{arch_title}**.")

st.divider()
st.caption(
    "**Procurement Governance Rule**: Recommendations and evidence synthesis are advisory. "
    "All purchasing, budgetary approvals, and vendor sign-offs require human authorization per Section 11 of the procurement policy."
)
