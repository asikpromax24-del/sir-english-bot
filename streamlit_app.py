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

# ================= ২. আল্ট্রা-প্রিমিয়াম CSS (মোবাইল ও স্ক্রিন সাইজ ফিক্স) =================
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

/* গ্লোবাল ডার্ক থিম */
.stApp { background: #0E0E11; font-family: 'Inter', sans-serif; color: #E2E8F0; }

/* ================= সাইডবার ছোট করা (যাতে মেইন স্ক্রিন বড় হয়) ================= */
[data-testid="stSidebar"] { 
    background: #15151A; 
    border-right: 1px solid #2A2A35; 
    width: 280px !important; /* সাইডবারের সাইজ ছোট করা হলো */
}

/* হেডার এবং Fork বাটন হাইড করা */
[data-testid="stHeader"] { display: none !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
#MainMenu {visibility: hidden;} footer {visibility: hidden;} 

/* মোবাইলে সাইডবার ওপেন বাটন */
[data-testid="collapsedControl"] {
    display: flex !important; visibility: visible !important;
    color: #FFF !important; background-color: #2A2A35 !important;
    border-radius: 8px !important; margin: 10px !important;
    position: absolute; top: 10px; left: 10px; z-index: 99999;
}

/* ================= মেইন কন্টেইনার ফুল স্ক্রিন করা ================= */
.block-container { 
    padding-top: 2rem !important; 
    padding-bottom: 5rem !important; 
    padding-left: 1rem !important; 
    padding-right: 1rem !important;
    max-width: 100% !important; /* মেইন কন্টেইনার ফুল উইডথ */
}

/* বাটন ডিজাইন */
.stButton>button[kind="primary"] { background: linear-gradient(90deg, #6366F1, #A855F7); border-radius: 12px; height: 45px; font-weight: 600; border: 0; color: white; box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3); transition: 0.2s; }
.stButton>button[kind="secondary"] { background: #1E1E24; border: 1px solid #333; border-radius: 10px; color: #A0A0B0; padding: 10px; font-size: 13px; transition: 0.3s; }
.stButton>button[kind="secondary"]:hover { background: #2A2A35; color: white; border-color: #6366F1; }

/* ================= চ্যাট ডিজাইন (লেখা ছোট ও টেবিল ফিক্স) ================= */
div[data-testid="stChatMessage"] { background-color: transparent; padding: 8px 0; border: none; }
div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li { color: #E2E8F0 !important; font-size: 14px !important; line-height: 1.5; }

/* ইউজার মেসেজ */
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse; text-align: right; margin-left: auto; margin-right: 0; width: fit-content; max-width: 85%; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) .stMarkdown { background: #1E1E24; padding: 10px 15px; border-radius: 20px 20px 5px 20px; display: inline-block; }

/* এআই মেসেজ */
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) { margin-right: auto; margin-left: 0; width: fit-content; max-width: 95%; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) .stMarkdown { background: #25252D; padding: 15px; border-radius: 20px 20px 20px 5px; display: inline-block; }

/* ================= টেবিল ভেঙে যাওয়া বন্ধ করা ================= */
div[data-testid="stChatMessage"] table {
    display: block !important;
    overflow-x: auto !important; /* টেবিল বড় হলে স্ক্রল হবে */
    white-space: nowrap !important;
    border-collapse: collapse !important;
    margin: 10px 0 !important;
}
div[data-testid="stChatMessage"] th, div[data-testid="stChatMessage"] td { 
    color: #E2E8F0 !important; 
    border: 1px solid #444 !important; 
    padding: 6px 10px !important; 
    font-size: 13px !important;
}

/* ================= চ্যাট ইনপুট বক্স ================= */
div[data-testid="stChatInput"] { 
    background-color: #15151A !important; 
    border-radius: 25px !important; 
    border: 1px solid #444 !important; 
    padding: 5px;
}
div[data-testid="stChatInput"] textarea { 
    color: #FFFFFF !important; 
    font-size: 15px !important;
}
div[data-testid="stChatInput"] textarea::placeholder { color: #888888 !important; }
div[data-testid="stChatInput"] button { 
    background: linear-gradient(90deg, #6366F1, #A855F7) !important; 
    border-radius: 50% !important; 
}
div[data-testid="stChatInput"] button svg { fill: white !important; }

/* সাইডবার টেক্সট */
.sidebar-header { padding: 20px 10px 10px 10px; }
.sidebar-title { font-size: 20px; font-weight: 800; color: #FFF; margin: 0; letter-spacing: 1px; }
.sidebar-subtitle { font-size: 9px; color: #888; letter-spacing: 1.5px; margin-top: 5px; font-weight: 600; }
.divider { border-top: 1px solid #1F1F27; margin: 15px 0; }
.label-text { font-size: 11px; color: #888; margin-bottom: 8px; font-weight: 500; }

/* ইউজার কার্ড */
.user-card { display: flex; align-items: center; background: #1E1E24; padding: 8px; border-radius: 8px; border: 1px solid #333; margin-bottom: 10px; }
.user-avatar { background: #6366F1; color: white; border-radius: 50%; width: 25px; height: 25px; display: flex; align-items: center; justify-content: center; font-size: 12px; margin-right: 8px; }
.user-email { font-size: 11px; color: #E2E8F0; overflow: hidden; text-overflow: ellipsis; }
.footer-text { text-align: center; color: #555; font-size: 9px; margin-top: 20px; }
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
    st.markdown("<h2 style='text-align: center; margin-top: 50px; font-weight:800; color:white; letter-spacing:2px;'>⚡ ASIKERA</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color:#888; font-size:12px; letter-spacing:1px;'>ASIKUL'S KNOWLEDGE ERA</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Sign Up"])
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
        <div class="sidebar-subtitle">ASIKUL'S KNOWLEDGE ERA</div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        new_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
        st.session_state.chat_sessions[new_id] = []
        st.session_state.current_session = new_id
        st.rerun()
        
    search_query = st.text_input("Search", placeholder="🔍 Search chats...", label_visibility="collapsed")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="label-text">✨ Choose AI Version</div>', unsafe_allow_html=True)
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("Nova", use_container_width=True, type="secondary"): st.session_state.persona = "nova"
        if st.button("Quantum", use_container_width=True, type="secondary"): st.session_state.persona = "quantum"
    with col_p2:
        if st.button("Orion", use_container_width=True, type="secondary"): st.session_state.persona = "orion"
        if st.button("English Board", use_container_width=True, type="secondary"): st.session_state.persona = "english"

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
    st.markdown('<div class="label-text">⚡ Mode</div>', unsafe_allow_html=True)
    tool = st.selectbox("Mode", ["Chat", "Image Gen", "File Analyzer", "Web Search"], label_visibility="collapsed")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="label-text">💬 Recent</div>', unsafe_allow_html=True)
    
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
    
    if st.button("🚪 Logout", use_container_width=True, type="secondary"):
        st.session_state.logged_in = False
        st.query_params.clear()
        st.rerun()
        
    st.markdown("<div class='footer-text'>ASIKERA • 1.0</div>", unsafe_allow_html=True)

# ================= ৯. মেইন অ্যাপ লজিক =================
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

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
            with st.spinner("ASIKERA is thinking..."):
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

# --- অন্যান্য টুল ---
elif tool == "Image Gen":
    st.markdown("### 🖼️ ASIKERA Image Gen")
    img_prompt = st.text_input("Describe your image:")
    if st.button("Generate Image", type="primary"):
        if img_prompt:
            with st.spinner("Painting..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, use_container_width=True)

elif tool == "File Analyzer":
    st.markdown("### 📄 ASIKERA File Analyzer")
    uploaded_file = st.file_uploader("Upload a PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
    file_query = st.text_input("What do you want to know?")
    if st.button("Analyze File", type="primary") and uploaded_file and file_query:
        with st.spinner("Analyzing..."):
            try:
                gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                response = gemini_model.generate_content([file_query, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Error: {str(e)}")

elif tool == "Web Search":
    st.markdown("### 🌐 ASIKERA Web Search")
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
