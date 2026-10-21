
import streamlit as st
from groq import Groq
import time

st.set_page_config(page_title="ASIKERA AI", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# ===== PRO CSS - ALL PAGES =====
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
* { font-family: 'Inter' !important; }
.stApp { background: #070709 !important; }
#MainMenu, footer, header {visibility: hidden;}
[data-testid="stHeader"] { display: none; }
[data-testid="stSidebar"] { background: #0F0F0F !important; border-right: 1px solid #1E1E1E !important; }

/* Buttons */
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, #8B5CF6 0%, #3B82F6 100%) !important;
    border-radius: 12px !important; border: 0 !important; color: white !important;
    font-weight: 700 !important; height: 48px !important;
    box-shadow: 0 8px 20px rgba(139,92,246,0.35);
}
.stButton button[kind="secondary"] {
    background: #1A1A1E !important; border: 1px solid #2A2A2A !important;
    border-radius: 10px !important; color: #CCC !important;
}

/* Inputs */
div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea {
    background: rgba(255,255,255,0.05) !important; border: 1px solid rgba(255,255,255,0.15) !important;
    border-radius: 12px !important; color: white !important; height: 48px !important;
}
div[data-testid="stChatInput"] {
    background: #151518 !important; border: 1px solid #2A2A2A !important; border-radius: 24px !important;
}

/* Blobs */
.blob { position: fixed; border-radius: 50%; filter: blur(80px); opacity: 0.35; z-index: -1; }
.blob1 { width: 500px; height: 500px; background: #7C3AED; left: -120px; top: 100px; }
.blob2 { width: 400px; height: 400px; background: #3B82F6; right: -100px; top: 400px; }

.glass {
    background: rgba(24,24,28,0.85); backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.1); border-radius: 20px;
    padding: 28px; box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}
.feature-card {
    background: rgba(20,20,24,0.8); border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px; padding: 20px; transition: all 0.3s;
}
.feature-card:hover { border-color: #7C3AED; transform: translateY(-2px); }
</style>
<div class="blob blob1"></div><div class="blob blob2"></div>
""", unsafe_allow_html=True)

# Init session
if "page" not in st.session_state: st.session_state.page = "landing"
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "messages" not in st.session_state: st.session_state.messages = []

# Groq client
try:
    groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except:
    groq_client = None

# ===== NAVIGATION FUNCTION =====
def nav_to(p): st.session_state.page = p; st.rerun()

# ===== LANDING PAGE =====
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
        if st.button("View Docs", type="secondary", use_container_width=True): nav_to("chat")
    st.markdown('<p style="text-align:center; color:#666; font-size:12px; margin:16px 0;">• No credit card required • Free plan available • Start in seconds</p>', unsafe_allow_html=True)
    
    st.markdown('<h3 style="text-align:center; color:#A78BFA; font-size:14px; letter-spacing:2px; margin:30px 0 16px;">POWERFUL FEATURES</h3>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="feature-card"><h4 style="color:white; margin:0;">💬 Chat</h4><p style="color:#888; font-size:13px; margin:6px 0 0;">Conversational AI for research, writing, and problem-solving in real time.</p></div>', unsafe_allow_html=True)
        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="feature-card"><h4 style="color:white; margin:0;">📄 File Analyzer</h4><p style="color:#888; font-size:13px; margin:6px 0 0;">Upload PDFs, CSVs, and documents to analyze data and extract key insights.</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="feature-card"><h4 style="color:white; margin:0;">🖼️ Image Gen</h4><p style="color:#888; font-size:13px; margin:6px 0 0;">Create high-quality images from text using advanced generative AI models.</p></div>', unsafe_allow_html=True)
        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
        st.markdown('<div class="feature-card"><h4 style="color:white; margin:0;">🌐 Web Search</h4><p style="color:#888; font-size:13px; margin:6px 0 0;">Search the live web for up-to-date information with sourced answers.</p></div>', unsafe_allow_html=True)
    
    st.markdown('<p style="text-align:center; color:#666; font-size:13px; margin-top:40px;">Trusted by 1,000+ innovators • NOTION • VERCEL • LINEAR • SUPABASE</p>', unsafe_allow_html=True)
    st.stop()

# ===== LOGIN PAGE =====
if st.session_state.page == "login":
    if st.button("← Back to Home", type="secondary"): nav_to("landing")
    st.markdown("""
    <div style="text-align:center; padding: 10px 0;">
        <div style="font-size:42px; font-weight:800; color:white;">⚡ ASIKERA</div>
        <div style="color:#666; font-size:11px; letter-spacing:3px; font-weight:600;">ASIKUL'S KNOWLEDGE ERA</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div style="max-width:440px; margin:0 auto;"><div class="glass">', unsafe_allow_html=True)
    st.markdown('<h3 style="color:white; margin:0;">Welcome back</h3><p style="color:#888; font-size:13px;">Sign in to your ASIKERA workspace</p>', unsafe_allow_html=True)
    email = st.text_input("Email", placeholder="you@company.com")
    pwd = st.text_input("Password", type="password", placeholder="••••••••")
    st.checkbox("Remember me", value=True)
    if st.button("Login", type="primary", use_container_width=True):
        st.session_state.logged_in = True
        nav_to("chat")
    st.markdown('<p style="text-align:center; color:#666; font-size:12px; margin:12px 0;">Or continue with</p>', unsafe_allow_html=True)
    st.button("Continue with Google", use_container_width=True, type="secondary")
    st.markdown('</div></div>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center; color:#444; font-size:11px; margin-top:20px;">© 2024 ASIKERA AI • Privacy • Terms</p>', unsafe_allow_html=True)
    st.stop()

# ===== SIDEBAR - FOR CHAT PAGES =====
with st.sidebar:
    st.markdown("## ⚡ ASIKERA")
    if st.button("＋ New Chat", type="primary", use_container_width=True): 
        st.session_state.messages = []
        nav_to("new_chat")
    st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
    st.text_input("Search", placeholder="🔍 Search chats...", label_visibility="collapsed")
    st.markdown("**AI MODEL**")
    model = st.selectbox("model", ["Nova (Smart & Fast)", "Orion (Friendly)", "Quantum (Pro)", "Atlas (English)"], label_visibility="collapsed")
    st.markdown("**RECENT CHATS**")
    if st.button("Quantum embeddings question", use_container_width=True, type="secondary"): nav_to("chat")
    if st.button("Python async debugging help", use_container_width=True, type="secondary"): nav_to("chat")
    if st.button("Brand strategy draft", use_container_width=True, type="secondary"): nav_to("chat")
    st.markdown('<div style="height:60px;"></div>', unsafe_allow_html=True)
    st.markdown("**HELP & SUPPORT**")
    if st.button("⚙️ Settings", use_container_width=True, type="secondary"): nav_to("settings")
    if st.button("↪ Logout", use_container_width=True, type="secondary"): 
        st.session_state.logged_in = False
        nav_to("landing")
    st.markdown('<p style="color:#666; font-size:12px;">asikul.era<br>sukeymona24@gmail.com</p>', unsafe_allow_html=True)

# ===== NEW CHAT EMPTY STATE =====
if st.session_state.page == "new_chat":
    st.markdown("""
    <div style="text-align:center; padding:80px 20px;">
        <div style="font-size:36px; font-weight:700; color:white; margin-bottom:20px;">How can I help you today, Asikul?</div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; max-width:600px; margin:0 auto;">
            <div class="feature-card" style="text-align:left;">📘 Explain quantum physics</div>
            <div class="feature-card" style="text-align:left;">💻 Write a Python script</div>
            <div class="feature-card" style="text-align:left;">📊 Analyze my file</div>
            <div class="feature-card" style="text-align:left;">🌐 Search the web</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if prompt := st.chat_input("Ask anything..."):
        st.session_state.messages.append({"role":"user","content":prompt})
        nav_to("chat")
    st.stop()

# ===== SETTINGS PAGE =====
if st.session_state.page == "settings":
    st.title("Settings")
    st.caption("Manage your account, preferences, security, and billing for ASIKERA AI.")
    col1, col2 = st.columns([1,2])
    with col1:
        st.markdown('<div class="glass"><h4 style="color:white;">Profile</h4><p style="color:#888; font-size:12px;">asikul.era<br>sukeymona24@gmail.com<br>Member since Sep 2024</p>', unsafe_allow_html=True)
        st.button("Edit profile", type="secondary")
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="glass"><h4 style="color:white;">Preferences</h4>', unsafe_allow_html=True)
        st.selectbox("Theme", ["Dark", "Light"])
        st.selectbox("Language", ["English, Bengali", "English Only"])
        st.selectbox("AI Version", ["Nova", "Orion", "Quantum"])
        st.markdown('</div>', unsafe_allow_html=True)
    
    c1,c2 = st.columns(2)
    with c1:
        st.markdown('<div class="glass"><h4 style="color:white;">Security</h4><p style="color:#888; font-size:12px;">Password last changed 12 days ago</p>', unsafe_allow_html=True)
        st.button("Change password", type="secondary")
        st.button("Delete account", type="secondary")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="glass" style="border-color:#7C3AED;"><h4 style="color:white;">Billing - PRO PLAN</h4><p style="color:#888; font-size:12px;">Active • Next billing Oct 28, 2026 • $20/month<br>10x higher AI usage • Nova model access</p>', unsafe_allow_html=True)
        st.button("Manage subscription", type="primary")
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ===== MAIN CHAT PAGE =====
st.markdown("### ✨ Nova")
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Default demo messages if empty
if not st.session_state.messages:
    with st.chat_message("user"):
        st.markdown("Can you summarize the benefits of quantum embeddings for retrieval?")
    with st.chat_message("assistant", avatar="⚡"):
        st.markdown("""
        Here's a quick summary of the benefits of using quantum embeddings for retrieval:
        - **Higher expressivity** — represent complex relationships by leveraging superposition
        - **Improved semantic similarity** — better capture nuanced meaning
        - **More efficient storage** — compress information into lower-dimensional quantum states
        These properties can lead to more accurate retrieval results.
        """)

if prompt := st.chat_input("Ask anything..."):
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar="⚡"):
        if groq_client:
            try:
                stream = groq_client.chat.completions.create(model="llama-3.1-8b-instant", messages=[{"role":"user","content":prompt}], stream=True)
                full = st.write_stream(c.choices[0].delta.content for c in stream if c.choices[0].delta.content)
                st.session_state.messages.append({"role":"assistant","content":full})
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            resp = f"You said: {prompt} - ASIKERA is ready!"
            st.markdown(resp)
            st.session_state.messages.append({"role":"assistant","content":resp})
