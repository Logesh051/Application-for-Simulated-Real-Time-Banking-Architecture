"""
Friends Bank - A Simulated Digital Banking Environment.

Features:
- Clean light theme with deep teal accents and local font fallbacks
- Personalized fictional customers (Nila Varadhan, Rehan Thomas, Tara Dev)
- Interactive visual request pipeline showing agent collaboration and step highlights
- Gemini-powered plain-English explanations with deterministic local fallback
- Two-step transfer confirmation with cancellation safety and idempotency protection
- Six supported banking sample-use-case quick actions
"""

import html
import os
import uuid
from typing import Any, Dict, List, Optional

# Attempt loading environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import streamlit as st

from banking_api import get_api_instance
from supervisor import Supervisor


# Page configuration: Light theme only, wide layout
st.set_page_config(
    page_title="Friends Bank",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Custom CSS for distinctive Friends Bank Light Theme
st.markdown(
    """
    <style>
    /* -------------------------------------------------------------
       1. GLOBAL LIGHT STYLING & THEME ENFORCEMENT
       ------------------------------------------------------------- */
    :root {
        color-scheme: light !important;
    }
    
    html, body, .stApp {
        background-color: #f8fafc !important;
        font-family: Inter, "Segoe UI", -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: #0f172a !important;
    }

    /* Force all base text in app to dark legible slate */
    .stApp, .stApp p, .stApp span, .stApp label, .stApp div {
        color: #0f172a;
    }

    /* Transparent top header bar */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }

    /* Sidebar container & widgets */
    section[data-testid="stSidebar"] {
        background-color: #ffffff !important;
        border-right: 1px solid #e2e8f0 !important;
    }
    section[data-testid="stSidebar"] * {
        color: #0f172a;
    }

    /* -------------------------------------------------------------
       2. BRAND HEADER & CONTENT CARDS
       ------------------------------------------------------------- */
    .fb-header-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px 28px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
    }
    .fb-brand-title {
        color: #0f766e;
        font-size: 28px;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .fb-brand-subtitle {
        color: #475569;
        font-size: 14px;
        font-style: italic;
        margin-top: 4px;
        margin-bottom: 8px;
    }
    .fb-demo-notice {
        display: inline-block;
        background: #f1f5f9;
        color: #475569;
        font-size: 12px;
        padding: 5px 12px;
        border-radius: 6px;
        border: 1px solid #e2e8f0;
    }

    .fb-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
    }
    .fb-card-title {
        color: #0f766e;
        font-size: 18px;
        font-weight: 600;
        margin-top: 0;
        margin-bottom: 10px;
    }
    .fb-card-text {
        color: #334155;
        font-size: 14px;
        line-height: 1.6;
    }

    /* -------------------------------------------------------------
       3. BUTTON STYLES (Light or teal backgrounds, dark/white text)
       ------------------------------------------------------------- */
    /* Secondary & default buttons (Sample scenarios, Cancel, Reset) */
    div[data-testid="stButton"] > button,
    div[data-testid="stFormSubmitButton"] > button,
    .stButton > button,
    .stFormSubmitButton > button {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        padding: 0.5rem 1rem !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05) !important;
        transition: all 0.15s ease-in-out !important;
    }

    div[data-testid="stButton"] > button *,
    div[data-testid="stFormSubmitButton"] > button *,
    .stButton > button *,
    .stFormSubmitButton > button * {
        color: inherit !important;
    }

    div[data-testid="stButton"] > button:hover,
    .stButton > button:hover {
        background-color: #f0fdfa !important;
        border-color: #0f766e !important;
        color: #0f766e !important;
    }
    div[data-testid="stButton"] > button:hover *,
    .stButton > button:hover * {
        color: #0f766e !important;
    }

    div[data-testid="stButton"] > button:active,
    .stButton > button:active {
        background-color: #ccfbf1 !important;
        border-color: #0f766e !important;
        color: #0f766e !important;
    }

    /* Primary buttons (Submit Request, Confirm Transfer) */
    div[data-testid="stButton"] > button[kind="primary"],
    div[data-testid="stButton"] > button[data-testid*="primary"],
    div[data-testid="stFormSubmitButton"] > button,
    .stFormSubmitButton > button {
        background-color: #0f766e !important;
        color: #ffffff !important;
        border: 1px solid #0f766e !important;
        font-weight: 600 !important;
        box-shadow: 0 1px 3px rgba(15, 118, 110, 0.25) !important;
    }

    div[data-testid="stButton"] > button[kind="primary"] *,
    div[data-testid="stButton"] > button[data-testid*="primary"] *,
    div[data-testid="stFormSubmitButton"] > button *,
    .stFormSubmitButton > button * {
        color: #ffffff !important;
    }

    div[data-testid="stButton"] > button[kind="primary"]:hover,
    div[data-testid="stButton"] > button[data-testid*="primary"]:hover,
    div[data-testid="stFormSubmitButton"] > button:hover,
    .stFormSubmitButton > button:hover {
        background-color: #115e59 !important;
        border-color: #115e59 !important;
        color: #ffffff !important;
    }

    /* -------------------------------------------------------------
       4. INPUT & SELECT-BOX STYLING
       ------------------------------------------------------------- */
    /* Input box container */
    div[data-testid="stTextInput"] > div > div,
    div[data-baseweb="input"],
    div[data-baseweb="base-input"] {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        color: #0f172a !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
    }
    div[data-baseweb="input"]:focus-within {
        border-color: #0f766e !important;
        box-shadow: 0 0 0 1px #0f766e !important;
    }

    /* Input text & placeholder */
    div[data-testid="stTextInput"] input,
    div[data-baseweb="input"] input {
        background-color: #ffffff !important;
        color: #0f172a !important;
        font-size: 14px !important;
        caret-color: #0f766e !important;
    }
    div[data-testid="stTextInput"] input::placeholder,
    div[data-baseweb="input"] input::placeholder {
        color: #64748b !important;
        opacity: 1 !important;
    }

    /* Selectbox container */
    div[data-testid="stSelectbox"] > div > div,
    div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        color: #0f172a !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
    }
    div[data-baseweb="select"] * {
        color: #0f172a !important;
    }
    div[data-baseweb="select"] svg {
        fill: #475569 !important;
    }

    /* Selectbox dropdown popup */
    div[data-baseweb="popover"],
    div[data-baseweb="menu"],
    ul[role="listbox"],
    li[role="option"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
    }
    li[role="option"] {
        background-color: #ffffff !important;
        color: #0f172a !important;
        font-size: 14px !important;
    }
    li[role="option"]:hover,
    li[role="option"][aria-selected="true"] {
        background-color: #f0fdfa !important;
        color: #0f766e !important;
    }
    li[role="option"] * {
        color: inherit !important;
    }

    /* -------------------------------------------------------------
       5. ACCESSIBLE RESULT & WARNING CARDS (Dark text, pale backgrounds)
       ------------------------------------------------------------- */
    div[data-testid="stAlert"],
    div[data-testid="stAlertContainer"] {
        border-radius: 10px !important;
        padding: 16px 20px !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
    }
    div[data-testid="stAlert"] *,
    div[data-testid="stAlertContainer"] * {
        color: #0f172a !important;
    }
    div[data-testid="stAlert"] h3,
    div[data-testid="stAlertContainer"] h3 {
        color: #0f172a !important;
        font-size: 16px !important;
        font-weight: 700 !important;
        margin-top: 0 !important;
        margin-bottom: 6px !important;
    }
    div[data-testid="stAlert"] p,
    div[data-testid="stAlertContainer"] p {
        color: #1e293b !important;
        font-size: 14px !important;
        line-height: 1.5 !important;
        margin: 0 !important;
    }

    /* Success Card (Completed successfully, Approved, Eligible) */
    div[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]),
    div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]),
    div:has(> [data-testid="stAlertContentSuccess"]),
    div[data-testid="stAlertContentSuccess"] {
        background-color: #ecfdf5 !important;
        border: 1px solid #6ee7b7 !important;
    }

    /* Warning / Review Required Card */
    div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]),
    div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]),
    div:has(> [data-testid="stAlertContentWarning"]),
    div[data-testid="stAlertContentWarning"] {
        background-color: #fffbeb !important;
        border: 1px solid #fcd34d !important;
    }

    /* Error / Blocked / Stopped Card */
    div[data-testid="stAlert"]:has([data-testid="stAlertContentError"]),
    div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]),
    div:has(> [data-testid="stAlertContentError"]),
    div[data-testid="stAlertContentError"] {
        background-color: #fef2f2 !important;
        border: 1px solid #fca5a5 !important;
    }

    /* Info / Notice / Needs Input Card */
    div[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]),
    div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]),
    div:has(> [data-testid="stAlertContentInfo"]),
    div[data-testid="stAlertContentInfo"] {
        background-color: #f0fdfa !important;
        border: 1px solid #99f6e4 !important;
    }

    /* Metrics & Expanders */
    div[data-testid="stMetric"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.03) !important;
    }
    div[data-testid="stMetricLabel"] * {
        color: #64748b !important;
        font-size: 13px !important;
    }
    div[data-testid="stMetricValue"] * {
        color: #0f766e !important;
        font-weight: 700 !important;
    }

    div[data-testid="stExpander"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
    }
    div[data-testid="stExpander"] details summary * {
        color: #0f766e !important;
        font-weight: 600 !important;
    }

    /* -------------------------------------------------------------
       6. VISUAL REQUEST PIPELINE
       ------------------------------------------------------------- */
    .pipeline-container {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px;
        margin: 18px 0;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }
    .pipeline-title {
        font-size: 14px;
        font-weight: 600;
        color: #0f766e;
        margin-bottom: 14px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .pipeline-track {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
        position: relative;
    }
    .pipeline-step {
        flex: 1;
        min-width: 140px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px 14px;
        text-align: center;
    }
    .pipeline-step.step-active {
        border-color: #0f766e;
        background: #f0fdfa;
    }
    .pipeline-step.step-completed {
        border-color: #0d9488;
        background: #f0fdfa;
    }
    .pipeline-step.step-skipped {
        border-color: #f1f5f9;
        background: #f8fafc;
        opacity: 0.65;
    }
    .step-icon {
        font-size: 20px;
        margin-bottom: 4px;
    }
    .step-title {
        font-size: 13px;
        font-weight: 600;
        color: #0f172a;
    }
    .step-status {
        font-size: 11px;
        color: #0f766e;
        font-weight: 500;
        margin-top: 4px;
    }
    .step-status.status-skipped {
        color: #94a3b8;
        font-style: italic;
    }

    @keyframes flowDotPulse {
        0% { transform: scale(0.9); opacity: 0.6; }
        50% { transform: scale(1.2); opacity: 1; }
        100% { transform: scale(0.9); opacity: 0.6; }
    }
    .pipeline-pulse-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        background: #0f766e;
        border-radius: 50%;
        animation: flowDotPulse 1.8s infinite ease-in-out;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# Initialize session state
if "supervisor" not in st.session_state:
    st.session_state.supervisor = Supervisor(banking_api=get_api_instance())

if "history" not in st.session_state:
    st.session_state.history = []

if "current_response" not in st.session_state:
    st.session_state.current_response = None

if "pending_transfer" not in st.session_state:
    st.session_state.pending_transfer = None


def reset_demo_ledger() -> None:
    """Resets in-memory banking ledger and clears session history."""
    st.session_state.supervisor.banking_api.reset()
    st.session_state.history = []
    st.session_state.current_response = None
    st.session_state.pending_transfer = None
    st.toast("Friends Bank demo ledger reset to initial values.", icon="🔄")


# ==============================================================================
# SIDEBAR: Account Selector & System Status
# ==============================================================================
with st.sidebar:
    st.markdown("### 🏦 Friends Bank")
    st.caption("A simulated banking environment")
    st.divider()

    api = st.session_state.supervisor.banking_api
    c1001 = api.get_customer_profile("C1001")["profile"]
    c1002 = api.get_customer_profile("C1002")["profile"]
    c1003 = api.get_customer_profile("C1003")["profile"]

    customer_display_options = {
        "C1001": f"C1001 — {c1001['name']}",
        "C1002": f"C1002 — {c1002['name']} (Restricted)",
        "C1003": f"C1003 — {c1003['name']}",
    }

    selected_account_id = st.selectbox(
        "Active Customer Account:",
        options=list(customer_display_options.keys()),
        format_func=lambda x: customer_display_options[x],
        help="Select customer account context for queries and transfers.",
    )

    st.divider()

    # Model / Engine Status
    gemini_key = os.environ.get("GEMINI_API_KEY")
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
    if gemini_key:
        st.success(f"🤖 Gemini: Connected ({gemini_model})")
    else:
        st.info("⚡ Local Engine: Active (Deterministic Fallback)")

    st.button("🔄 Reset Demo Ledger", on_click=reset_demo_ledger, use_container_width=True)


# ==============================================================================
# 1. HEADER SECTION
# ==============================================================================
st.markdown(
    """
    <div class="fb-header-box">
        <div class="fb-brand-title">Friends Bank</div>
        <div class="fb-brand-subtitle">A simulated banking environment</div>
        <div class="fb-demo-notice">Demo environment — fictional accounts and simulated money. No real transactions.</div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# 2. HOW FRIENDS BANK WORKS
# ==============================================================================
st.markdown(
    """
    <div class="fb-card">
        <div class="fb-card-title">How Friends Bank works</div>
        <div class="fb-card-text">
            When you ask a banking question, a coordinator understands your request and sends it to the relevant specialist agents.
            The <b>Banking Agent</b> handles account information and transfer requests.
            The <b>Risk Agent</b> checks account restrictions and transfer risk.
            The <b>Credit Agent</b> evaluates loan eligibility.
            <b>Gemini</b> helps understand your request and explain the verified result in simple language.
            <i>(Note: Only the specialists required for your specific request are invoked.)</i>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ==============================================================================
# 3. CHAT WITH AGENT
# ==============================================================================
st.markdown("### Chat with Agent")

active_profile = api.get_customer_profile(selected_account_id)["profile"]
cust_name = active_profile["name"]
cust_bal = active_profile["balance"]
is_restricted = active_profile["is_blocklisted"]

# Account overview bar
acc_col1, acc_col2 = st.columns([2, 1])
with acc_col1:
    st.markdown(f"**Customer:** {cust_name} &nbsp;|&nbsp; **Account:** `{selected_account_id}`")
    if is_restricted:
        st.warning("⚠️ Restricted Account: Transfers and loans are on hold for security screening.")
    else:
        st.caption("Account Status: Active & In Good Standing")

with acc_col2:
    st.metric(
        label="Available Demo Balance",
        value=f"₹{cust_bal:,.2f}",
    )


# Six Sample Use-Case Buttons
st.markdown("#### Sample Banking Scenarios")
sc_col1, sc_col2, sc_col3 = st.columns(3)
sc_col4, sc_col5, sc_col6 = st.columns(3)

sample_prompt: Optional[str] = None
sample_preparsed: Optional[Dict[str, Any]] = None

# Scenario 1: Check balance for C1001
if sc_col1.button("💰 Balance C1001", use_container_width=True, help="Check balance for Nila Varadhan (C1001)"):
    sample_prompt = "Check balance for C1001"
    sample_preparsed = {"intent": "BALANCE", "account_id": "C1001"}

# Scenario 2: View recent transactions for C1001
if sc_col2.button("📜 Transactions C1001", use_container_width=True, help="View recent transactions for C1001"):
    sample_prompt = "View recent transactions for C1001"
    sample_preparsed = {"intent": "STATEMENT", "account_id": "C1001"}

# Scenario 3: Transfer ₹12,000 from C1001 to C1003 (Allowed)
if sc_col3.button("💸 Transfer ₹12,000", use_container_width=True, help="Transfer ₹12,000 from C1001 to C1003"):
    sample_prompt = "Transfer ₹12,000 from C1001 to C1003"
    sample_preparsed = {
        "intent": "TRANSFER",
        "account_id": "C1001",
        "recipient_id": "C1003",
        "amount": 12000.0,
    }

# Scenario 4: Try a ₹65,000 transfer from C1001 to C1003 (High-Value Review)
if sc_col4.button("⚠️ Transfer ₹65,000 (Review)", use_container_width=True, help="High-value transfer > ₹50,000 triggers review"):
    sample_prompt = "Transfer ₹65,000 from C1001 to C1003"
    sample_preparsed = {
        "intent": "TRANSFER",
        "account_id": "C1001",
        "recipient_id": "C1003",
        "amount": 65000.0,
    }

# Scenario 5: Check loan eligibility for C1001 (EMI ₹10,000)
if sc_col5.button("📋 Loan Check C1001", use_container_width=True, help="Loan eligibility check for C1001 with ₹10,000 EMI"):
    sample_prompt = "Check loan eligibility for C1001 with a proposed monthly EMI of ₹10,000"
    sample_preparsed = {
        "intent": "LOAN_ELIGIBILITY",
        "account_id": "C1001",
        "proposed_emi": 10000.0,
    }

# Scenario 6: Check loan eligibility for restricted account C1002
if sc_col6.button("⛔ Loan Check C1002", use_container_width=True, help="Loan eligibility check for restricted account C1002"):
    sample_prompt = "Check loan eligibility for C1002 with a proposed monthly EMI of ₹5,000"
    sample_preparsed = {
        "intent": "LOAN_ELIGIBILITY",
        "account_id": "C1002",
        "proposed_emi": 5000.0,
    }


# Chat input form
with st.form(key="friends_bank_chat_form", clear_on_submit=False):
    chat_input = st.text_input(
        "Ask your banking question:",
        value=sample_prompt if sample_prompt else "",
        placeholder="e.g., What's my balance?",
        label_visibility="collapsed",
    )
    submit_chat = st.form_submit_button("Submit Request", type="primary", use_container_width=True)


# Determine active prompt and whether preparsed parameters are available
active_prompt: Optional[str] = None
active_preparsed: Optional[Dict[str, Any]] = None

if sample_prompt:
    active_prompt = sample_prompt
    active_preparsed = sample_preparsed
elif submit_chat and chat_input.strip():
    active_prompt = chat_input.strip()


# ==============================================================================
# 4. REQUEST PROCESSING & TRANSFER CONFIRMATION
# ==============================================================================
if active_prompt:
    # Determine intent (either from sample button or via intent parser)
    if active_preparsed and active_preparsed.get("intent") == "TRANSFER":
        target_sender = active_preparsed.get("account_id") or selected_account_id
        target_recipient = active_preparsed.get("recipient_id")
        target_amount = active_preparsed.get("amount")
        is_transfer = True
    else:
        # Parse intent dynamically
        parsed_fields, _, _ = st.session_state.supervisor.parse_intent(active_prompt)
        is_transfer = (parsed_fields.get("intent") == "TRANSFER")
        target_sender = parsed_fields.get("account_id") or selected_account_id
        target_recipient = parsed_fields.get("recipient_id")
        target_amount = parsed_fields.get("amount")

    if is_transfer:
        # If parameters are missing, route through normal supervisor pipeline (returns friendly NEEDS_INPUT)
        if not target_recipient or target_amount is None:
            txn_id = f"TXN_{uuid.uuid4().hex[:8].upper()}"
            result = st.session_state.supervisor.process_request(
                prompt=active_prompt,
                active_account_id=selected_account_id,
                transaction_id=txn_id,
            )
            st.session_state.current_response = {
                "prompt": active_prompt,
                "result": result,
                "txn_id": txn_id,
            }
            st.session_state.history.append(st.session_state.current_response)
            st.session_state.pending_transfer = None
        else:
            # Stage transfer for explicit user review and confirmation
            transfer_txn_id = f"TXN_{uuid.uuid4().hex[:8].upper()}"
            st.session_state.pending_transfer = {
                "sender_id": target_sender,
                "recipient_id": target_recipient,
                "amount": float(target_amount),
                "prompt": active_prompt,
                "txn_id": transfer_txn_id,
                "preparsed": active_preparsed,
            }
            st.session_state.current_response = None
    else:
        # Non-transfer requests execute immediately
        st.session_state.pending_transfer = None
        txn_id = f"TXN_{uuid.uuid4().hex[:8].upper()}"
        with st.spinner("Friends Bank Coordinator is processing your request..."):
            result = st.session_state.supervisor.process_request(
                prompt=active_prompt,
                active_account_id=selected_account_id,
                transaction_id=txn_id,
                preparsed_intent=active_preparsed,
            )
        st.session_state.current_response = {
            "prompt": active_prompt,
            "result": result,
            "txn_id": txn_id,
        }
        st.session_state.history.append(st.session_state.current_response)


# 5. Transfer Review and Confirmation Card (if transfer is pending)
if st.session_state.pending_transfer:
    pt = st.session_state.pending_transfer
    st.markdown("---")
    st.warning("### ⚠️ Review & Confirm Demo Transfer")
    st.markdown(
        f"**From Account:** `{pt['sender_id']}`  \n"
        f"**To Recipient:** `{pt['recipient_id']}`  \n"
        f"**Transfer Amount:** **₹{pt['amount']:,.2f}**  \n\n"
        f"*Note: Fictional demo transfer. No real money will be transferred.*"
    )

    conf_col1, conf_col2 = st.columns(2)
    if conf_col1.button("✅ Confirm demo transfer", type="primary", use_container_width=True):
        with st.spinner("Submitting transfer through specialist agent security checks..."):
            result = st.session_state.supervisor.process_request(
                prompt=pt["prompt"],
                active_account_id=pt["sender_id"],
                transaction_id=pt["txn_id"],
                preparsed_intent=pt.get("preparsed"),
            )
        st.session_state.current_response = {
            "prompt": pt["prompt"],
            "result": result,
            "txn_id": pt["txn_id"],
        }
        st.session_state.history.append(st.session_state.current_response)
        st.session_state.pending_transfer = None
        st.rerun()

    if conf_col2.button("❌ Cancel", use_container_width=True):
        st.session_state.pending_transfer = None
        st.session_state.current_response = {
            "prompt": pt["prompt"],
            "result": {
                "intent": "TRANSFER",
                "status": "CANCELLED",
                "message": "Transfer cancelled. No changes were made to your account.",
                "data": None,
                "execution_trace": [
                    f"Supervisor: User cancelled transfer of ₹{pt['amount']:,.2f} before execution.",
                    "Ledger: Zero mutations made. Balances remain unmodified.",
                ],
                "parser_used": "USER_ACTION",
                "explanation_source": "LOCAL_EXPLANATION",
            },
            "txn_id": None,
        }
        st.rerun()


# ==============================================================================
# 5. VISUAL REQUEST PIPELINE COMPONENT
# ==============================================================================
if st.session_state.current_response:
    curr = st.session_state.current_response
    res = curr["result"]
    intent = res.get("intent", "UNKNOWN")
    status = res.get("status", "UNKNOWN")
    trace = res.get("execution_trace", [])
    parser_used = res.get("parser_used", "LOCAL_PARSER")
    expl_source = res.get("explanation_source", "LOCAL_EXPLANATION")

    # Determine real agent participation based on execution trace
    trace_text = " ".join(trace)
    banking_agent_ran = "Banking Agent" in trace_text
    risk_agent_ran = "Risk Agent" in trace_text
    credit_agent_ran = "Credit Agent" in trace_text

    # Pipeline node state helpers
    def step_class(has_run: bool) -> str:
        return "step-completed" if has_run else "step-skipped"

    def step_status(has_run: bool) -> str:
        return "Completed" if has_run else "Not needed for this request"

    pipeline_html = f"""
    <div class="pipeline-container">
        <div class="pipeline-title">
            <span class="pipeline-pulse-dot"></span>
            <b>Visual Request Pipeline:</b> Your Request &rarr; Coordinator &rarr; Specialist Agents &rarr; Gemini Response &rarr; Your Answer
        </div>
        <div class="pipeline-track">
            <div class="pipeline-step step-completed">
                <div class="step-icon">💬</div>
                <div class="step-title">Your Request</div>
                <div class="step-status">Received</div>
            </div>
            <div class="pipeline-step step-completed">
                <div class="step-icon">🎯</div>
                <div class="step-title">Coordinator</div>
                <div class="step-status">Intent: {html.escape(intent)}</div>
            </div>
            <div class="pipeline-step {step_class(banking_agent_ran)}">
                <div class="step-icon">🏦</div>
                <div class="step-title">Banking Agent</div>
                <div class="step-status {'status-skipped' if not banking_agent_ran else ''}">{step_status(banking_agent_ran)}</div>
            </div>
            <div class="pipeline-step {step_class(risk_agent_ran)}">
                <div class="step-icon">🛡️</div>
                <div class="step-title">Risk Agent</div>
                <div class="step-status {'status-skipped' if not risk_agent_ran else ''}">{step_status(risk_agent_ran)}</div>
            </div>
            <div class="pipeline-step {step_class(credit_agent_ran)}">
                <div class="step-icon">📊</div>
                <div class="step-title">Credit Agent</div>
                <div class="step-status {'status-skipped' if not credit_agent_ran else ''}">{step_status(credit_agent_ran)}</div>
            </div>
            <div class="pipeline-step step-completed">
                <div class="step-icon">🤖</div>
                <div class="step-title">Gemini Response</div>
                <div class="step-status">{'Gemini Natural Language' if expl_source == 'GEMINI_EXPLANATION' else 'Plain-English Fallback'}</div>
            </div>
            <div class="pipeline-step step-completed">
                <div class="step-icon">✅</div>
                <div class="step-title">Your Answer</div>
                <div class="step-status">Presented</div>
            </div>
        </div>
    </div>
    """
    st.markdown(pipeline_html, unsafe_allow_html=True)


    # ==============================================================================
    # 6. FRIENDLY CUSTOMER-FACING ANSWER & RESULTS
    # ==============================================================================
    data = res.get("data")
    friendly_message = res.get("message", "")

    # Source provenance indicator
    if expl_source == "GEMINI_EXPLANATION":
        st.caption("✨ Response generated by Gemini LLM (Natural Language)")
    else:
        st.caption("⚡ Response generated by Local Fallback (Deterministic Plain-English)")

    # Display clean status alert card
    if status in ("SUCCESS", "APPROVED", "ELIGIBLE"):
        st.success(f"### Completed successfully\n{friendly_message}")
    elif status == "REVIEW_REQUIRED":
        st.warning(f"### Review Required\n{friendly_message}")
    elif status in ("BLOCKED", "FAILED"):
        st.error(f"### Request Stopped\n{friendly_message}")
    elif status in ("ON_HOLD", "INELIGIBLE"):
        st.warning(f"### Application Notice\n{friendly_message}")
    elif status == "NEEDS_INPUT":
        st.info(f"### Additional Information Needed\n{friendly_message}")
    elif status == "CANCELLED":
        st.info(f"### Notice\n{friendly_message}")
    else:
        st.info(f"### Notice\n{friendly_message}")

    # Formatted financial details
    if data:
        if intent == "BALANCE" and isinstance(data, dict):
            b_col1, b_col2 = st.columns(2)
            b_col1.metric("Account ID", data.get("account_id"))
            b_col2.metric("Available Balance", f"₹{data.get('balance', 0):,.2f}")

        elif intent == "STATEMENT" and isinstance(data, dict):
            st.markdown(f"**Transaction Records for Account {data.get('account_id')}** (Current Balance: ₹{data.get('current_balance', 0):,.2f}):")
            txs = data.get("transactions", [])
            if txs:
                st.dataframe(
                    [
                        {
                            "Reference ID": t.get("transaction_id"),
                            "Date & Time": t.get("timestamp"),
                            "Transaction Type": t.get("type"),
                            "Amount": f"₹{t.get('amount', 0):,.2f}",
                            "Description": t.get("description"),
                            "Balance After": f"₹{t.get('balance_after', 0):,.2f}",
                        }
                        for t in txs
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

        elif intent == "TRANSFER" and isinstance(data, dict):
            t_cols = st.columns(3)
            t_cols[0].metric("Transfer Amount", f"₹{data.get('amount', 0):,.2f}")
            if "sender_balance" in data and data["sender_balance"] is not None:
                t_cols[1].metric("Sender New Balance", f"₹{data.get('sender_balance'):,.2f}")
            if "recipient_balance" in data and data["recipient_balance"] is not None:
                t_cols[2].metric("Recipient New Balance", f"₹{data.get('recipient_balance'):,.2f}")

        elif intent == "LOAN_ELIGIBILITY" and isinstance(data, dict):
            l_cols = st.columns(3)
            l_cols[0].metric("Credit Score", data.get("credit_score"))
            l_cols[1].metric("Debt-to-Income (DTI)", f"{data.get('dti', 0):.1f}%")
            l_cols[2].metric("Risk Rating", data.get("risk_level", "N/A"))


    # ==============================================================================
    # 7. HOW THIS REQUEST WAS HANDLED (COLLAPSED BY DEFAULT)
    # ==============================================================================
    with st.expander("🔍 How this request was handled", expanded=False):
        st.markdown(
            f"**Identified Request:** `{intent}` &nbsp;|&nbsp; "
            f"**Intent Parser:** `{parser_used}` &nbsp;|&nbsp; "
            f"**Explanation Engine:** `{expl_source}` &nbsp;|&nbsp; "
            f"**System Status:** `{status}`"
        )
        st.markdown("---")
        st.markdown("**Chronological Multi-Agent Trace:**")
        for i, step in enumerate(trace):
            if step.startswith("Supervisor:"):
                st.markdown(f"**{i+1}. 🎯 {step}**")
            elif step.startswith("Banking Agent:"):
                st.markdown(f"**{i+1}. 🏦 {step}**")
            elif step.startswith("Risk Agent:"):
                st.markdown(f"**{i+1}. 🛡️ {step}**")
            elif step.startswith("Credit Agent:"):
                st.markdown(f"**{i+1}. 📊 {step}**")
            else:
                st.markdown(f"**{i+1}. ⚙️ {step}**")

        # Nested collapsed JSON inspector
        with st.expander("🛠️ View Raw Technical Payload (JSON)", expanded=False):
            st.json(res)


# ==============================================================================
# 8. ACTIVITY HISTORY (COLLAPSED BY DEFAULT)
# ==============================================================================
if len(st.session_state.history) > 1:
    with st.expander("🕒 Recent Activity", expanded=False):
        for idx, item in enumerate(reversed(st.session_state.history[:-1])):
            item_status = item["result"].get("status", "UNKNOWN")
            st.markdown(
                f"**Request:** `{item['prompt']}`  \n"
                f"**Status:** `{item_status}` — {item['result'].get('message', '')}"
            )
            st.divider()
