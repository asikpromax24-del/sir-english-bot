import streamlit as st
from groq import Groq
import google.generativeai as genai
from ddgs import DDGS
import urllib.parse
import edge_tts, asyncio, io
from langdetect import detect
import hashlib
from supabase import create_client, Client

st.set_page_config(page_title="Super AI Pro", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

# ========== PRO CSS - ENTRY + MAIN FIXED ==========
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
.stApp { background: #0A0A0A; font-family: 'Inter'; }
[data-testid="stSidebar"] { background: #111111; border-right: 1px solid #222; }
#MainMenu, footer {visibility: hidden;}

/* Entry Card */
.entry-card {
    background: rgba(22,22,22,0.9); backdrop-filter: blur(20px);
    border: 1px solid #2A2A2A; border-radius: 24px;
    padding: 32px; box-shadow: 0 20px 60px rgba(0,0,0,0.6);
    max-width: 440px; margin: 40px auto;
}
.gradient-btn {
    background: linear-gradient(135deg, #7C3AED, #3B82F6);
    color: white; border: 0; height: 48px; border-radius: 12px;
    font-weight: 700; width: 100%;
}
.stTextInput input {
    background: #1A1A1A !important; border: 1px solid #2A2A2A !important;
    border-radius: 12px !important; color: white !important; height: 48px;
}
div[data-testid="stChatInput"] { background: #1A1A1A !important; border-radius: 24px !important; border: 1px solid #333 !important; }
</style>
""", unsafe_allow_html=True)

# Backend
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def make_hashes(p): return hashlib.sha256(str.encode(p)).hexdigest()
def create_user(e,p):
    try: supabase.table("users").insert({"email":e,"password":make_hashes(p)}).execute(); return True
    except: return False
def login_user(e,p):
    r = supabase.table("users").select("password").eq("email",e).execute()
    return r.data and r.data[0]["password"] == make_hashes(p)
def save_chat(e,s,m):
    try:
        supabase.table("chats").delete().eq("user_email",e).eq("session_name",s).execute()
        supabase.table("chats").insert({"user_email":e,"session_name":s,"messages":m}).execute()
    except: pass
def load_chats(e):
    r = supabase.table("chats").select("session_name, messages").eq("user_email",e).execute()
    return {row["session_name"]:row["messages"] for row in r.data} if r.data else {"New Chat":[]}

def generate_audio(text):
    try: lang = detect(text); voice = 'bn-BD-NabanitaNeural' if lang=='bn' else 'en-US-AriaNeural'
    except: voice='en-US-AriaNeural'
    async def _gen():
        c=edge_tts.Communicate(text,voice); d=b""
        async for chunk in c.stream():
            if chunk["type"]=="audio": d+=chunk["data"]
        return d
    try:
        loop=asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        return io.BytesIO(loop.run_until_complete(_gen()))
    except: return None

if "logged_in" not in st.session_state: st.session_state.logged_in=False
if not st.session_state.logged_in and "email" in st.query_params:
    st.session_state.logged_in=True; st.session_state.user_email=st.query_params["email"]; st.rerun()

# ========== ENTRY UI - PRO VERSION ==========
if not st.session_state.logged_in:
    st.markdown("""
    <div style="text-align:center; padding-top: 30px;">
        <div style="font-size:48px;">✨</div>
        <h1 style="color:white; font-weight:800; margin:10px 0;">Super AI Pro</h1>
        <p style="color:#7C3AED; font-weight:600; letter-spacing:2px; font-size:12px;">PRO • TRENDING FIRST • POPULAR BRAND</p>
        <p style="color:#888;">Your Professional AI Companion</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1,col2,col3 = st.columns([1,1.2,1])
    with col2:
        st.markdown('<div class="entry-card">', unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Sign Up"])
        with tab1:
            l_e = st.text_input("Email Address", placeholder="you@example.com", key="l_e")
            l_p = st.text_input("Password", type="password", placeholder="••••••••", key="l_p")
            if st.button("Login to Super AI →", use_container_width=True, type="primary"):
                if login_user(l_e,l_p):
                    st.session_state.logged_in=True; st.session_state.user_email=l_e
                    st.query_params["email"]=l_e; st.rerun()
                else: st.error("Invalid credentials")
        with tab2:
            s_e = st.text_input("Email Address", placeholder="you@example.com", key="s_e")
            s_p = st.text_input("Password", type="password", placeholder="Create password", key="s_p")
            if st.button("Create Account", use_container_width=True, type="primary"):
                if create_user(s_e,s_p): st.success("Account created! Now login.")
                else: st.error("Email already exists")
        st.markdown("<p style='text-align:center; color:#555; font-size:11px; margin-top:20px;'>© 2026 Super AI Pro • Built by Asikul Islam</p>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ========== SIDEBAR ==========
if "chat_sessions" not in st.session_state: st.session_state.chat_sessions=load_chats(st.session_state.user_email)
if "current_session" not in st.session_state: st.session_state.current_session=list(st.session_state.chat_sessions.keys())[0]

with st.sidebar:
    st.markdown("## ✨ Super AI")
    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        nid=f"Chat {len(st.session_state.chat_sessions)+1}"; st.session_state.chat_sessions[nid]=[]; st.session_state.current_session=nid; st.rerun()
    search=st.text_input("Search", placeholder="🔍 Search chats...", label_visibility="collapsed")
    st.divider()
    st.markdown("**🎭 Choose AI Version**")
    persona = st.radio("", ["🚀 Nova (Smart & Fast)", "😎 Vibe (Friendly)", "🧑‍🏫 Pro (Professional)", "📚 Sir English"], label_visibility="collapsed")
    if "Sir English" in persona: sys_prompt="You are Sir English, strict English teacher, explain in Bengali"
    elif "Vibe" in persona: sys_prompt="You are Vibe, friendly, witty, use emojis"
    elif "Pro" in persona: sys_prompt="You are Pro AI, professional, detailed"
    else: sys_prompt="You are Nova, smart and fast"
    st.divider()
    tool=st.selectbox("🛠️ Tools", ["💬 Chat", "🖼️ Image Gen", "📄 File Analyzer", "🌐 Web Search"])
    st.divider()
    st.markdown("**💬 Recent**")
    for s in [x for x in st.session_state.chat_sessions if search.lower() in x.lower()]:
        if st.button(f"💬 {s}", key=s, use_container_width=True): st.session_state.current_session=s; st.rerun()
    st.divider()
    if st.button("🚪 Logout", use_container_width=True): st.session_state.logged_in=False; st.query_params.clear(); st.rerun()

# ========== MAIN CHAT - ERROR FIXED ==========
msgs=st.session_state.chat_sessions[st.session_state.current_session]
if not msgs: st.markdown(f"<div style='text-align:center; padding:60px;'><h2 style='color:white;'>How can I help you today?</h2><p style='color:#666;'>{persona}</p></div>", unsafe_allow_html=True)

if tool=="💬 Chat":
    for m in msgs:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    if prompt:=st.chat_input("Ask anything..."):
        msgs.append({"role":"user","content":prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            try:
                # FIXED MODEL - 2 model fallback
                models_to_try = ["llama-3.1-8b-instant", "gemma2-9b-it", "llama3-8b-8192"]
                reply=""
                for model_name in models_to_try:
                    try:
                        stream = groq_client.chat.completions.create(model=model_name, messages=[{"role":"system","content":sys_prompt}]+msgs[-8:], stream=True, temperature=0.7)
                        reply = st.write_stream(c.choices[0].delta.content for c in stream if c.choices[0].delta.content)
                        break
                    except: continue
                if not reply: reply="Sorry, model busy. Try again."
            except Exception as e:
                reply=f"Error: {e}"
            msgs.append({"role":"assistant","content":reply}); save_chat(st.session_state.user_email, st.session_state.current_session, msgs)
            audio=generate_audio(reply)
            if audio: st.audio(audio, format="audio/mp3", autoplay=True)
