import streamlit as st
from groq import Groq
import google.generativeai as genai
from ddgs import DDGS
import urllib.parse
import edge_tts
import asyncio
import io
from langdetect import detect
import hashlib
from supabase import create_client, Client

# ================= ১. PRO PAGE CONFIG =================
st.set_page_config(page_title="Super AI Pro", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

# ================= ২. PRO BRAND CSS - FIXED =================
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #0A0A0A; }
[data-testid="stSidebar"] { background: #111111; border-right: 1px solid #232323; }
[data-testid="stSidebar"] .stButton>button { border-radius: 10px; }

/* Gradient Primary Button */
.stButton>button[kind="primary"] { 
    background: linear-gradient(135deg, #7C3AED 0%, #3B82F6 100%);
    border: 0; color: white; font-weight: 700; height: 48px; border-radius: 12px;
}

/* Chat Bubbles - Modern */
div[data-testid="stChatMessage"] { background: transparent; border: none; padding: 12px 0; }
div[data-testid="stChatMessage"][data-testid*="user"] { 
    background: linear-gradient(135deg, #7C3AED, #3B82F6);
    border-radius: 20px 20px 4px 20px; margin-left: 40px;
}
div[data-testid="stChatMessage"] p { color: #E5E5E5 !important; font-size: 15px; line-height: 1.7; }

/* Input Bar - Pro */
div[data-testid="stChatInput"] { 
    background: #1A1A1A !important; border-radius: 24px !important; 
    border: 1px solid #2A2A2A !important; box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}

/* Hide only footer, NOT header - This fixes your menu bug */
#MainMenu {visibility: hidden;} 
footer {visibility: hidden;}
/* header {visibility: hidden;} <-- এটা বাদ দিলাম, এটাই তোমার মেনু মুছে দিচ্ছিলো */

.persona-badge {
    background: #1E1E1E; border: 1px solid #2A2A2A; padding: 10px; border-radius: 12px;
    text-align: center; cursor: pointer; transition: 0.2s;
}
.persona-badge:hover { border-color: #7C3AED; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ================= ৩. BACKEND (তোমার আগের মতোই) =================
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

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

# Auto-login
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if not st.session_state.logged_in and "email" in st.query_params:
    st.session_state.logged_in = True
    st.session_state.user_email = st.query_params["email"]
    st.rerun()

if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align:center; margin-top:80px;'>✨ Super AI Pro</h1><p style='text-align:center; color:#888;'>Professional • Trending • Your Brand</p>", unsafe_allow_html=True)
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
            if st.button("Sign Up", use_container_width=True, type="primary"):
                if create_user(s_email, s_pass): st.success("Account created! Please login.")
                else: st.error("Email already exists.")
    st.stop()

# ================= ৪. SIDEBAR - PRO VERSION (Like Preview) =================
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_chats(st.session_state.user_email)
if "current_session" not in st.session_state:
    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]

with st.sidebar:
    st.markdown("## ✨ Super AI")
    st.caption("PRO • TRENDING FIRST")
    
    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        new_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
        st.session_state.chat_sessions[new_id] = []
        st.session_state.current_session = new_id
        st.rerun()
        
    search_query = st.text_input("Search", placeholder="🔍 Search chats...", label_visibility="collapsed")
    st.divider()
    
    st.markdown("**🎭 Choose AI Version**")
    persona_choice = st.radio("persona", ["🚀 Nova (Smart & Fast)", "😎 Vibe (Friendly & Witty)", "🧑‍🏫 Pro (Professional)", "📚 Sir English"], label_visibility="collapsed")
    
    if persona_choice == "📚 Sir English": persona_prompt = "You are 'Sir English', a strict English teacher. Correct grammar, explain in Bengali."
    elif persona_choice == "😎 Vibe (Friendly & Witty)": persona_prompt = "You are Vibe AI. Be friendly, slightly humorous, use emojis, keep it concise."
    elif persona_choice == "🧑‍🏫 Pro (Professional)": persona_prompt = "You are Pro AI, a professional, highly intelligent AI assistant. Provide detailed, well-formatted answers."
    else: persona_prompt = "You are Nova, an incredibly smart and fast AI. Answer clearly and efficiently."
        
    st.divider()
    tool = st.selectbox("🛠️ Choose Tool", ["💬 Chat", "🖼️ Image Gen", "📄 File Analyzer", "🌐 Web Search"])
    st.divider()
    
    st.markdown("**💬 Recent**")
    filtered_sessions = [s for s in st.session_state.chat_sessions.keys() if search_query.lower() in s.lower()]
    for s in filtered_sessions:
        if st.button(f"💬 {s}", key=s, use_container_width=True):
            st.session_state.current_session = s
            st.rerun()
            
    st.divider()
    st.caption(f"Logged in as: {st.session_state.user_email}")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.query_params.clear()
        st.rerun()

# ================= ৫. MAIN LOGIC =================
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

if not current_messages:
    st.markdown(f"<div style='text-align:center; padding:60px 20px;'><h1 style='color:white;'>How can I help you today?</h1><p style='color:#666;'>Persona: {persona_choice}</p></div>", unsafe_allow_html=True)

if tool == "💬 Chat":
    for m in current_messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    if prompt := st.chat_input("Ask anything..."):
        current_messages.append({"role":"user","content":prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                system_msg = {"role": "system", "content": persona_prompt}
                stream = groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile", 
                    messages=[system_msg] + current_messages[-10:], 
                    temperature=0.7, max_tokens=1500, stream=True
                )
                reply = st.write_stream(chunk.choices[0].delta.content for chunk in stream if chunk.choices[0].delta.content)
            current_messages.append({"role":"assistant","content":reply})
            save_chat(st.session_state.user_email, st.session_state.current_session, current_messages)
            audio_data = generate_audio_edge(reply)
            if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)

elif tool == "🖼️ Image Gen":
    st.markdown("### 🖼️ Image Generator")
    img_prompt = st.text_input("Describe your image:")
    if st.button("Generate Image", type="primary") and img_prompt:
        with st.spinner("Painting..."):
            safe_prompt = urllib.parse.quote(img_prompt)
            image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
            st.image(image_url, use_container_width=True)

elif tool == "📄 File Analyzer":
    st.markdown("### 📄 File Analyzer")
    uploaded_file = st.file_uploader("Upload PDF/Image", type=["pdf", "png", "jpg", "jpeg"])
    file_query = st.text_input("What do you want to know?")
    if st.button("Analyze File", type="primary") and uploaded_file and file_query:
        with st.spinner("Analyzing..."):
            gemini_model = genai.GenerativeModel('gemini-1.5-flash')
            response = gemini_model.generate_content([file_query, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
            st.markdown(response.text)

elif tool == "🌐 Web Search":
    st.markdown("### 🌐 Live Web Search")
    search_q = st.text_input("Search the web:")
    if st.button("Search", type="primary") and search_q:
        with st.spinner("Searching..."):
            results = list(DDGS().text(search_q, max_results=4))
            context = "\n".join([f"{r['body']}" for r in results])
            res = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile", 
                messages=[{"role": "system", "content": f"Answer based on: {context}"}, {"role": "user", "content": search_q}]
            )
            st.markdown(res.choices[0].message.content)
