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

# ================= ১. পেজ কনফিগারেশন ও UI (আপনার দেওয়া ডিজাইন) =================
st.set_page_config(page_title="Super AI Pro", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

# আপনার দেওয়া CSS + চ্যাট ইন্টারফেসের জন্য কিছু বাড়তি ফিক্স
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');
.stApp { background: #0F0F0F; font-family: 'Inter', sans-serif; color: #E0E0E0; }
[data-testid="stSidebar"] { background: #151515; border-right: 1px solid #262626; }
.stButton>button[kind="primary"] { 
    background: linear-gradient(135deg, #7C3AED, #3B82F6);
    border-radius: 12px; height: 44px; font-weight: 600; border:0; color: white;
}
.stButton>button[kind="secondary"] {
    background: #1E1E1E; border: 1px solid #333; border-radius: 12px; color: #CCC;
}
.stButton>button[kind="secondary"]:hover { border-color: #7C3AED; color: white; }

/* চ্যাট মেসেজ ডিজাইন */
div[data-testid="stChatMessage"] { background-color: transparent; padding: 10px 0; border-bottom: 1px solid #262626; }
div[data-testid="stChatMessage"] p { color: #E0E0E0 !important; font-size: 16px; line-height: 1.6; }
div[data-testid="stChatMessage"] table { border-collapse: collapse; width: 100%; margin: 10px 0; }
div[data-testid="stChatMessage"] th, div[data-testid="stChatMessage"] td { color: #E0E0E0 !important; border: 1px solid #444 !important; padding: 8px; }

/* চ্যাট ইনপুট */
div[data-testid="stChatInput"] { background-color: #1A1A1A !important; border-radius: 15px !important; border: 1px solid #333; }
div[data-testid="stChatInput"] textarea { color: #E0E0E0 !important; }
div[data-testid="stChatInput"] button { background-color: #2B2D31 !important; border-radius: 10px !important; }
div[data-testid="stChatInput"] button svg { fill: #FFF !important; }

/* অন্যান্য ইনপুট */
div[data-testid="stTextInput"] input { color: #E0E0E0 !important; background-color: #1A1A1A !important; border-radius: 10px; border: 1px solid #333; }
#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ================= ২. API Clients & Supabase =================
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# ================= ৩. ডেটাবেস ফাংশন =================
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

# ================= ৪. অডিও জেনারেটর =================
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

# ================= ৫. অটো-লগইন =================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if not st.session_state.logged_in and "email" in st.query_params:
    st.session_state.logged_in = True
    st.session_state.user_email = st.query_params["email"]
    st.rerun()

# ================= ৬. লগইন পেজ =================
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>✨ Super AI Pro</h2>", unsafe_allow_html=True)
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

# ================= ৭. সাইডবার (আপনার দেওয়া ডিজাইন) =================
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_chats(st.session_state.user_email)
if "current_session" not in st.session_state:
    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]

with st.sidebar:
    st.markdown("## ✨ Super AI Pro")
    
    # New Chat Button (Gradient)
    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        new_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
        st.session_state.chat_sessions[new_id] = []
        st.session_state.current_session = new_id
        st.rerun()
        
    search_query = st.text_input("Search", placeholder="🔍 Search chats...", label_visibility="collapsed")
    st.divider()
    
    st.markdown("**🎭 AI Personalities**")
    persona_choice = st.radio("persona", ["🚀 Nova", "😎 Vibe", "🧑‍🏫 Pro", "📚 Sir English"], label_visibility="collapsed")
    
    # প্রম্পট ম্যাপিং
    if persona_choice == "📚 Sir English":
        persona_prompt = "You are 'Sir English', a strict English teacher. Correct grammar, explain in Bengali."
    elif persona_choice == "😎 Vibe":
        persona_prompt = "You are Vibe AI. Be friendly, slightly humorous, use emojis, keep it concise."
    elif persona_choice == "🧑‍🏫 Pro":
        persona_prompt = "You are Pro AI, a professional, highly intelligent AI assistant. Provide detailed answers."
    else:
        persona_prompt = "You are Nova, an incredibly smart and fast AI. Answer clearly and efficiently."
        
    st.divider()
    
    tool = st.selectbox("🛠️ Tools", ["💬 Chat", "🖼️ Image Gen", "📄 File Analyzer", "🌐 Web Search"])
    
    st.divider()
    st.markdown("**💬 Recent**")
    filtered_sessions = [s for s in st.session_state.chat_sessions.keys() if search_query.lower() in s.lower()]
    for s in filtered_sessions:
        if st.button(f"💬 {s}", use_container_width=True, type="secondary"):
            st.session_state.current_session = s
            st.rerun()
            
    st.divider()
    if st.button("🚪 Logout", use_container_width=True, type="secondary"):
        st.session_state.logged_in = False
        st.query_params.clear()
        st.rerun()

# ================= ৮. মেইন অ্যাপ লজিক =================
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

# --- টুল ১: চ্যাট ---
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
                    model="openai/gpt-oss-120b", 
                    messages=[system_msg] + current_messages[-10:], 
                    temperature=0.7, max_tokens=1500, stream=True
                )
                reply = st.write_stream(chunk.choices[0].delta.content for chunk in stream if chunk.choices[0].delta.content)
                
            current_messages.append({"role":"assistant","content":reply})
            save_chat(st.session_state.user_email, st.session_state.current_session, current_messages)
            
            # অডিও
            audio_data = generate_audio_edge(reply)
            if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)

# --- টুল ২: ইমেজ জেনারেটর ---
elif tool == "🖼️ Image Gen":
    st.markdown("### 🖼️ Image Generator")
    img_prompt = st.text_input("Describe your image:")
    if st.button("Generate Image", type="primary"):
        if img_prompt:
            with st.spinner("Painting..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, use_container_width=True)

# --- টুল ৩: ফাইল এনালাইজার ---
elif tool == "📄 File Analyzer":
    st.markdown("### 📄 File Analyzer (PDF/Image)")
    uploaded_file = st.file_uploader("Upload a PDF or Image to analyze", type=["pdf", "png", "jpg", "jpeg"])
    file_query = st.text_input("What do you want to know about this file?")
    
    if st.button("Analyze File", type="primary") and uploaded_file and file_query:
        with st.spinner("Analyzing file..."):
            try:
                gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                response = gemini_model.generate_content([file_query, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
                st.markdown("### 📝 Analysis Result:")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Error: {str(e)}")

# --- টুল ৪: ওয়েব সার্চ ---
elif tool == "🌐 Web Search":
    st.markdown("### 🌐 Live Web Search")
    search_query = st.text_input("Search the web:")
    if st.button("Search", type="primary") and search_query:
        with st.spinner("Searching the live internet..."):
            try:
                results = list(DDGS().text(search_query, max_results=4))
                if results:
                    context = "\n".join([f"Snippet: {r['body']}" for r in results])
                    sys_prompt = f"You are a smart AI. Answer accurately based on these search results:\n{context}"
                    res = groq_client.chat.completions.create(
                        model="openai/gpt-oss-120b", 
                        messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": search_query}]
                    )
                    st.markdown(res.choices[0].message.content)
                else:
                    st.warning("No results found.")
            except Exception as e:
                st.error(f"Search Error: {str(e)}")
