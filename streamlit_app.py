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
import time
import uuid
import extra_streamlit_components as stx

# ================= ১. পেজ কনফিগারেশন ও API ক্লায়েন্ট =================
# initial_sidebar_state="auto" দিলে মোবাইলে মেনু বাটনটা সবসময় দৃশ্যমান থাকে
st.set_page_config(page_title="ASIKERA AI", page_icon="⚡", layout="wide", initial_sidebar_state="auto")


def get_secret(name, default=None):
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = os.environ.get(name, default)
    return value

# Browser cookie helps restore login after refresh. Cookie values are not encrypted by this component.
try:
    cookies = stx.CookieManager(key="asikera_cookie_manager")
except Exception:
    cookies = None

GROQ_API_KEY = get_secret("GROQ_API_KEY")
GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
SUPABASE_URL = get_secret("SUPABASE_URL")
SUPABASE_KEY = get_secret("SUPABASE_KEY")

# App can still show a setup message rather than crashing when secrets are not configured.
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
supabase: Client | None = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None


# ---- Signed login cookie (cannot be forged without the server secret) ----
def _cookie_secret():
    s = get_secret("COOKIE_SECRET") or get_secret("SUPABASE_KEY")
    return ("asikera-login|" + str(s)).encode("utf-8") if s else None

def make_auth_cookie(email):
    key = _cookie_secret()
    if not key:
        return ""
    ts = str(int(time.time()))
    sig = hmac.new(key, f"{email}|{ts}".encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{email}|{ts}|{sig}"

def read_auth_cookie(value):
    key = _cookie_secret()
    try:
        email, ts, sig = str(value or "").rsplit("|", 2)
        good = hmac.new(key, f"{email}|{ts}".encode("utf-8"), hashlib.sha256).hexdigest()
        if key and hmac.compare_digest(sig, good) and (time.time() - int(ts)) < 30 * 86400:
            return email.strip().lower()
    except Exception:
        pass
    return None


# ================= SUBSCRIPTION / PAYMENT CONFIG =================
# Receiver details are public payment instructions, not API secrets.
PAYMENT_DETAILS = {
    "bKash": "01608364088",
    "Rocket": "01608364088",
    "Binance Pay ID": "1076189034",
    "USDT (TRC20)": "TKeEd3wuTqHse2rdzAg3rqYeRfQD1NC7tq",
    "USDT (BEP20 / BNB Smart Chain)": "0xb83a03d9ded3ac7a4908aa87cfdfe1df9e05f719",
}
PLANS = {
    "Monthly": {"days": 30, "bdt": 299, "usd": 3.99},
    "Quarterly": {"days": 90, "bdt": 799, "usd": 10.99},
    "Yearly": {"days": 365, "bdt": 2999, "usd": 39.99},
}
FREE_DAILY_LIMIT = 10
PAYMENT_PROOF_BUCKET = "payment_proofs"
MAX_PROOF_BYTES = 5 * 1024 * 1024

def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc)

def _admin_emails():
    raw = get_secret("ADMIN_EMAILS", "") or ""
    if isinstance(raw, list):
        return {str(x).strip().lower() for x in raw if str(x).strip()}
    return {x.strip().lower() for x in str(raw).split(",") if x.strip()}

def is_admin(email):
    return (email or "").strip().lower() in _admin_emails()

def get_subscription(email):
    if not supabase:
        return None
    try:
        r = supabase.table("subscriptions").select("status,plan,expires_at").eq("user_email", email.lower()).eq("status", "active").order("expires_at", desc=True).limit(1).execute()
        if not r.data:
            return None
        sub = r.data[0]
        expires = datetime.datetime.fromisoformat(str(sub["expires_at"]).replace("Z", "+00:00"))
        if expires > _utc_now():
            return sub
        try:
            supabase.table("subscriptions").update({"status": "expired"}).eq("user_email", email.lower()).eq("status", "active").execute()
        except Exception:
            pass
    except Exception:
        return None
    return None

def daily_usage(email):
    if not supabase:
        return 0
    today = _utc_now().date().isoformat()
    try:
        r = supabase.table("daily_usage").select("message_count").eq("user_email", email.lower()).eq("usage_date", today).limit(1).execute()
        return int(r.data[0]["message_count"]) if r.data else 0
    except Exception:
        return 0

def increment_daily_usage(email):
    if not supabase:
        return False
    today = _utc_now().date().isoformat()
    try:
        r = supabase.table("daily_usage").select("id,message_count").eq("user_email", email.lower()).eq("usage_date", today).limit(1).execute()
        if r.data:
            row = r.data[0]
            supabase.table("daily_usage").update({"message_count": int(row["message_count"]) + 1}).eq("id", row["id"]).execute()
        else:
            supabase.table("daily_usage").insert({"user_email": email.lower(), "usage_date": today, "message_count": 1}).execute()
        return True
    except Exception:
        return False

def upload_payment_proof(proof_file):
    """Uploads the screenshot to Supabase Storage and returns (ok, public_url_or_error)."""
    data = proof_file.getvalue()
    if len(data) > MAX_PROOF_BYTES:
        return False, "Screenshot is too large (max 5 MB)."
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        ext, mime = "png", "image/png"
    elif data[:3] == b"\xff\xd8\xff":
        ext, mime = "jpg", "image/jpeg"
    else:
        return False, "Please upload a PNG or JPG screenshot."
    path = f"{uuid.uuid4().hex}.{ext}"
    try:
        bucket = supabase.storage.from_(PAYMENT_PROOF_BUCKET)
        bucket.upload(path, data, {"content-type": mime})
        return True, str(bucket.get_public_url(path)).rstrip("?")
    except Exception:
        return False, "Screenshot upload failed. Create the 'payment_proofs' bucket in Supabase (run the payment-proof SQL) and check the server-side key."

def submit_payment_request(email, plan, method, transaction_ref, proof_file=None):
    if not supabase:
        return False, "Supabase is not configured."
    if not transaction_ref.strip():
        return False, "Enter the transaction/reference ID first."
    if proof_file is None:
        return False, "Upload your payment screenshot first."
    ok, result = upload_payment_proof(proof_file)
    if not ok:
        return False, result
    try:
        supabase.table("payment_requests").insert({
            "user_email": email.lower(), "plan": plan, "payment_method": method,
            "transaction_ref": transaction_ref.strip(), "amount_bdt": PLANS[plan]["bdt"],
            "amount_usd": PLANS[plan]["usd"], "status": "pending", "proof_url": result
        }).execute()
        return True, "Request submitted. Premium will activate after admin approval."
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            return False, "This transaction ID was already submitted."
        return False, "Could not submit request. Run the payment-proof SQL in Supabase (adds the proof_url column)."

def approve_payment_request(request_id, admin_email):
    if not supabase or not is_admin(admin_email):
        return False, "Admin permission is not configured for this account."
    try:
        result = supabase.table("payment_requests").select("id,user_email,plan,status").eq("id", request_id).eq("status", "pending").limit(1).execute()
        if not result.data:
            return False, "Request is no longer pending."
        req = result.data[0]
        existing = get_subscription(req["user_email"])
        now = _utc_now()
        if existing:
            exp = datetime.datetime.fromisoformat(str(existing["expires_at"]).replace("Z", "+00:00"))
            start = max(now, exp)
        else:
            start = now
        expires = start + datetime.timedelta(days=PLANS[req["plan"]]["days"])
        # Idempotency guard: if an earlier approval inserted the subscription but
        # failed before updating the request status, finish that update safely.
        prior = supabase.table("subscriptions").select("id,expires_at").eq("payment_request_id", request_id).limit(1).execute()
        if prior.data:
            supabase.table("payment_requests").update({"status": "approved", "reviewed_by": admin_email.lower(), "reviewed_at": now.isoformat()}).eq("id", request_id).execute()
            return True, f"This request was already activated until {str(prior.data[0]['expires_at'])[:10]}."
        # Insert entitlement first; the unique payment_request_id prevents double activation.
        supabase.table("subscriptions").insert({"user_email": req["user_email"], "plan": req["plan"], "status": "active", "starts_at": now.isoformat(), "expires_at": expires.isoformat(), "approved_by": admin_email.lower(), "payment_request_id": request_id}).execute()
        supabase.table("payment_requests").update({"status": "approved", "reviewed_by": admin_email.lower(), "reviewed_at": now.isoformat()}).eq("id", request_id).eq("status", "pending").execute()
        return True, f"Approved for {req['user_email']} until {expires.date().isoformat()}."
    except Exception:
        return False, "Approval failed. Check Supabase tables and permissions, then review the request status."

# ================= ২. ডেটাবেস ফাংশন (Supabase) =================
def make_hashes(password):
    # PBKDF2 is deliberately slow; format is self-describing for future upgrades.
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
    return "pbkdf2_sha256$310000$" + salt.hex() + "$" + digest.hex()

def verify_password(password, stored_hash):
    stored_hash = (stored_hash or "").strip()
    try:
        if stored_hash.startswith("pbkdf2_sha256$"):
            _, rounds, salt_hex, digest_hex = stored_hash.split("$", 3)
            candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(rounds)).hex()
            return hmac.compare_digest(candidate, digest_hex), False
        # Old accounts: plain SHA-256 (hex case/spaces ignored); upgraded to PBKDF2 after a successful login.
        legacy = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(legacy, stored_hash.lower()), True
    except (ValueError, TypeError):
        return False, False

def create_user(email, password):
    if not supabase:
        return False
    email = email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return False
    try:
        supabase.table("users").insert({"email": email, "password": make_hashes(password)}).execute()
        return True
    except Exception:
        return False

def login_user(email, password):
    if not supabase:
        return False
    email = email.strip()
    try:
        row = None
        # Old accounts may have been saved with capital letters, so try lowercase first, then as typed.
        for candidate in dict.fromkeys([email.lower(), email]):
            response = supabase.table("users").select("email,password").eq("email", candidate).limit(1).execute()
            if response.data:
                row = response.data[0]
                break
        if not row:
            return False
        ok, legacy = verify_password(password, row.get("password"))
        if ok and legacy:
            supabase.table("users").update({"password": make_hashes(password)}).eq("email", row["email"]).execute()
        return ok
    except Exception:
        return False

def save_chat(email, session_name, messages):
    if not supabase:
        return
    try:
        supabase.table("chats").delete().eq("user_email", email).eq("session_name", session_name).execute()
        supabase.table("chats").insert({"user_email": email, "session_name": session_name, "messages": messages}).execute()
    except: pass

def load_chats(email):
    if not supabase:
        return {"New Chat": []}
    try:
        response = supabase.table("chats").select("session_name, messages").eq("user_email", email).execute()
        sessions = {row["session_name"]: row["messages"] for row in response.data}
        return sessions if sessions else {"New Chat": []}
    except: return {"New Chat": []}

# ================= ৩. ভয়েস ও অডিও জেনারেটর (Edge-TTS) =================
def generate_audio_edge(text, voice_type="Female"):
    try:
        lang = detect(text)
        if lang == 'bn':
            voice = 'bn-BD-NabanitaNeural' if voice_type == "Female" else 'bn-BD-PradeepNeural'
        else:
            voice = 'en-US-AriaNeural' if voice_type == "Female" else 'en-US-GuyNeural'
    except: voice = 'en-US-AriaNeural'
        
    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": audio_data += chunk["data"]
        return audio_data
    try:
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        return io.BytesIO(loop.run_until_complete(_generate()))
    except: return None

# ================= ৪. থিম সেটিংস (লাইট ও ডার্ক মোড) =================
if "theme" not in st.session_state: st.session_state.theme = "Light"

if st.session_state.theme == "Light":
    bg_color, text_color, sidebar_bg, card_bg = "#F4F6F8", "#1A1A1A", "#FFFFFF", "#FFFFFF"
    border_color, input_bg = "#E5E7EB", "#F9FAFB"
else:
    bg_color, text_color, sidebar_bg, card_bg = "#1E1E1E", "#E0E0E0", "#191919", "#25252D"
    border_color, input_bg = "#333333", "#2A2A2A"

custom_css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
.stApp {{ background: {bg_color}; font-family: 'Inter', sans-serif; color: {text_color}; }}
[data-testid="stSidebar"] {{ background: {sidebar_bg}; border-right: 1px solid {border_color}; width: 280px !important; }}

/* ================= Header: transparent, sidebar toggle preserved ================= */
#MainMenu {{ display: none !important; }}
footer {{ display: none !important; }}
[data-testid="stHeader"] {{
    background: transparent !important;
    box-shadow: none !important;
    border: none !important;
    z-index: 999999 !important;
}}
[data-testid="stDecoration"] {{ display: none !important; }}

/* Hide ONLY the right-side actions (Share / Fork / Edit / menu / Deploy). The header itself stays. */
[data-testid="stToolbarActions"],
[data-testid="stMainMenu"],
[data-testid="stAppDeployButton"],
.stDeployButton,
[data-testid="stToolbar"] button[title*="Share"],
[data-testid="stToolbar"] button[aria-label*="Share"],
[data-testid="stToolbar"] button[title*="Fork"],
[data-testid="stToolbar"] button[aria-label*="Fork"],
[data-testid="stToolbar"] button[title*="Edit"],
[data-testid="stToolbar"] button[aria-label*="Edit"],
[data-testid="stToolbar"] button[title*="Manage"],
[data-testid="stToolbar"] button[aria-label*="Manage"] {{
    display: none !important;
    visibility: hidden !important;
}}
[data-testid="stToolbar"] {{
    background: transparent !important;
    box-shadow: none !important;
}}

/* Left-side sidebar toggle (>>): always visible, clickable and fixed at top-left */
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {{
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    position: fixed !important;
    top: 12px !important;
    left: 12px !important;
    z-index: 1000000 !important;
    background-color: {border_color} !important;
    border-radius: 8px !important;
}}
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapseButton"] button {{
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
}}
[data-testid="stSidebarCollapsedControl"] *,
[data-testid="collapsedControl"] *,
[data-testid="stExpandSidebarButton"] *,
[data-testid="stSidebarCollapseButton"] * {{
    color: {text_color} !important;
    fill: {text_color} !important;
    visibility: visible !important;
}}

/* Widget labels follow the app's own Light/Dark theme (never invisible) */
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label, [data-testid="stCaptionContainer"] * {{ color: {text_color} !important; }}

.block-container {{ padding-top: 3rem !important; padding-bottom: 6rem !important; max-width: 850px !important; margin: 0 auto !important; }}
.stButton>button[kind="primary"] {{ background: #4D6BFE; border-radius: 10px; height: 40px; font-weight: 600; border: 0; color: white; }}
.stButton>button[kind="secondary"] {{ background: {input_bg}; border: 1px solid {border_color}; border-radius: 10px; color: {text_color}; padding: 5px; font-size: 13px; }}

div[data-testid="stChatMessage"] {{ background-color: transparent; padding: 10px 0; border: none; }}
div[data-testid="stChatMessage"] h1, div[data-testid="stChatMessage"] h2, div[data-testid="stChatMessage"] h3, div[data-testid="stChatMessage"] h4, div[data-testid="stChatMessage"] strong {{ color: {text_color} !important; margin-top: 15px !important; margin-bottom: 10px !important; }}
div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li {{ color: {text_color} !important; font-size: 15px !important; line-height: 1.6; }}

div[data-testid="stChatMessage"] table {{ display: block !important; overflow-x: auto !important; border-collapse: collapse !important; margin: 15px 0 !important; width: 100% !important; }}
div[data-testid="stChatMessage"] table th, div[data-testid="stChatMessage"] table td {{ color: {text_color} !important; border: 1px solid {border_color} !important; padding: 10px !important; background-color: {input_bg} !important; }}

div[data-testid="stChatMessage"] pre {{ background-color: {input_bg} !important; border: 1px solid {border_color} !important; border-radius: 8px !important; padding: 12px !important; }}
div[data-testid="stChatMessage"] code {{ color: #DC2626 !important; background-color: transparent !important; font-family: 'Courier New', monospace !important; }}

div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {{ flex-direction: row-reverse; text-align: right; margin-left: auto; margin-right: 0; width: fit-content; max-width: 85%; }}
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) .stMarkdown {{ background: {input_bg}; border: 1px solid {border_color}; padding: 12px 18px; border-radius: 20px 20px 4px 20px; display: inline-block; }}
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {{ margin-right: auto; margin-left: 0; width: 100%; }}
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) .stMarkdown {{ background: {card_bg}; border: 1px solid {border_color}; padding: 18px 20px; border-radius: 20px 20px 20px 4px; display: inline-block; box-shadow: 0 2px 8px rgba(0,0,0,0.04); width: 100%; }}

div[data-testid="stTextInput"] input {{ background-color: {input_bg} !important; color: {text_color} !important; border: 1px solid {border_color} !important; border-radius: 10px !important; }}
div[data-testid="stChatInput"] {{ background-color: {card_bg} !important; border-radius: 12px !important; border: 1px solid {border_color} !important; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
div[data-testid="stChatInput"] > div {{ background-color: {card_bg} !important; }}
div[data-testid="stChatInput"] textarea {{ color: {text_color} !important; background-color: transparent !important; }}
div[data-testid="stChatInput"] button {{ background: #4D6BFE !important; border-radius: 8px !important; }}
div[data-testid="stChatInput"] button svg {{ fill: white !important; }}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{ background-color: {input_bg} !important; color: {text_color} !important; border: 1px solid {border_color} !important; }}

.sidebar-title {{ font-size: 20px; font-weight: 700; color: {text_color}; margin: 0; }}
.sidebar-subtitle {{ font-size: 10px; color: #6B7280; letter-spacing: 1.5px; margin-top: 5px; }}
.divider {{ border-top: 1px solid {border_color}; margin: 15px 0; }}
.label-text {{ font-size: 12px; color: #6B7280; margin-bottom: 8px; font-weight: 600; text-transform: uppercase; }}
.user-card {{ display: flex; align-items: center; background: {input_bg}; padding: 10px; border-radius: 10px; border: 1px solid {border_color}; margin-bottom: 10px; }}
.user-avatar {{ background: #4D6BFE; color: white; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; margin-right: 12px; }}
.user-email {{ font-size: 12px; color: {text_color}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
</style>
"""

# ================= ৫. লগইন পেজ =================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
# Restore login only from a SIGNED cookie (30-day maximum). Unsigned/forged cookies are ignored.
if not st.session_state.logged_in and cookies is not None and not st.session_state.get("just_logged_out"):
    try:
        saved_email = read_auth_cookie(cookies.get("asikera_auth") or "")
        if saved_email:
            st.session_state.logged_in = True
            st.session_state.user_email = saved_email
    except Exception:
        pass

if not st.session_state.logged_in:
    if not supabase:
        st.warning("Supabase configuration is missing. Add SUPABASE_URL and SUPABASE_KEY in Streamlit Secrets before using login/signup.")
    st.markdown(custom_css, unsafe_allow_html=True)  # hides Share/Fork/Edit on the login page too
    st.markdown("""
    <style>
    .stApp { background: radial-gradient(circle at 10% 20%, rgba(139, 92, 246, 0.25), transparent 40%), radial-gradient(circle at 90% 80%, rgba(59, 130, 246, 0.25), transparent 40%), #0B0F17 !important; }
    /* One centered column on phone and desktop */
    .block-container { max-width: 440px !important; margin: 0 auto !important; padding: 2.5rem 1rem 3rem !important; }
    /* All login text is white */
    .login-hero, .login-hero * { color: #FFFFFF !important; }
    .login-hero .login-sub { color: #AEB6C8 !important; }
    div[data-testid="stForm"] { background: rgba(20, 26, 38, 0.95) !important; border: 1px solid #2A3550 !important; border-radius: 20px !important; padding: 24px !important; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.35) !important; }
    div[data-testid="stForm"], div[data-testid="stForm"] *, div[data-testid="stTabs"] [data-baseweb="tab"] p, div[data-testid="stTabs"] label { color: #FFFFFF !important; }
    div[data-baseweb="input"], div[data-baseweb="base-input"] { background-color: #1B2332 !important; border-color: #2A3550 !important; }
    div[data-testid="stTextInput"] input, div[data-baseweb="input"] input { background-color: #1B2332 !important; color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important; caret-color: #FFFFFF !important; border: 1px solid #2A3550 !important; }
    div[data-testid="stTextInput"] input::placeholder { color: #AEB6C8 !important; -webkit-text-fill-color: #AEB6C8 !important; opacity: 1 !important; }
    div[data-testid="stForm"] svg { fill: #FFFFFF !important; color: #FFFFFF !important; }
    div[data-testid="stFormSubmitButton"] > button { background: linear-gradient(135deg, #8B5CF6, #3B82F6) !important; border: none !important; color: #FFFFFF !important; font-weight: 600 !important; min-height: 46px !important; }
    div[data-testid="stFormSubmitButton"] > button * { color: #FFFFFF !important; }
    [data-baseweb="tab-highlight"] { background-color: #8B5CF6 !important; }
    @media (max-width: 640px) { .block-container { padding-left: 0.9rem !important; padding-right: 0.9rem !important; } div[data-testid="stForm"] { padding: 18px !important; } }
    st.markdown("""
<style>
/* উপরের ডানদিকের Share, star, edit, GitHub, মেনু */
[data-testid="stToolbar"] {display: none !important;}
[data-testid="stAppDeployButton"] {display: none !important;}
[data-testid="stStatusWidget"] {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
#MainMenu {visibility: hidden !important;}
footer {visibility: hidden !important;}

/* header পুরো লুকাবেন না, নইলে মোবাইলে সাইডবার বোতাম হারিয়ে যায় */
header[data-testid="stHeader"] {background: transparent !important;}
[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
}
</style>
""", unsafe_allow_html=True)
    </style

    login_container = st.container()
    with login_container:
        st.markdown("""<div class="login-hero" style='text-align:center;padding:10px 0 22px;'><div style='font-size:36px;font-weight:850;letter-spacing:-1px;'>⚡ ASIKERA AI</div><div class="login-sub" style='letter-spacing:3px;font-size:10px;margin-top:4px;'>ASIKUL'S KNOWLEDGE ERA</div><p style='font-size:14px;margin:16px auto 8px;'>One workspace for learning, writing, coding, research and everyday questions.</p><div style='display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-top:14px;'><span style='border:1px solid #3A4560;border-radius:20px;padding:6px 10px;font-size:12px;'>✦ AI Chat</span><span style='border:1px solid #3A4560;border-radius:20px;padding:6px 10px;font-size:12px;'>📚 Learning tools</span><span style='border:1px solid #3A4560;border-radius:20px;padding:6px 10px;font-size:12px;'>🔒 Private account</span></div></div>""", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Sign in", "Create account"])
        with tab1:
            with st.form("login_form"):
                l_email = st.text_input("Email", placeholder="you@company.com")
                l_pass = st.text_input("Password", type="password", placeholder="••••••••")
                if st.form_submit_button("Login", use_container_width=True):
                    if login_user(l_email, l_pass):
                        st.session_state.logged_in = True
                        st.session_state.user_email = l_email.strip().lower()
                        st.session_state.just_logged_out = False
                        if cookies is not None and _cookie_secret():
                            try:
                                cookies.set("asikera_auth", make_auth_cookie(st.session_state.user_email), expires_at=datetime.datetime.now() + datetime.timedelta(days=30), key="set_auth_cookie")
                                time.sleep(0.6)
                            except Exception:
                                pass
                        st.rerun()
                    else: st.error("Invalid credentials.")
        with tab2:
            with st.form("signup_form"):
                s_email = st.text_input("Email", placeholder="you@company.com")
                s_pass = st.text_input("Password", type="password", placeholder="Min 6 characters")
                if st.form_submit_button("Sign Up", use_container_width=True):
                    if len(s_pass) < 6: st.warning("Password too short.")
                    elif create_user(s_email, s_pass): st.success("Account created! Please login.")
                    else: st.error("Email already registered.")
    st.stop()

# ================= ৬. মেইন অ্যাপ লজিক =================
st.markdown(custom_css, unsafe_allow_html=True)

if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_chats(st.session_state.user_email)
if "current_session" not in st.session_state:
    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]

CATEGORIES = [
    "💬 General Chat", "🎓 English Tutor", "👨‍💻 Coding Assistant", 
    "📚 Learning & Study", "✍️ Writing & Editing", "🔍 Deep Research", 
    "🎨 Image Generation", "📄 File/PDF Analyzer", "🌐 Web Search", 
    "📊 Data Analysis", "🌍 Translator", "🔗 URL Reader", 
    "🤖 Custom Persona", "📝 Text Summarizer", "💡 Idea Generator",
    "📧 Email Writer", "📱 Social Media Post", "📖 Story Writer",
    "🎯 IELTS Writing Evaluator", "🗣️ Interview Preparer",
    "✈️ Travel Planner", "🍳 Recipe Creator", "💪 Fitness Coach",
    "🧠 Psychology Advisor", "⚖️ Legal Advisor (Basic)",
    "🎬 Movie Recommender", "🎵 Music Recommender",
    "💰 Finance Advisor", "📈 Marketing Strategist",
    "🛠️ Task Automation"
]

with st.sidebar:
    col_logo, col_text = st.columns([1, 3])
    with col_logo:
        try: st.image("logo.png", use_container_width=True)
        except: st.markdown("⚡")
    with col_text:
        st.markdown(f"""<div style='padding-top: 5px;'><div class="sidebar-title">ASIKERA</div><div class="sidebar-subtitle">KNOWLEDGE ERA</div></div>""", unsafe_allow_html=True)
        
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
    free_categories = [
        "💬 General Chat", "🎓 English Tutor", "👨‍💻 Coding Assistant",
        "📚 Learning & Study", "✍️ Writing & Editing", "📝 Text Summarizer",
        "💡 Idea Generator", "📧 Email Writer", "📖 Story Writer"
    ]
    mode_options = CATEGORIES if premium_for_modes else free_categories
    selected_category = st.selectbox("Select Mode", mode_options, label_visibility="collapsed")
    if not premium_for_modes:
        st.caption("Free plan: 9 basic modes. Premium unlocks all 30+ modes and advanced tools.")
    
    theme_toggle = st.checkbox("🌙 Dark Mode" if st.session_state.theme == "Light" else "☀️ Light Mode")
    if theme_toggle:
        st.session_state.theme = "Dark" if st.session_state.theme == "Light" else "Light"
        st.rerun()
        
    voice_gender = st.radio("Voice", ["Female", "Male"], horizontal=True)
    chat_provider = st.selectbox("AI Engine", ["Fast", "Smart"], index=0, help="Choose the ASIKERA Fast or Smart engine.")
    
    custom_persona = ""
    if selected_category == "🤖 Custom Persona":
        custom_persona = st.text_area("Define AI Personality:", "You are a helpful assistant.")
    
    # প্রম্পট ইঞ্জিন
    base_identity = "You are ASIKERA. Do not mention OpenAI or Google. "
    prompts = {
        "🎓 English Tutor": "You are Sir English, an elite IELTS examiner. Correct grammar, explain in Bengali.",
        "👨‍💻 Coding Assistant": "You are an expert programmer. Write clean, optimized code.",
        "📚 Learning & Study": "You are a brilliant tutor. Explain concepts simply.",
        "✍️ Writing & Editing": "You are a professional editor. Fix grammar and improve tone.",
        "🔍 Deep Research": "You are a deep research agent. Synthesize detailed reports.",
        "📝 Text Summarizer": "You are an expert summarizer. Extract key points into bullet points.",
        "💡 Idea Generator": "You are a creative brainstormer. Generate 10 unique ideas.",
        "📧 Email Writer": "You are a professional email writer. Write clear and polite emails.",
        "📱 Social Media Post": "You are a viral social media manager. Write engaging posts with emojis.",
        "📖 Story Writer": "You are a creative novelist. Write engaging stories.",
        "🎯 IELTS Writing Evaluator": "You are an IELTS examiner. Grade the writing on a 1-9 scale and explain errors.",
        "🗣️ Interview Preparer": "You are an HR manager. Ask interview questions and evaluate the answers.",
        "✈️ Travel Planner": "You are a travel agent. Create detailed itineraries.",
        "🍳 Recipe Creator": "You are a master chef. Provide recipes with ingredients and steps.",
        "💪 Fitness Coach": "You are a fitness coach. Provide workout plans and diet advice.",
        "🧠 Psychology Advisor": "You are a compassionate psychologist. Provide emotional support.",
        "⚖️ Legal Advisor (Basic)": "You are a legal advisor. Provide general legal information.",
        "🎬 Movie Recommender": "You are a movie buff. Recommend movies based on preferences.",
        "🎵 Music Recommender": "You are a music expert. Recommend songs.",
        "💰 Finance Advisor": "You are a financial advisor. Provide money-saving and investment tips.",
        "📈 Marketing Strategist": "You are a marketing expert. Create marketing plans.",
        "🛠️ Task Automation": "You are an automation expert. Create step-by-step workflows.",
        "🤖 Custom Persona": custom_persona if custom_persona else "You are a smart AI."
    }
    persona_prompt = base_identity + prompts.get(selected_category, "You are a smart and helpful AI.")

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
    
    # Subscription panel
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown("### 👑 ASIKERA Premium")
    active_sub = get_subscription(st.session_state.user_email)
    used_today = daily_usage(st.session_state.user_email)
    if active_sub:
        st.success(f"Premium active · {active_sub['plan']}\nExpires: {str(active_sub['expires_at'])[:10]}")
        st.caption("Premium includes all modes, file/PDF analysis, image generation, voice input and higher usage allowance (fair-use applies).")
    else:
        st.info(f"Free plan · {used_today}/{FREE_DAILY_LIMIT} messages used today (UTC)")
        with st.expander("Upgrade to Premium", expanded=False):
            chosen_plan = st.selectbox("Choose a plan", list(PLANS.keys()), format_func=lambda x: f"{x} — ৳{PLANS[x]['bdt']} / ${PLANS[x]['usd']}")
            chosen_method = st.selectbox("Payment method", list(PAYMENT_DETAILS.keys()))
            st.code(PAYMENT_DETAILS[chosen_method])
            st.caption("Send the exact plan amount using the selected method. For crypto, verify the network before sending. Payments are manually reviewed; do not send extra funds.")
            txn_ref = st.text_input("Transaction ID / payment reference", key="premium_txn_ref")
            proof_file = st.file_uploader("Payment screenshot (PNG/JPG, max 5 MB)", type=["png", "jpg", "jpeg"], key=f"premium_proof_{st.session_state.get('proof_key', 0)}")
            if proof_file is not None:
                st.image(proof_file, caption="Screenshot preview", use_container_width=True)
            if st.button("Submit payment for approval", use_container_width=True, type="primary"):
                ok, msg = submit_payment_request(st.session_state.user_email, chosen_plan, chosen_method, txn_ref, proof_file)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.session_state.proof_key = st.session_state.get("proof_key", 0) + 1
            if supabase:
                try:
                    mine = supabase.table("payment_requests").select("plan,payment_method,status,created_at").eq("user_email", st.session_state.user_email.lower()).order("created_at", desc=True).limit(5).execute().data or []
                    if mine:
                        st.caption("Recent payment requests")
                        for req in mine:
                            st.write(f"{req['plan']} · {req['payment_method']} · {req['status']}")
                except Exception:
                    pass

    if is_admin(st.session_state.user_email):
        with st.expander("🛡️ Admin: payment approvals"):
            if not supabase:
                st.error("Supabase is not configured.")
            else:
                try:
                    pending = supabase.table("payment_requests").select("id,user_email,plan,payment_method,transaction_ref,amount_bdt,amount_usd,created_at,proof_url").eq("status", "pending").order("created_at", desc=False).execute().data or []
                    if not pending:
                        st.caption("No pending payment requests.")
                    for req in pending:
                        st.markdown(f"**{req['user_email']}** · {req['plan']} · {req['payment_method']}")
                        st.caption(f"Ref: {req['transaction_ref']} | ৳{req['amount_bdt']} / ${req['amount_usd']} | {req['created_at']}")
                        if req.get("proof_url"):
                            st.image(req["proof_url"], caption="Payment screenshot", use_container_width=True)
                            st.markdown(f"[Open full size]({req['proof_url']})")
                        else:
                            st.caption("No screenshot uploaded.")
                        if st.button("Approve payment", key=f"approve_{req['id']}", type="primary"):
                            ok, msg = approve_payment_request(req["id"], st.session_state.user_email)
                            (st.success if ok else st.error)(msg)
                            st.rerun()
                except Exception:
                    st.warning("Run supabase_subscription.sql and check the server-side Supabase key permissions.")

    if st.button("Logout", use_container_width=True, type="secondary"):
        st.session_state.logged_in = False
        st.session_state.user_email = ""
        st.session_state.just_logged_out = True
        if cookies is not None:
            try:
                cookies.delete("asikera_auth", key="del_auth_cookie")
                time.sleep(0.6)
            except Exception:
                pass
        st.session_state.pop("chat_sessions", None)
        st.session_state.pop("current_session", None)
        st.rerun()

# ================= ৭. ডাইনামিক টুলস এক্সিকিউশন =================
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

if selected_category == "🎨 Image Generation":
    if not get_subscription(st.session_state.user_email):
        st.warning("🎨 Image Generation is a Premium feature. Upgrade from the sidebar to unlock it.")
        st.stop()
    st.markdown("### 🎨 AI Image Generator")
    img_prompt = st.text_input("Describe your image:")
    if st.button("Generate Image", type="primary") and img_prompt:
        with st.spinner("Painting..."):
            image_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(img_prompt)}?width=1024&height=1024&nologo=true"
            st.image(image_url, use_container_width=True)

elif selected_category == "📄 File/PDF Analyzer":
    if not get_subscription(st.session_state.user_email):
        st.warning("📄 File/PDF analysis is a Premium feature. Upgrade from the sidebar to unlock it.")
        st.stop()
    st.markdown("### 📄 File Analyzer")
    uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
    file_query = st.text_input("What do you want to know about this file?")
    if st.button("Analyze File", type="primary") and uploaded_file and file_query:
        with st.spinner("Analyzing..."):
            try:
                if not GEMINI_API_KEY:
                    raise RuntimeError("Add GEMINI_API_KEY to Streamlit Secrets.")
                gemini_model = genai.GenerativeModel(get_secret("GEMINI_MODEL", "gemini-2.5-flash"))
                response = gemini_model.generate_content([file_query, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
                st.markdown(response.text)
            except Exception as e: st.error(f"Error: {e}")

elif selected_category == "📊 Data Analysis":
    st.markdown("### 📊 Data Visualization")
    csv_file = st.file_uploader("Upload CSV", type=["csv"])
    if csv_file:
        df = pd.read_csv(csv_file)
        st.write("Data Preview:", df.head())
        chart_prompt = st.text_input("Ask AI to draw a chart (e.g., 'Draw a bar chart of Sales')")
        if st.button("Generate Chart", type="primary") and chart_prompt:
            with st.spinner("Generating..."):
                try:
                    if not groq_client:
                        st.error("Chart AI needs GROQ_API_KEY in Streamlit Secrets.")
                    else:
                        sys_prompt = ("Return ONLY valid JSON with keys chart_type, x, y. "
                                      "chart_type must be one of bar, line, scatter, histogram, pie, box. "
                                      f"x and y must be exact column names from {list(df.columns)}. "
                                      "For histogram use x as the numeric column and y as null. For pie use categorical x and numeric y.")
                        res = groq_client.chat.completions.create(model=get_secret("GROQ_MODEL", "openai/gpt-oss-120b"), messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": chart_prompt}], temperature=0.1)
                        spec = json.loads(res.choices[0].message.content.strip().replace("```json", "").replace("```", ""))
                        chart_type = spec.get("chart_type")
                        x_col, y_col = spec.get("x"), spec.get("y")
                        allowed = {"bar": px.bar, "line": px.line, "scatter": px.scatter, "histogram": px.histogram, "pie": px.pie, "box": px.box}
                        if chart_type not in allowed or x_col not in df.columns or (y_col is not None and y_col not in df.columns):
                            st.error("The chart suggestion used an unsupported chart type or column. Please rephrase your request.")
                        else:
                            kwargs = {"x": x_col}
                            if chart_type != "histogram" and y_col is not None:
                                kwargs["y"] = y_col
                            fig = allowed[chart_type](df, **kwargs, title=chart_prompt)
                            st.plotly_chart(fig, use_container_width=True)
                except Exception as e: st.error(f"Error: {e}")

elif selected_category == "🌐 Web Search":
    st.markdown("### 🌐 Live Web Search")
    search_query = st.text_input("Search the web:")
    if st.button("Search", type="primary") and search_query:
        with st.spinner("Searching..."):
            try:
                results = list(DDGS().text(search_query, max_results=4))
                if results:
                    context = "\n".join([f"Snippet: {r['body']}" for r in results])
                    res = groq_client.chat.completions.create(model=get_secret("GROQ_MODEL", "openai/gpt-oss-120b"), messages=[{"role": "system", "content": f"Answer based on these search results:\n{context}"}, {"role": "user", "content": search_query}])
                    st.markdown(res.choices[0].message.content)
            except Exception as e: st.error(f"Error: {e}")

elif selected_category == "🔍 Deep Research":
    st.markdown("### 🔍 Agentic Deep Research")
    research_prompt = st.text_input("What should I research?")
    if st.button("Start Research", type="primary") and research_prompt:
        with st.spinner("Browsing live internet and generating report..."):
            try:
                query_gen = groq_client.chat.completions.create(model=get_secret("GROQ_MODEL", "openai/gpt-oss-120b"), messages=[{"role": "system", "content": "Generate 3 search queries based on this topic. Output ONLY the queries separated by newlines."}, {"role": "user", "content": research_prompt}])
                queries = query_gen.choices[0].message.content.strip().split('\n')
                all_results = []
                for q in queries:
                    if q.strip():
                        res = list(DDGS().text(q, max_results=3))
                        all_results.extend(res)
                context = "\n".join([f"Title: {r['title']}\nSnippet: {r['body']}" for r in all_results])
                final_report = groq_client.chat.completions.create(model=get_secret("GROQ_MODEL", "openai/gpt-oss-120b"), messages=[{"role": "system", "content": "Synthesize into a highly detailed report with headings."}, {"role": "user", "content": f"Topic: {research_prompt}\n\nResults:\n{context}"}], temperature=0.5, max_tokens=2000)
                st.markdown(final_report.choices[0].message.content)
            except Exception as e: st.error(f"Error: {e}")

elif selected_category == "🌍 Translator":
    st.markdown("### 🌍 Language Translator")
    col1, col2 = st.columns(2)
    with col1: src_lang = st.selectbox("From", ["Auto-Detect", "Bengali", "English", "Hindi", "Arabic"])
    with col2: tgt_lang = st.selectbox("To", ["English", "Bengali", "Hindi", "Arabic", "Spanish"])
    text_to_translate = st.text_area("Enter text to translate:")
    if st.button("Translate", type="primary") and text_to_translate:
        with st.spinner("Translating..."):
            prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Only output the translation: \n\n{text_to_translate}"
            res = groq_client.chat.completions.create(model=get_secret("GROQ_MODEL", "openai/gpt-oss-120b"), messages=[{"role": "user", "content": prompt}])
            st.success(res.choices[0].message.content)

elif selected_category == "🔗 URL Reader":
    st.markdown("### 🔗 URL Reader")
    url_input = st.text_input("Paste a website link here:")
    url_query = st.text_input("What do you want to know about this page?")
    if st.button("Read URL", type="primary") and url_input:
        with st.spinner("Reading webpage..."):
            try:
                parsed = urlparse(url_input.strip())
                if parsed.scheme not in ("http", "https") or not parsed.hostname:
                    raise ValueError("Please enter a valid http:// or https:// URL.")
                host = parsed.hostname.lower()
                if host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith((".local", ".internal")):
                    raise ValueError("Local or internal URLs are not allowed.")
                headers = {'User-Agent': 'Mozilla/5.0'}
                page = requests.get(url_input, headers=headers, timeout=10, allow_redirects=False)
                page.raise_for_status()
                soup = BeautifulSoup(page.content, 'html.parser')
                text = soup.get_text(separator=' ', strip=True)[:5000]
                prompt = f"Based on the following website content, answer this: {url_query if url_query else 'Summarize this page'}\n\nContent:\n{text}"
                res = groq_client.chat.completions.create(model=get_secret("GROQ_MODEL", "openai/gpt-oss-120b"), messages=[{"role": "user", "content": prompt}])
                st.markdown(res.choices[0].message.content)
            except Exception as e: st.error(f"Failed to read URL: {e}")

else:
    # চ্যাট ইন্টারফেস
    for m in current_messages:
        avatar_ai = "logo.png" if "logo.png" else "✨"
        avatar = avatar_ai if m["role"] == "assistant" else "👤"
        with st.chat_message(m["role"], avatar=avatar):
            st.markdown(m["content"])

    active_sub_for_chat = bool(get_subscription(st.session_state.user_email))
    with st.expander("🎤 Voice & Image (Premium)", expanded=False):
        if active_sub_for_chat:
            audio_value = st.audio_input("Record a voice message")
            uploaded_image = st.file_uploader("Attach an image", type=["png", "jpg", "jpeg"], key="chat_image_upload")
            st.caption("You can send text, voice, an image, or combine text with an image.")
        else:
            audio_value = None
            uploaded_image = None
            st.caption("Voice and image understanding are Premium features. Upgrade in the sidebar to unlock them.")
    prompt = st.chat_input("Ask ASIKERA anything...")
    send_attachment = st.button("Send voice / image", type="secondary", disabled=(not active_sub_for_chat or (audio_value is None and uploaded_image is None)))
    if prompt or send_attachment:
        active_sub_for_chat = bool(get_subscription(st.session_state.user_email))
        has_attachment = bool(uploaded_image or audio_value)
        if not active_sub_for_chat and daily_usage(st.session_state.user_email) >= FREE_DAILY_LIMIT:
            st.warning("You have reached the free daily limit of 10 requests. Upgrade to Premium from the sidebar to continue.")
            st.stop()
        if has_attachment and not active_sub_for_chat:
            st.warning("Voice and image requests require Premium.")
            st.stop()
        user_text = (prompt or "").strip()
        if audio_value:
            if not groq_client:
                st.error("Voice transcription needs GROQ_API_KEY in Streamlit Secrets.")
                st.stop()
            with st.spinner("Transcribing voice..."):
                try:
                    audio_bytes = audio_value.getvalue()
                    transcript = groq_client.audio.transcriptions.create(file=("voice.wav", audio_bytes), model="whisper-large-v3").text
                    user_text = (user_text + "\n\n" + transcript).strip() if user_text else transcript.strip()
                except Exception as exc:
                    st.error(f"Voice transcription failed: {exc}")
                    st.stop()
        if uploaded_image and not user_text:
            user_text = "Please describe and analyze this image."
        if not user_text:
            st.warning("Write a message or attach a voice recording/image first.")
            st.stop()
        current_messages.append({"role":"user","content":user_text + ("\n\n[Image attached]" if uploaded_image else "")})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_text)
            if uploaded_image:
                st.image(uploaded_image, caption="Attached image", use_container_width=True)
        with st.chat_message("assistant", avatar="✨"):
            with st.spinner("Thinking..."):
                try:
                    if uploaded_image:
                        if not GEMINI_API_KEY:
                            raise RuntimeError("Image understanding needs GEMINI_API_KEY in Streamlit Secrets.")
                        gemini_model = genai.GenerativeModel(get_secret("GEMINI_MODEL", "gemini-2.5-flash"))
                        response = gemini_model.generate_content([user_text, {"mime_type": uploaded_image.type, "data": uploaded_image.getvalue()}])
                        reply = response.text or "I couldn't read a response. Please try again."
                        st.markdown(reply)
                    elif chat_provider == "Smart":
                        if not GEMINI_API_KEY:
                            raise RuntimeError("Smart engine is not configured. Add GEMINI_API_KEY to Streamlit Secrets.")
                        history_text = "\n\n".join(f"{m['role'].upper()}: {m['content']}" for m in current_messages[-10:])
                        gemini_model = genai.GenerativeModel(get_secret("GEMINI_MODEL", "gemini-2.5-flash"), system_instruction=persona_prompt)
                        response = gemini_model.generate_content(history_text + "\n\nASSISTANT:")
                        reply = response.text or "I couldn't read a response. Please try again."
                        st.markdown(reply)
                    else:
                        if not groq_client:
                            raise RuntimeError("Fast engine is not configured. Add GROQ_API_KEY in Streamlit Secrets.")
                        system_msg = {"role": "system", "content": persona_prompt}
                        stream = groq_client.chat.completions.create(model=get_secret("GROQ_MODEL", "openai/gpt-oss-120b"), messages=[system_msg] + current_messages[-10:], temperature=0.7, max_tokens=1500, stream=True)
                        reply = st.write_stream(chunk.choices[0].delta.content for chunk in stream if chunk.choices[0].delta.content)
                except Exception as exc:
                    reply = "Sorry, I couldn't process that request. Please check the AI provider configuration and try again."
                    st.error(str(exc))
            current_messages.append({"role":"assistant","content":reply})
            save_chat(st.session_state.user_email, st.session_state.current_session, current_messages)
            # Count every successful request type against the same free daily quota.
            if not active_sub_for_chat and not reply.startswith("Sorry, I couldn't process"):
                if not increment_daily_usage(st.session_state.user_email):
                    st.warning("Your reply was generated, but daily usage could not be saved. Check the Supabase daily_usage table.")
            audio_data = generate_audio_edge(reply, voice_gender)
            if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)
