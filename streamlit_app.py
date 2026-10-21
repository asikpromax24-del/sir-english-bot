import streamlit as st
from groq import Groq
import google.generativeai as genai
from ddgs import DDGS
import urllib.parse
import edge_tts
import asyncio
import io
from langdetect import detect
import json
import hashlib
import hmac
import os
import re
from urllib.parse import urlparse
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
import requests
from bs4 import BeautifulSoup
import datetime
import extra_streamlit_components as stx

# ================= ১. পেজ কনফিগারেশন ও API ক্লায়েন্ট =================
st.set_page_config(page_title="ASIKERA AI", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

def get_secret(name, default=None):
    try: return st.secrets.get(name, default)
    except Exception: return os.environ.get(name, default)

try: cookies = stx.CookieManager(key="asikera_cookie_manager")
except Exception: cookies = None

GROQ_API_KEY = get_secret("GROQ_API_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
if GEMINI_API_KEY: genai.configure(api_key=GEMINI_API_KEY)
supabase: Client | None = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

# ================= SUBSCRIPTION / PAYMENT CONFIG =================
PAYMENT_DETAILS = {
    "bKash": "01608364088", "Rocket": "01608364088", "Binance Pay ID": "1076189034",
    "USDT (TRC20)": "TKeEd3wuTqHse2rdzAg3rqYeRfQD1NC7tq",
}
PLANS = {
    "Monthly": {"days": 30, "bdt": 299, "usd": 3.99},
    "Quarterly": {"days": 90, "bdt": 799, "usd": 10.99},
    "Yearly": {"days": 365, "bdt": 2999, "usd": 39.99},
}
FREE_DAILY_LIMIT = 10

def _utc_now(): return datetime.datetime.now(datetime.timezone.utc)
def _admin_emails():
    raw = get_secret("ADMIN_EMAILS", "") or ""
    return {x.strip().lower() for x in str(raw).split(",") if x.strip()}
def is_admin(email): return (email or "").strip().lower() in _admin_emails()

def get_subscription(email):
    if not supabase: return None
    try:
        r = supabase.table("subscriptions").select("status,plan,expires_at").eq("user_email", email.lower()).eq("status", "active").order("expires_at", desc=True).limit(1).execute()
        if not r.data: return None
        sub = r.data[0]
        expires = datetime.datetime.fromisoformat(str(sub["expires_at"]).replace("Z", "+00:00"))
        if expires > _utc_now(): return sub
    except Exception: pass
    return None

def daily_usage(email):
    if not supabase: return 0
    today = _utc_now().date().isoformat()
    try:
        r = supabase.table("daily_usage").select("message_count").eq("user_email", email.lower()).eq("usage_date", today).limit(1).execute()
        return int(r.data[0]["message_count"]) if r.data else 0
    except Exception: return 0

def increment_daily_usage(email):
    if not supabase: return False
    today = _utc_now().date().isoformat()
    try:
        r = supabase.table("daily_usage").select("id,message_count").eq("user_email", email.lower()).eq("usage_date", today).limit(1).execute()
        if r.data:
            supabase.table("daily_usage").update({"message_count": int(r.data[0]["message_count"]) + 1}).eq("id", r.data[0]["id"]).execute()
        else:
            supabase.table("daily_usage").insert({"user_email": email.lower(), "usage_date": today, "message_count": 1}).execute()
        return True
    except Exception: return False

def submit_payment_request(email, plan, method, transaction_ref):
    if not supabase: return False, "Supabase is not configured."
    try:
        supabase.table("payment_requests").insert({
            "user_email": email.lower(), "plan": plan, "payment_method": method,
            "transaction_ref": transaction_ref.strip(), "amount_bdt": PLANS[plan]["bdt"],
            "amount_usd": PLANS[plan]["usd"], "status": "pending"
        }).execute()
        return True, "Request submitted. Wait for Admin approval."
    except Exception: return False, "Could not submit request."

def approve_payment_request(request_id, admin_email):
    if not supabase or not is_admin(admin_email): return False, "Permission denied."
    try:
        result = supabase.table("payment_requests").select("id,user_email,plan,status").eq("id", request_id).eq("status", "pending").limit(1).execute()
        if not result.data: return False, "Request is no longer pending."
        req = result.data[0]
        existing = get_subscription(req["user_email"])
        now = _utc_now()
        start = max(now, datetime.datetime.fromisoformat(str(existing["expires_at"]).replace("Z", "+00:00"))) if existing else now
        expires = start + datetime.timedelta(days=PLANS[req["plan"]]["days"])
        
        supabase.table("subscriptions").insert({"user_email": req["user_email"], "plan": req["plan"], "status": "active", "starts_at": now.isoformat(), "expires_at": expires.isoformat(), "approved_by": admin_email.lower(), "payment_request_id": request_id}).execute()
        supabase.table("payment_requests").update({"status": "approved", "reviewed_by": admin_email.lower(), "reviewed_at": now.isoformat()}).eq("id", request_id).eq("status", "pending").execute()
        return True, f"Approved for {req['user_email']}."
    except Exception: return False, "Approval failed."

# ================= ২. ডেটাবেস ফাংশন =================
def make_hashes(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return "pbkdf2_sha256$310000$" + salt.hex() + "$" + digest.hex()

def verify_password(password, stored_hash):
    try:
        if stored_hash.startswith("pbkdf2_sha256$"):
            _, rounds, salt_hex, digest_hex = stored_hash.split("$", 3)
            candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)).hex()
            return hmac.compare_digest(candidate, digest_hex)
    except Exception: return False

def create_user(email, password):
    if not supabase: return False
    try: supabase.table("users").insert({"email": email.lower(), "password": make_hashes(password)}).execute(); return True
    except Exception: return False

def login_user(email, password):
    if not supabase: return False
    try:
        response = supabase.table("users").select("password").eq("email", email.lower()).limit(1).execute()
        if not response.data: return False
        return verify_password(password, response.data[0]["password"])
    except Exception: return False

def save_chat(email, session_name, messages):
    if not supabase: return
    try:
        supabase.table("chats").delete().eq("user_email", email).eq("session_name", session_name).execute()
        supabase.table("chats").insert({"user_email": email, "session_name": session_name, "messages": messages}).execute()
    except Exception: pass

def load_chats(email):
    if not supabase: return {"New Chat": []}
    try:
        response = supabase.table("chats").select("session_name, messages").eq("user_email", email).execute()
        sessions = {row["session_name"]: row["messages"] for row in response.data}
        return sessions if sessions else {"New Chat": []}
    except Exception: return {"New Chat": []}

# ================= ৩. অডিও জেনারেটর =================
def generate_audio_edge(text, voice_type="Female"):
    try:
        lang = detect(text)
        voice = 'bn-BD-NabanitaNeural' if lang == 'bn' and voice_type == "Female" else ('bn-BD-PradeepNeural' if lang == 'bn' else ('en-US-AriaNeural' if voice_type == "Female" else 'en-US-GuyNeural'))
    except Exception: voice = 'en-US-AriaNeural'
    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": audio_data += chunk["data"]
        return audio_data
    try:
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        return io.BytesIO(loop.run_until_complete(_generate()))
    except Exception: return None

# ================= ৪. প্রিমিয়াম ডার্ক থিম CSS =================
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* { font-family: 'Inter', sans-serif !important; }
.stApp { background: #070709 !important; color: #E0E0E0; }
#MainMenu, footer {visibility: hidden;}
[data-testid="stHeader"] { background: transparent !important; z-index: 999999 !important; }
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }

/* Sidebar Toggle Fix */
[data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"], button[kind="header"] {
    display: flex !important; visibility: visible !important;
    color: #FFF !important; background-color: #1A1A1E !important;
    border-radius: 8px !important; position: fixed !important;
    top: 15px !important; left: 15px !important; z-index: 1000000 !important;
}

/* Sidebar Theme */
[data-testid="stSidebar"] { background: #0F0F0F !important; border-right: 1px solid #1E1E1E !important; }
[data-testid="stSidebar"] * { color: #CCC !important; }

/* Buttons */
.stButton>button[kind="primary"] { background: linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%) !important; border-radius: 12px !important; border: 0 !important; color: white !important; font-weight: 700 !important; height: 48px !important; box-shadow: 0 8px 20px rgba(139,92,246,0.35); }
.stButton>button[kind="secondary"] { background: #1A1A1E !important; border: 1px solid #2A2A2A !important; border-radius: 10px !important; color: #CCC !important; }

/* Inputs */
div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea { background: rgba(255,255,255,0.05) !important; border: 1px solid rgba(255,255,255,0.15) !important; border-radius: 12px !important; color: white !important; height: 48px !important; }
div[data-testid="stChatInput"] { background: #151518 !important; border: 1px solid #2A2A2A !important; border-radius: 24px !important; }
div[data-testid="stChatInput"] textarea { color: white !important; }

/* Background Blobs */
.blob { position: fixed; border-radius: 50%; filter: blur(80px); opacity: 0.3; z-index: -1; pointer-events: none; }
.blob1 { width: 500px; height: 500px; background: #7C3AED; left: -120px; top: 100px; }
.blob2 { width: 400px; height: 400px; background: #3B82F6; right: -100px; top: 400px; }

.glass { background: rgba(24,24,28,0.85); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); border-radius: 20px; padding: 28px; box-shadow: 0 20px 60px rgba(0,0,0,0.5); }
.feature-card { background: rgba(20,20,24,0.8); border: 1px solid rgba(255,255,255,0.1); border-radius: 16px; padding: 20px; transition: all 0.3s; }
.feature-card:hover { border-color: #7C3AED; transform: translateY(-2px); }

/* Chat Message Fix */
div[data-testid="stChatMessage"] { background-color: transparent; padding: 10px 0; border: none; }
div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li { color: #E0E0E0 !important; font-size: 15px !important; line-height: 1.6; }
div[data-testid="stChatMessage"] table { display: block !important; overflow-x: auto !important; border-collapse: collapse !important; margin: 15px 0 !important; width: 100% !important; }
div[data-testid="stChatMessage"] table th, div[data-testid="stChatMessage"] table td { color: #E0E0E0 !important; border: 1px solid #333 !important; padding: 10px !important; background-color: #1A1A1E !important; }
div[data-testid="stChatMessage"] pre { background-color: #111 !important; border: 1px solid #333 !important; border-radius: 8px !important; padding: 12px !important; }
div[data-testid="stChatMessage"] code { color: #A8FF60 !important; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse; text-align: right; margin-left: auto; margin-right: 0; width: fit-content; max-width: 85%; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) .stMarkdown { background: #1A1A1E; border: 1px solid #333; padding: 12px 18px; border-radius: 20px 20px 4px 20px; display: inline-block; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) .stMarkdown { background: transparent; padding: 10px 0; }
</style>
<div class="blob blob1"></div><div class="blob blob2"></div>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ================= ৫. সেশন ম্যানেজমেন্ট =================
if "page" not in st.session_state: st.session_state.page = "landing"
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if "chat_sessions" not in st.session_state: st.session_state.chat_sessions = {}
if "current_session" not in st.session_state: st.session_state.current_session = "New Chat"

# কুকি থেকে লগইন রিস্টোর
if not st.session_state.logged_in and cookies is not None:
    try:
        saved_email = cookies.get("asikera_email") or ""
        if saved_email:
            st.session_state.logged_in = True
            st.session_state.user_email = saved_email.strip().lower()
            st.session_state.page = "chat"
    except Exception: pass

def nav_to(p): 
    st.session_state.page = p
    st.rerun()

# ================= ৬. ল্যান্ডিং পেজ =================
if st.session_state.page == "landing":
    st.markdown("""
    <div style="display:flex; justify-content:space-between; align-items:center; padding:12px 20px; border:1px solid rgba(255,255,255,0.1); border-radius:14px; background: rgba(15,15,15,0.8); margin: 10px 0 30px;">
        <div style="font-size:22px; font-weight:800; color:white;">⚡ ASIKERA</div>
        <div style="display:flex; gap:20px; color:#888; font-size:14px;"><span>Product</span><span>Solutions</span><span>Docs</span><span>Pricing</span></div>
    </div>
    <div style="text-align:center; padding: 30px 0;">
        <div style="font-size:52px; font-weight:800; color:white; line-height:1.1;">⚡ ASIKERA<br><span style="font-size:26px; background: linear-gradient(135deg,#A78BFA,#60A5FA); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">Asikul's Knowledge Era</span></div>
        <h1 style="font-size:48px; font-weight:800; color:white; margin:20px 0 10px; line-height:1.1;">The Future of AI is Here</h1>
        <p style="color:#999; font-size:16px; max-width:700px; margin:0 auto;">Build, analyze, and create with the most powerful AI tools for the new knowledge era. Chat, generate images, analyze files, and search the web—all in one unified platform.</p>
    </div>
    """, unsafe_allow_html=True)
    
    c1,c2,c3 = st.columns([1,1,1])
    with c2:
        if st.button("Get Started Free →", type="primary", use_container_width=True): nav_to("login")
        if st.button("View Demo", type="secondary", use_container_width=True): 
            st.session_state.logged_in = True
            st.session_state.user_email = "demo@asikera.com"
            nav_to("chat")
    st.markdown('<p style="text-align:center; color:#666; font-size:12px; margin:16px 0;">• No credit card required • Free plan available • Start in seconds</p>', unsafe_allow_html=True)
    
    st.markdown('<h3 style="text-align:center; color:#A78BFA; font-size:14px; letter-spacing:2px; margin:30px 0 16px;">POWERFUL FEATURES</h3>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="feature-card"><h4 style="color:white; margin:0;">💬 Chat</h4><p style="color:#888; font-size:13px; margin:6px 0 0;">Conversational AI for research, writing, and problem-solving.</p></div><div style="height:12px;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="feature-card"><h4 style="color:white; margin:0;">📄 File Analyzer</h4><p style="color:#888; font-size:13px; margin:6px 0 0;">Upload PDFs, CSVs, and documents to analyze data.</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="feature-card"><h4 style="color:white; margin:0;">🖼️ Image Gen</h4><p style="color:#888; font-size:13px; margin:6px 0 0;">Create high-quality images from text.</p></div><div style="height:12px;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="feature-card"><h4 style="color:white; margin:0;">🌐 Web Search</h4><p style="color:#888; font-size:13px; margin:6px 0 0;">Search the live web for up-to-date information.</p></div>', unsafe_allow_html=True)
    
    st.markdown('<p style="text-align:center; color:#666; font-size:13px; margin-top:40px;">Trusted by 1,000+ innovators</p>', unsafe_allow_html=True)
    st.stop()

# ================= ৭. লগইন পেজ =================
if st.session_state.page == "login":
    if st.button("← Back to Home", type="secondary"): nav_to("landing")
    st.markdown("""
    <div style="text-align:center; padding: 10px 0;">
        <div style="font-size:42px; font-weight:800; color:white;">⚡ ASIKERA</div>
        <div style="color:#666; font-size:11px; letter-spacing:3px; font-weight:600;">ASIKUL'S KNOWLEDGE ERA</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div style="max-width:440px; margin:0 auto;"><div class="glass">', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Sign in", "Create account"])
    with tab1:
        with st.form("login_form"):
            st.markdown('<h3 style="color:white; margin:0;">Welcome back</h3><p style="color:#888; font-size:13px;">Sign in to your workspace</p>', unsafe_allow_html=True)
            l_email = st.text_input("Email", placeholder="you@company.com")
            l_pass = st.text_input("Password", type="password", placeholder="••••••••")
            if st.form_submit_button("Login", use_container_width=True):
                if login_user(l_email, l_pass):
                    st.session_state.logged_in = True
                    st.session_state.user_email = l_email.strip().lower()
                    if cookies is not None: cookies.set("asikera_email", st.session_state.user_email)
                    st.session_state.chat_sessions = load_chats(st.session_state.user_email)
                    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]
                    nav_to("chat")
                else: st.error("Invalid credentials.")
    with tab2:
        with st.form("signup_form"):
            st.markdown('<h3 style="color:white; margin:0;">Create account</h3><p style="color:#888; font-size:13px;">Join ASIKERA today</p>', unsafe_allow_html=True)
            s_email = st.text_input("Email", placeholder="you@company.com")
            s_pass = st.text_input("Password", type="password", placeholder="Min 6 characters")
            if st.form_submit_button("Sign Up", use_container_width=True):
                if len(s_pass) < 6: st.warning("Password too short.")
                elif create_user(s_email, s_pass): st.success("Account created! Please Sign In.")
                else: st.error("Email already registered.")
                
    st.markdown('</div></div>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center; color:#444; font-size:11px; margin-top:20px;">© 2024 ASIKERA AI • Privacy • Terms</p>', unsafe_allow_html=True)
    st.stop()

# ================= ৮. মেইন অ্যাপ (সাইডবার ও চ্যাট) =================
# প্রিমিয়াম মোড চেক
premium_for_modes = bool(get_subscription(st.session_state.user_email))

if st.session_state.page == "chat":
    CATEGORIES = [
        "💬 General Chat", "🎓 English Tutor", "👨‍💻 Coding Assistant", 
        "📚 Learning & Study", "✍️ Writing & Editing", "🔍 Deep Research", 
        "🎨 Image Generation", "📄 File/PDF Analyzer", "🌐 Web Search", 
        "📊 Data Analysis", "🌍 Translator", "🔗 URL Reader"
    ]
    free_categories = ["💬 General Chat", "🎓 English Tutor", "👨‍💻 Coding Assistant", "📚 Learning & Study", "✍️ Writing & Editing"]
    mode_options = CATEGORIES if premium_for_modes else free_categories

    with st.sidebar:
        st.markdown("## ⚡ ASIKERA")
        if st.button("＋ New Chat", type="primary", use_container_width=True): 
            new_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
            st.session_state.chat_sessions[new_id] = []
            st.session_state.current_session = new_id
            st.rerun()
        
        search_query = st.text_input("Search", placeholder="🔍 Search chats...", label_visibility="collapsed")
        
        st.markdown("**AI MODEL / MODES**")
        selected_category = st.selectbox("Mode", mode_options, label_visibility="collapsed")
        
        voice_gender = st.radio("Voice", ["Female", "Male"], horizontal=True)
        
        st.markdown("**RECENT CHATS**")
        filtered_sessions = [s for s in st.session_state.chat_sessions.keys() if search_query.lower() in s.lower()]
        for s in filtered_sessions:
            if st.button(f"💬 {s}", use_container_width=True, type="secondary"):
                st.session_state.current_session = s
                st.rerun()
                
        st.markdown("---")
        st.markdown("### 👑 ASIKERA Premium")
        active_sub = get_subscription(st.session_state.user_email)
        used_today = daily_usage(st.session_state.user_email)
        if active_sub:
            st.success(f"Premium Active\nExpires: {str(active_sub['expires_at'])[:10]}")
        else:
            st.info(f"Free plan · {used_today}/{FREE_DAILY_LIMIT} msgs used today")
            with st.expander("Upgrade to Premium"):
                chosen_plan = st.selectbox("Plan", list(PLANS.keys()), format_func=lambda x: f"{x} — ৳{PLANS[x]['bdt']}")
                chosen_method = st.selectbox("Method", list(PAYMENT_DETAILS.keys()))
                st.code(PAYMENT_DETAILS[chosen_method])
                txn_ref = st.text_input("TrxID")
                if st.button("Submit Payment", use_container_width=True):
                    ok, msg = submit_payment_request(st.session_state.user_email, chosen_plan, chosen_method, txn_ref)
                    (st.success if ok else st.error)(msg)
                    
        if is_admin(st.session_state.user_email):
            with st.expander("🛡️ Admin: Approvals"):
                try:
                    pending = supabase.table("payment_requests").select("id,user_email,plan,transaction_ref").eq("status", "pending").execute().data or []
                    if not pending: st.caption("No pending requests.")
                    for req in pending:
                        st.markdown(f"**{req['user_email']}** · {req['plan']}")
                        st.caption(f"Ref: {req['transaction_ref']}")
                        if st.button("Approve", key=f"app_{req['id']}", type="primary"):
                            ok, msg = approve_payment_request(req["id"], st.session_state.user_email)
                            (st.success if ok else st.error)(msg)
                            st.rerun()
                except Exception: pass

        st.markdown("---")
        if st.button("↪ Logout", use_container_width=True, type="secondary"):
            st.session_state.logged_in = False
            st.session_state.user_email = ""
            if cookies is not None: cookies.delete("asikera_email")
            nav_to("landing")

    # মেইন চ্যাট UI
    st.markdown("### ✨ " + st.session_state.current_session)
    current_messages = st.session_state.chat_sessions.get(st.session_state.current_session, [])

    for m in current_messages:
        avatar = "⚡" if m["role"] == "assistant" else "👤"
        with st.chat_message(m["role"], avatar=avatar):
            st.markdown(m["content"])

    # ইমেজ ও ফাইল আপলোড
    with st.expander("🎤 Voice & Image (Premium)"):
        if premium_for_modes:
            audio_value = st.audio_input("Record a voice message")
            uploaded_image = st.file_uploader("Attach an image", type=["png", "jpg", "jpeg"])
        else:
            st.caption("Voice and image understanding are Premium features.")

    if prompt := st.chat_input("Ask ASIKERA anything..."):
        if not premium_for_modes and daily_usage(st.session_state.user_email) >= FREE_DAILY_LIMIT:
            st.warning("Free limit reached. Upgrade to continue.")
            st.stop()
            
        current_messages.append({"role":"user","content":prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
            
        with st.chat_message("assistant", avatar="⚡"):
            with st.spinner("Thinking..."):
                try:
                    if not groq_client: raise Exception("Groq API Key missing.")
                    base_identity = "You are ASIKERA. Do not mention OpenAI or Google. "
                    persona_prompt = base_identity + f"You are operating in {selected_category} mode. Answer clearly."
                    
                    stream = groq_client.chat.completions.create(
                        model="openai/gpt-oss-120b", 
                        messages=[{"role": "system", "content": persona_prompt}] + current_messages[-10:], 
                        temperature=0.7, max_tokens=1500, stream=True
                    )
                    reply = st.write_stream(chunk.choices[0].delta.content for chunk in stream if chunk.choices[0].delta.content)
                except Exception as e:
                    reply = f"Error: {e}"
                    st.error(reply)
                    
        current_messages.append({"role":"assistant","content":reply})
        save_chat(st.session_state.user_email, st.session_state.current_session, current_messages)
        
        if not premium_for_modes: increment_daily_usage(st.session_state.user_email)
        
        # অডিও
        audio_data = generate_audio_edge(reply, voice_gender)
        if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)
