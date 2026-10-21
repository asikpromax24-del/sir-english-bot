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
st.set_page_config(page_title="ASIKERA AI", page_icon="⚡", layout="wide", initial_sidebar_state="auto")

def get_secret(name, default=None):
    try: return st.secrets.get(name, default)
    except Exception: return os.environ.get(name, default)

# Cookie Manager (লগইন মনে রাখার জন্য)
cookies = stx.CookieManager(key="asikera_cookie")

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

def submit_payment_request(email, plan, method, transaction_ref, screenshot):
    if not supabase: return False, "Supabase is not configured."
    if not transaction_ref.strip(): return False, "Enter transaction ID."
    if not screenshot: return False, "Please upload a payment screenshot."
    
    try:
        file_ext = screenshot.name.split('.')[-1]
        file_name = f"{email}_{int(_utc_now().timestamp())}.{file_ext}"
        bucket = supabase.storage.from_("payment_proofs")
        bucket.upload(file_name, screenshot.getvalue(), {"content-type": screenshot.type})
        public_url = bucket.get_public_url(file_name)

        supabase.table("payment_requests").insert({
            "user_email": email.lower(), "plan": plan, "payment_method": method,
            "transaction_ref": transaction_ref.strip(), "amount_bdt": PLANS[plan]["bdt"],
            "amount_usd": PLANS[plan]["usd"], "status": "pending", "screenshot_url": public_url
        }).execute()
        return True, "Request submitted! Wait for Admin approval."
    except Exception as e:
        return False, f"Could not submit request. Error: {e}"

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

# ================= ৪. সেশন ম্যানেজমেন্ট ও কুকি রিস্টোর =================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""

if not st.session_state.logged_in:
    try:
        saved_email = cookies.get("asikera_user")
        if saved_email:
            st.session_state.logged_in = True
            st.session_state.user_email = saved_email
            st.rerun()
    except Exception: pass

# ================= ৫. লগইন পেজ (টেক্সট কালার ও ডিজাইন ফিক্স) =================
if not st.session_state.logged_in:
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    /* Hide Top Right Toolbar */
    #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stAppDeployButton"], [data-testid="stDecoration"] {{ display: none !important; }}
    header[data-testid="stHeader"] {{ background: transparent !important; }}
    
    .stApp {{ background: #070709; font-family: 'Inter', sans-serif; }}
    .blob1 {{ position: fixed; width: 400px; height: 400px; background: #7C3AED; filter: blur(100px); opacity: 0.4; top: -100px; left: -100px; z-index: -1; }}
    .blob2 {{ position: fixed; width: 400px; height: 400px; background: #3B82F6; filter: blur(100px); opacity: 0.4; bottom: -100px; right: -100px; z-index: -1; }}
    
    /* Glassmorphism Card */
    div[data-testid="stForm"] {{
        background: rgba(20, 20, 25, 0.85) !important; backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1) !important; border-radius: 24px !important;
        padding: 40px !important; box-shadow: 0 20px 60px rgba(0,0,0,0.6) !important;
    }}
    
    /* Force White Text for everything inside form */
    div[data-testid="stForm"] p, div[data-testid="stForm"] h3, div[data-testid="stForm"] label {{
        color: #FFFFFF !important;
    }}
    
    /* Tabs */
    button[data-baseweb="tab"] p {{ color: #A0A0B0 !important; }}
    button[data-baseweb="tab"][aria-selected="true"] p {{ color: #4D6BFE !important; }}
    button[data-baseweb="tab"][aria-selected="true"] {{ border-bottom-color: #4D6BFE !important; }}
    
    /* Input Boxes */
    div[data-testid="stTextInput"] input {{
        background: rgba(255, 255, 255, 0.05) !important; 
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        border-radius: 10px !important; 
        color: #FFFFFF !important; 
        height: 45px !important;
    }}
    
    /* Buttons */
    div[data-testid="stFormSubmitButton"] > button {{
        background: linear-gradient(135deg, #8B5CF6, #3B82F6) !important;
        border-radius: 10px !important; height: 45px !important; font-weight: 700 !important; color: white !important;
    }}
    </style>
    <div class="blob1"></div><div class="blob2"></div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.markdown("""
        <div style='padding: 50px 20px;'>
            <div style='font-size: 48px; font-weight: 800; color: white; line-height: 1.1;'>⚡ ASIKERA<br><span style='font-size: 24px; background: linear-gradient(135deg,#A78BFA,#60A5FA); -webkit-background-clip:text; -webkit-text-fill-color:transparent;'>Asikul's Knowledge Era</span></div>
            <p style='color: #A0A0B0; font-size: 18px; margin-top: 20px; line-height: 1.5;'>The most advanced AI workspace for learning, coding, writing, and research. Trusted by innovators.</p>
            <div style='display: flex; gap: 15px; margin-top: 30px;'>
                <span style='color: #CCC; font-size: 14px;'>✔ Secure Login</span>
                <span style='color: #CCC; font-size: 14px;'>✔ 30+ AI Modes</span>
                <span style='color: #CCC; font-size: 14px;'>✔ Premium Features</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        tab1, tab2 = st.tabs(["Sign In", "Create Account"])
        with tab1:
            with st.form("login_form"):
                st.markdown("<h3 style='margin:0;'>Welcome back</h3>", unsafe_allow_html=True)
                l_email = st.text_input("Email", placeholder="you@company.com")
                l_pass = st.text_input("Password", type="password", placeholder="••••••••")
                if st.form_submit_button("Sign In", use_container_width=True):
                    if login_user(l_email, l_pass):
                        st.session_state.logged_in = True
                        st.session_state.user_email = l_email.strip().lower()
                        cookies.set("asikera_user", st.session_state.user_email, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                        st.rerun()
                    else: st.error("Invalid credentials.")
        with tab2:
            with st.form("signup_form"):
                st.markdown("<h3 style='margin:0;'>Create Account</h3>", unsafe_allow_html=True)
                s_email = st.text_input("Email", placeholder="you@company.com")
                s_pass = st.text_input("Password", type="password", placeholder="Min 6 characters")
                if st.form_submit_button("Sign Up", use_container_width=True):
                    if len(s_pass) < 6: st.warning("Password too short.")
                    elif create_user(s_email, s_pass): st.success("Account created! Please Sign In.")
                    else: st.error("Email already registered.")
    st.stop()

# ================= ৬. মেইন অ্যাপ CSS =================
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
.stApp { background: #070709; font-family: 'Inter', sans-serif; color: #E0E0E0; }
[data-testid="stSidebar"] { background: #0F0F0F; border-right: 1px solid #1E1E1E; width: 280px !important; }

/* Hide Top Toolbar */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stAppDeployButton"], [data-testid="stDecoration"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent !important; }

/* Keep Sidebar Toggle Visible */
[data-testid="collapsedControl"], [data-testid="stSidebarCollapsedControl"], button[kind="header"] {
    display: flex !important; visibility: visible !important;
    color: #FFF !important; background-color: #1A1A1E !important;
    border-radius: 8px !important; position: fixed !important;
    top: 15px !important; left: 15px !important; z-index: 1000000 !important;
}

.block-container { padding-top: 3rem !important; padding-bottom: 6rem !important; max-width: 850px !important; margin: 0 auto !important; }
.stButton>button[kind="primary"] { background: #4D6BFE; border-radius: 10px; height: 40px; font-weight: 600; border: 0; color: white; }
.stButton>button[kind="secondary"] { background: #1A1A1E; border: 1px solid #2A2A2A; border-radius: 10px; color: #CCC; padding: 5px; }

/* Chat Bubbles */
div[data-testid="stChatMessage"] { background-color: transparent; padding: 10px 0; border: none; }
div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li { color: #E0E0E0 !important; font-size: 15px !important; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse; text-align: right; margin-left: auto; margin-right: 0; width: fit-content; max-width: 85%; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) .stMarkdown { background: #1A1A1E; border: 1px solid #333; padding: 12px 18px; border-radius: 20px 20px 4px 20px; display: inline-block; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) .stMarkdown { background: #151518; border: 1px solid #2A2A2A; padding: 12px 18px; border-radius: 20px 20px 20px 4px; display: inline-block; width: 100%; }

/* Inputs */
div[data-testid="stTextInput"] input { background: #1A1A1E !important; color: white !important; border: 1px solid #333 !important; border-radius: 10px !important; }
div[data-testid="stChatInput"] { background: #151518 !important; border-radius: 12px !important; border: 1px solid #333 !important; }
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { background: #1A1A1E !important; color: white !important; border: 1px solid #333 !important; }

/* Sidebar Text */
.sidebar-title { font-size: 20px; font-weight: 700; color: #FFF; }
.sidebar-subtitle { font-size: 10px; color: #666; letter-spacing: 1.5px; }
.divider { border-top: 1px solid #1E1E1E; margin: 15px 0; }
.label-text { font-size: 12px; color: #888; margin-bottom: 8px; font-weight: 600; text-transform: uppercase; }
.user-card { display: flex; align-items: center; background: #1A1A1E; padding: 10px; border-radius: 10px; border: 1px solid #333; }
.user-avatar { background: #4D6BFE; color: white; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; margin-right: 12px; }
.user-email { font-size: 12px; color: #CCC; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ================= ৭. সাইডবার ও চ্যাট লজিক =================
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_chats(st.session_state.user_email)
if "current_session" not in st.session_state:
    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]

CATEGORIES = [
    "💬 General Chat", "🎓 English Tutor", "👨‍💻 Coding Assistant", "📚 Learning & Study", "✍️ Writing & Editing", 
    "🔍 Deep Research", "🎨 Image Generation", "📄 File/PDF Analyzer", "🌐 Web Search", 
    "📊 Data Analysis", "🌍 Translator", "🔗 URL Reader", "📝 Text Summarizer", "💡 Idea Generator"
]

with st.sidebar:
    st.markdown("## ⚡ ASIKERA")
    st.markdown("<div class='sidebar-subtitle'>KNOWLEDGE ERA</div>", unsafe_allow_html=True)
    st.write("")
    
    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        new_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
        st.session_state.chat_sessions[new_id] = []
        st.session_state.current_session = new_id
        st.rerun()
        
    search_query = st.text_input("Search", placeholder="Search chats...", label_visibility="collapsed")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    premium_for_modes = bool(get_subscription(st.session_state.user_email))
    
    st.markdown('<div class="label-text">✨ 30+ Modes</div>', unsafe_allow_html=True)
    free_categories = ["💬 General Chat", "🎓 English Tutor", "👨‍💻 Coding Assistant", "📚 Learning & Study", "✍️ Writing & Editing"]
    mode_options = CATEGORIES if premium_for_modes else free_categories
    selected_category = st.selectbox("Select Mode", mode_options, label_visibility="collapsed")
    
    voice_gender = st.radio("Voice", ["Female", "Male"], horizontal=True)
    
    base_identity = "You are ASIKERA. Do not mention OpenAI or Google. "
    persona_prompt = base_identity + f"You are operating in {selected_category} mode. Answer clearly."

    if st.session_state.chat_sessions[st.session_state.current_session]:
        chat_text = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.chat_sessions[st.session_state.current_session]])
        st.download_button("📥 Export Chat (TXT)", data=chat_text, file_name="asikera_chat.txt", use_container_width=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="label-text">Recent</div>', unsafe_allow_html=True)
    
    filtered_sessions = [s for s in st.session_state.chat_sessions.keys() if search_query.lower() in s.lower()]
    for s in filtered_sessions:
        if st.button(f"💬 {s}", use_container_width=True, type="secondary"):
            st.session_state.current_session = s
            st.rerun()
            
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="user-card"><div class="user-avatar">👤</div><div class="user-email">{st.session_state.user_email}</div></div>""", unsafe_allow_html=True)
    
    # Subscription & Payment
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown("### 👑 Premium")
    active_sub = get_subscription(st.session_state.user_email)
    used_today = daily_usage(st.session_state.user_email)
    
    if active_sub:
        st.success(f"Premium active · {active_sub['plan']}")
    else:
        st.info(f"Free · {used_today}/{FREE_DAILY_LIMIT} msgs used today")
        with st.expander("Upgrade to Premium", expanded=False):
            chosen_plan = st.selectbox("Plan", list(PLANS.keys()), format_func=lambda x: f"{x} — ৳{PLANS[x]['bdt']}")
            chosen_method = st.selectbox("Method", list(PAYMENT_DETAILS.keys()))
            st.code(PAYMENT_DETAILS[chosen_method])
            txn_ref = st.text_input("Transaction ID / TrxID", key="premium_txn_ref")
            payment_proof = st.file_uploader("Upload Screenshot", type=["jpg", "png", "jpeg"], key="payment_proof")
            
            if st.button("Submit Payment", use_container_width=True, type="primary"):
                ok, msg = submit_payment_request(st.session_state.user_email, chosen_plan, chosen_method, txn_ref, payment_proof)
                (st.success if ok else st.error)(msg)

    if is_admin(st.session_state.user_email):
        with st.expander("🛡️ Admin: Payments"):
            try:
                pending = supabase.table("payment_requests").select("id,user_email,plan,transaction_ref,screenshot_url").eq("status", "pending").execute().data or []
                if not pending: st.caption("No pending requests.")
                for req in pending:
                    st.markdown(f"**{req['user_email']}** · {req['plan']}")
                    st.caption(f"Ref: {req['transaction_ref']}")
                    if req.get("screenshot_url"):
                        st.image(req["screenshot_url"], width=200, caption="Screenshot")
                    if st.button("Approve", key=f"app_{req['id']}", type="primary"):
                        ok, msg = approve_payment_request(req["id"], st.session_state.user_email)
                        (st.success if ok else st.error)(msg)
                        st.rerun()
            except Exception: pass

    if st.button("Logout", use_container_width=True, type="secondary"):
        st.session_state.logged_in = False
        st.session_state.user_email = ""
        cookies.delete("asikera_user")
        st.session_state.pop("chat_sessions", None)
        st.session_state.pop("current_session", None)
        st.rerun()

# ================= ৮. মেইন চ্যাট এরিয়া =================
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

if selected_category == "🎨 Image Generation":
    if not get_subscription(st.session_state.user_email):
        st.warning("🎨 Image Generation is a Premium feature.")
        st.stop()
    st.markdown("### 🎨 AI Image Generator")
    img_prompt = st.text_input("Describe your image:")
    if st.button("Generate Image", type="primary") and img_prompt:
        with st.spinner("Painting..."):
            image_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(img_prompt)}?width=1024&height=1024&nologo=true"
            st.image(image_url, use_container_width=True)

elif selected_category == "📄 File/PDF Analyzer":
    if not get_subscription(st.session_state.user_email):
        st.warning("📄 File/PDF analysis is a Premium feature.")
        st.stop()
    st.markdown("### 📄 File Analyzer")
    uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
    file_query = st.text_input("What do you want to know about this file?")
    if st.button("Analyze File", type="primary") and uploaded_file and file_query:
        with st.spinner("Analyzing..."):
            try:
                gemini_model = genai.GenerativeModel("gemini-1.5-flash")
                response = gemini_model.generate_content([file_query, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
                st.markdown(response.text)
            except Exception as e: st.error(f"Error: {e}")

else:
    # চ্যাট ইন্টারফেস
    for m in current_messages:
        avatar = "⚡" if m["role"] == "assistant" else "👤"
        with st.chat_message(m["role"], avatar=avatar):
            st.markdown(m["content"])

    # Premium Voice/Image Inputs
    active_sub_for_chat = bool(get_subscription(st.session_state.user_email))
    with st.expander("🎤 Voice / 📷 Image (Premium)", expanded=False):
        if active_sub_for_chat:
            audio_value = st.audio_input("Record voice")
            uploaded_image = st.file_uploader("Attach image", type=["png", "jpg", "jpeg"])
            st.caption("Tip: You can type a message, attach an image, or record voice.")
        else:
            audio_value = None
            uploaded_image = None
            st.caption("Voice and Image require Premium.")

    # Input & Send Logic
    prompt = st.chat_input("Ask ASIKERA anything...")
    send_attachment = st.button("Send Voice/Image", type="secondary", disabled=(not active_sub_for_chat or (audio_value is None and uploaded_image is None)))

    if prompt or send_attachment:
        if not active_sub_for_chat and daily_usage(st.session_state.user_email) >= FREE_DAILY_LIMIT:
            st.warning("Free limit reached. Upgrade to continue.")
            st.stop()
        if (audio_value or uploaded_image) and not active_sub_for_chat:
            st.warning("Voice/Image requires Premium.")
            st.stop()

        user_text = (prompt or "").strip()
        if audio_value:
            if not groq_client: st.error("Groq API missing.")
            else:
                with st.spinner("Transcribing..."):
                    transcript = groq_client.audio.transcriptions.create(file=("voice.wav", audio_value.getvalue()), model="whisper-large-v3").text
                    user_text = (user_text + "\n\n" + transcript).strip() if user_text else transcript.strip()

        if uploaded_image and not user_text:
            user_text = "Please analyze this image."

        if not user_text:
            st.warning("Write a message or attach a file.")
            st.stop()

        current_messages.append({"role":"user","content":user_text + ("\n\n[Image attached]" if uploaded_image else "")})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_text)
            if uploaded_image:
                st.image(uploaded_image, caption="Attached image", use_container_width=True)

        with st.chat_message("assistant", avatar="⚡"):
            with st.spinner("Thinking..."):
                try:
                    if uploaded_image:
                        gemini_model = genai.GenerativeModel("gemini-1.5-flash")
                        response = gemini_model.generate_content([user_text, {"mime_type": uploaded_image.type, "data": uploaded_image.getvalue()}])
                        reply = response.text or "Could not read image."
                        st.markdown(reply)
                    else:
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

        if not active_sub_for_chat: increment_daily_usage(st.session_state.user_email)

        audio_data = generate_audio_edge(reply, voice_gender)
        if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)
