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
import pandas as pd
import plotly.express as px
from supabase import create_client, Client

# ================= ১. পেজ কনফিগারেশন =================
st.set_page_config(page_title="ASIKERA AI", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# ================= ২. আল্ট্রা-প্রিমিয়াম CSS (DeepSeek স্টাইল) =================
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

/* গ্লোবাল ডার্ক থিম */
.stApp { background: #1E1E1E; font-family: 'Inter', sans-serif; color: #E0E0E0; }

/* ================= সাইডবার ছোট ও মিনিমাল করা ================= */
[data-testid="stSidebar"] { 
    background: #191919; 
    border-right: 1px solid #333; 
    width: 250px !important; 
    min-width: 250px !important;
}
[data-testid="stSidebar"] .stButton>button {
    padding: 5px 10px !important; font-size: 12px !important; height: 32px !important;
}

/* হেডার এবং Fork বাটন হাইড করা */
[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
#MainMenu {visibility: hidden;} footer {visibility: hidden;} 

/* মোবাইলে সাইডবার ওপেন বাটন */
[data-testid="collapsedControl"] {
    display: flex !important; visibility: visible !important;
    color: #FFF !important; background-color: #333 !important;
    border-radius: 5px !important; margin: 10px !important;
}

/* মেইন কন্টেইনার (DeepSeek স্টাইল) */
.block-container { 
    padding-top: 2rem !important; 
    padding-bottom: 6rem !important; 
    max-width: 800px !important; 
    margin: 0 auto !important;
}

/* বাটন ডিজাইন (মিনিমাল) */
.stButton>button[kind="primary"] { 
    background: #4D6BFE; border-radius: 8px; height: 35px; font-weight: 500; border: 0; color: white; font-size: 13px;
}
.stButton>button[kind="secondary"] { 
    background: #252525; border: 1px solid #333; border-radius: 8px; color: #AAA; padding: 5px; font-size: 12px; 
}
.stButton>button[kind="secondary"]:hover { background: #333; color: white; }

/* ================= চ্যাট ডিজাইন ================= */
div[data-testid="stChatMessage"] { background-color: transparent; padding: 10px 0; border: none; }

/* === এখানে লেখার কালার ফিক্স করা হয়েছে === */
div[data-testid="stChatMessage"] .stMarkdown * { 
    color: #E0E0E0 !important; 
}
div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li { 
    color: #E0E0E0 !important; font-size: 14px !important; line-height: 1.6; 
}

/* ইউজার মেসেজ */
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse; text-align: right; margin-left: auto; margin-right: 0; width: fit-content; max-width: 90%; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) .stMarkdown { background: #2A2A2A; padding: 10px 15px; border-radius: 15px 15px 2px 15px; display: inline-block; }

/* এআই মেসেজ */
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) { margin-right: auto; margin-left: 0; width: 100%; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) .stMarkdown { background: transparent; padding: 10px 0; display: inline-block; }

/* টেবিল ফিক্স (টেবিলের ভেতরের লেখাও সাদা হবে) */
div[data-testid="stChatMessage"] table { display: block !important; overflow-x: auto !important; border-collapse: collapse !important; margin: 10px 0 !important; }
div[data-testid="stChatMessage"] table th, div[data-testid="stChatMessage"] table td { 
    color: #E0E0E0 !important; border: 1px solid #444 !important; padding: 6px 12px !important; font-size: 13px !important; 
}

/* ================= ইনপুট বক্স ফিক্স ================= */
/* সার্চ বক্স (Sidebar) */
div[data-testid="stTextInput"] input { 
    background-color: #252525 !important; color: #FFFFFF !important; border: 1px solid #444 !important; border-radius: 8px !important;
}
div[data-testid="stTextInput"] input::placeholder { color: #888 !important; }

/* নিচের চ্যাট বক্স (Chat Input) */
div[data-testid="stChatInput"] { background-color: #252525 !important; border-radius: 8px !important; border: 1px solid #444 !important; }
div[data-testid="stChatInput"] > div { background-color: #252525 !important; }
div[data-testid="stChatInput"] textarea { color: #FFFFFF !important; background-color: #252525 !important; font-size: 14px !important; }
div[data-testid="stChatInput"] textarea::placeholder { color: #888 !important; }
div[data-testid="stChatInput"] button { background: #4D6BFE !important; border-radius: 5px !important; }
div[data-testid="stChatInput"] button svg { fill: white !important; }

/* সিলেক্ট বক্স ফিক্স */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: #252525 !important; color: #FFF !important; border: 1px solid #444 !important;
}

/* সাইডবার টেক্সট ও স্পেসিং */
.sidebar-header { padding: 15px 10px 10px 10px; }
.sidebar-title { font-size: 18px; font-weight: 600; color: #FFF; margin: 0; letter-spacing: 0.5px; }
.sidebar-subtitle { font-size: 9px; color: #777; letter-spacing: 1px; margin-top: 5px; font-weight: 500; }
.divider { border-top: 1px solid #333; margin: 15px 0; }
.label-text { font-size: 11px; color: #777; margin-bottom: 8px; font-weight: 500; }

/* ইউজার কার্ড */
.user-card { display: flex; align-items: center; background: #252525; padding: 8px; border-radius: 8px; border: 1px solid #333; margin-bottom: 10px; }
.user-avatar { background: #4D6BFE; color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 12px; margin-right: 10px; }
.user-email { font-size: 11px; color: #E0E0E0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.footer-text { text-align: center; color: #555; font-size: 9px; margin-top: 10px; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ================= ৩. API Clients & Supabase =================
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# ================= ৪. ডেটাবেস ফাংশন =================
def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def create_user(email, password):
    try: 
        supabase.table("users").insert({"email": email, "password": make_hashes(password)}).execute()
        return True
    except: return False
def login_user(email, password):
    response = supabase.table("users").select("password").eq("email", email).execute()
    if response.data and response.data[0]["password"] == make_hashes(password): return True
    return False
def save_chat(email, session_name, messages):
    try:
        supabase.table("chats").delete().eq("user_email", email).eq("session_name", session_name).execute()
        supabase.table("chats").insert({"user_email": email, "session_name": session_name, "messages": messages}).execute()
    except: pass
def load_chats(email):
    response = supabase.table("chats").select("session_name, messages").eq("user_email", email).execute()
    sessions = {row["session_name"]: row["messages"] for row in response.data}
    return sessions if sessions else {"New Chat": []}

# ================= ৫. অডিও জেনারেটর =================
def generate_audio_edge(text, speed="+0%"):
    try:
        lang = detect(text)
        voice = 'bn-BD-NabanitaNeural' if lang == 'bn' else 'en-US-AriaNeural'
    except: voice = 'en-US-AriaNeural'
    async def _generate():
        communicate = edge_tts.Communicate(text, voice, rate=speed)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": audio_data += chunk["data"]
        return audio_data
    try:
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        return io.BytesIO(loop.run_until_complete(_generate()))
    except: return None

# ================= ৬. অটো-লগইন =================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if not st.session_state.logged_in and "email" in st.query_params:
    st.session_state.logged_in = True
    st.session_state.user_email = st.query_params["email"]
    st.rerun()

# ================= ৭. লগইন পেজ =================
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; margin-top: 80px; font-weight:600; color:white;'>⚡ ASIKERA</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color:#777; font-size:12px; letter-spacing:1px; margin-bottom:40px;'>ASIKUL'S KNOWLEDGE ERA</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,1.5,1])
    with col2:
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        with tab1:
            l_email = st.text_input("Email", key="l_email")
            l_pass = st.text_input("Password", type="password", key="l_pass")
            if st.button("Login", use_container_width=True, type="primary"):
                if login_user(l_email, l_pass):
                    st.session_state.logged_in = True
                    st.session_state.user_email = l_email
                    st.query_params["email"] = l_email
                    st.rerun()
                else: st.error("Invalid credentials")
        with tab2:
            s_email = st.text_input("Email", key="s_email")
            s_pass = st.text_input("Password", type="password", key="s_pass")
            if st.button("Sign Up", use_container_width=True, type="secondary"):
                if create_user(s_email, s_pass): st.success("Account created! Please login.")
                else: st.error("Email already exists.")
    st.stop()

# ================= ৮. সাইডবার =================
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_chats(st.session_state.user_email)
if "current_session" not in st.session_state:
    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]

with st.sidebar:
    st.markdown("""
    <div class="sidebar-header">
        <div class="sidebar-title">⚡ ASIKERA</div>
        <div class="sidebar-subtitle">KNOWLEDGE ERA</div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        new_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
        st.session_state.chat_sessions[new_id] = []
        st.session_state.current_session = new_id
        st.rerun()
        
    search_query = st.text_input("Search", placeholder="Search chats...", label_visibility="collapsed")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="label-text">AI Versions</div>', unsafe_allow_html=True)
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("Nova", use_container_width=True, type="secondary"): st.session_state.persona = "nova"
        if st.button("Quantum", use_container_width=True, type="secondary"): st.session_state.persona = "quantum"
    with col_p2:
        if st.button("Orion", use_container_width=True, type="secondary"): st.session_state.persona = "orion"
        if st.button("English", use_container_width=True, type="secondary"): st.session_state.persona = "english"

    if "persona" not in st.session_state: st.session_state.persona = "nova"
    
    if st.session_state.persona == "orion":
        persona_prompt = "You are Orion, friendly and witty. Use emojis."
    elif st.session_state.persona == "quantum":
        persona_prompt = "You are Quantum, professional and detailed."
    elif st.session_state.persona == "english":
        persona_prompt = "You are 'Sir English' from the English Board. You are a strict English teacher. Correct grammar, explain rules in Bengali, and give examples."
    else:
        persona_prompt = "You are Nova, smart and fast. Answer clearly."

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="label-text">Tools</div>', unsafe_allow_html=True)
    tool = st.selectbox("Mode", ["Chat", "Image Gen", "File Analyzer", "Web Search"], label_visibility="collapsed")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="label-text">Recent</div>', unsafe_allow_html=True)
    
    filtered_sessions = [s for s in st.session_state.chat_sessions.keys() if search_query.lower() in s.lower()]
    for s in filtered_sessions:
        if st.button(f"💬 {s}", use_container_width=True, type="secondary"):
            st.session_state.current_session = s
            st.rerun()
            
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="user-card">
        <div class="user-avatar">👤</div>
        <div class="user-email">{st.session_state.user_email}</div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Logout", use_container_width=True, type="secondary"):
        st.session_state.logged_in = False
        st.query_params.clear()
        st.rerun()
        
    st.markdown("<div class='footer-text'>ASIKERA v1.0</div>", unsafe_allow_html=True)

# ================= ৯. মেইন অ্যাপ লজিক =================
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

# --- চ্যাট মোড ---
if tool == "Chat":
    for m in current_messages:
        avatar = "✨" if m["role"] == "assistant" else "👤"
        with st.chat_message(m["role"], avatar=avatar):
            st.markdown(m["content"])

    if prompt := st.chat_input("Ask ASIKERA anything..."):
        current_messages.append({"role":"user","content":prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
            
        with st.chat_message("assistant", avatar="✨"):
            with st.spinner("Thinking..."):
                system_msg = {"role": "system", "content": persona_prompt}
                stream = groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b", 
                    messages=[system_msg] + current_messages[-10:], 
                    temperature=0.7, max_tokens=1500, stream=True
                )
                reply = st.write_stream(chunk.choices[0].delta.content for chunk in stream if chunk.choices[0].delta.content)
                
            current_messages.append({"role":"assistant","content":reply})
            save_chat(st.session_state.user_email, st.session_state.current_session, current_messages)
            
            audio_data = generate_audio_edge(reply)
            if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)

# --- ইমেজ জেনারেটর ---
elif tool == "Image Gen":
    st.markdown("### Image Generator")
    img_prompt = st.text_input("Describe your image:")
    if st.button("Generate", type="primary"):
        if img_prompt:
            with st.spinner("Painting..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, use_container_width=True)

# --- ফাইল এনালাইজার ---
elif tool == "File Analyzer":
    st.markdown("### File Analyzer")
    uploaded_file = st.file_uploader("Upload PDF/Image", type=["pdf", "png", "jpg", "jpeg"])
    file_query = st.text_input("What do you want to know?")
    if st.button("Analyze", type="primary") and uploaded_file and file_query:
        with st.spinner("Analyzing..."):
            try:
                gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                response = gemini_model.generate_content([file_query, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Error: {str(e)}")

# --- ওয়েব সার্চ ---
elif tool == "Web Search":
    st.markdown("### Web Search")
    search_query = st.text_input("Search the web:")
    if st.button("Search", type="primary") and search_query:
        with st.spinner("Searching..."):
            try:
                results = list(DDGS().text(search_query, max_results=4))
                if results:
                    context = "\n".join([f"Snippet: {r['body']}" for r in results])
                    sys_prompt = f"Answer based on these results:\n{context}"
                    res = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": search_query}])
                    st.markdown(res.choices[0].message.content)
            except Exception as e:
                st.error(f"Error: {str(e)}")
