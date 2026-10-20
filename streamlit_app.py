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
st.set_page_config(page_title="Super AI Pro", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

# ================= ২. আল্ট্রা-প্রিমিয়াম CSS (সার্চ বক্স ফিক্সসহ) =================
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

.stApp { background: #0E0E11; font-family: 'Inter', sans-serif; color: #E2E8F0; }

[data-testid="stSidebar"] { 
    background: #15151A; 
    border-right: 1px solid #2A2A35; 
    padding-top: 10px;
}

/* সাইডবার সার্চ বক্সের লেখা দৃশ্যমান করার জন্য */
[data-testid="stSidebar"] input[type="text"] {
    color: #E2E8F0 !important;
    background-color: #1E1E24 !important;
}
[data-testid="stSidebar"] input[type="text"]::placeholder {
    color: #888888 !important;
}

[data-testid="collapsedControl"] {
    display: flex !important; visibility: visible !important;
    color: #FFF !important; background-color: #2A2A35 !important;
    border-radius: 8px !important; margin: 10px !important;
}
[data-testid="collapsedControl"] svg { fill: #FFF !important; }

.stButton>button[kind="primary"] { 
    background: linear-gradient(90deg, #6366F1, #A855F7);
    border-radius: 12px; height: 45px; font-weight: 600; border: 0; color: white;
    box-shadow: 0 4px 10px rgba(99, 102, 241, 0.3);
}
.stButton>button[kind="primary"]:hover { transform: translateY(-2px); }

.stButton>button[kind="secondary"] {
    background: #1E1E24; border: 1px solid #333; border-radius: 10px; 
    color: #A0A0B0; padding: 8px; font-size: 13px; transition: 0.3s;
}
.stButton>button[kind="secondary"]:hover { background: #2A2A35; color: white; border-color: #6366F1; }

div[data-testid="stChatMessage"] { background-color: transparent; padding: 10px 0; border: none; }
div[data-testid="stChatMessage"] p { color: #E2E8F0 !important; font-size: 15px; line-height: 1.6; }

div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {
    flex-direction: row-reverse; text-align: right;
}
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) .stMarkdown {
    background: #1E1E24; padding: 12px 18px; border-radius: 20px 20px 5px 20px; display: inline-block;
}
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) .stMarkdown {
    background: #25252D; padding: 12px 18px; border-radius: 20px 20px 20px 5px; display: inline-block;
}

div[data-testid="stChatInput"] { 
    background-color: #15151A !important; 
    border-radius: 25px !important; 
    border: 1px solid #333 !important; 
    padding: 5px;
}
div[data-testid="stChatInput"] textarea { color: #E2E8F0 !important; }
div[data-testid="stChatInput"] button { 
    background: linear-gradient(90deg, #6366F1, #A855F7) !important; 
    border-radius: 50% !important; 
}
div[data-testid="stChatInput"] button svg { fill: white !important; }

.footer-text { text-align: center; color: #666; font-size: 11px; margin-top: 10px; }
#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {background-color: transparent !important;}
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
def delete_chat_db(email, session_name):
    try:
        supabase.table("chats").delete().eq("user_email", email).eq("session_name", session_name).execute()
    except: pass

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
    st.markdown("<h2 style='text-align: center; margin-top: 50px; font-weight:700;'>✨ Super AI Pro</h2>", unsafe_allow_html=True)
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
    st.markdown("<h2 style='margin-bottom:0;'>✨ Super AI Pro</h2><p style='color:#888; font-size:10px; letter-spacing:1px; margin-top:0;'>PRO • ULTIMATE EDITION</p>", unsafe_allow_html=True)
    
    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        new_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
        st.session_state.chat_sessions[new_id] = []
        st.session_state.current_session = new_id
        st.rerun()
        
    search_query = st.text_input("Search", placeholder="🔍 Search chats...", label_visibility="collapsed")
    
    st.markdown("<p style='color:#888; font-size:12px; margin-bottom:5px;'>✨ Choose AI Version</p>", unsafe_allow_html=True)
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("Nova (Fast)", use_container_width=True, type="secondary"): st.session_state.persona = "nova"
        if st.button("Quantum (Pro)", use_container_width=True, type="secondary"): st.session_state.persona = "quantum"
    with col_p2:
        if st.button("Orion (Witty)", use_container_width=True, type="secondary"): st.session_state.persona = "orion"
        if st.button("Atlas (English)", use_container_width=True, type="secondary"): st.session_state.persona = "atlas"

    if "persona" not in st.session_state: st.session_state.persona = "nova"
    
    personas = {
        "nova": "You are Nova, smart and fast. Answer clearly.",
        "quantum": "You are Quantum, professional, analytical, and detailed.",
        "orion": "You are Orion, friendly, witty, and use emojis.",
        "atlas": "You are Atlas, a strict English expert. Explain things clearly in Bengali."
    }
    persona_prompt = personas.get(st.session_state.persona, personas["nova"])

    st.divider()
    
    st.markdown("<p style='color:#888; font-size:12px; margin-bottom:5px;'>⚡ Select Mode</p>", unsafe_allow_html=True)
    tool = st.selectbox("Mode", ["Chat", "Image Gen", "File Analyzer", "Web Search"], label_visibility="collapsed")
    
    with st.expander("⚙️ Advanced Settings"):
        temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.1)
        max_tokens = st.slider("Max Tokens", 500, 4000, 1500, 100)

    st.markdown("<p style='color:#888; font-size:12px; margin-bottom:5px; margin-top:10px;'>💬 Recent Chats</p>", unsafe_allow_html=True)
    
    filtered_sessions = [s for s in st.session_state.chat_sessions.keys() if search_query.lower() in s.lower()]
    for s in filtered_sessions:
        cols = st.columns([4, 1])
        with cols[0]:
            if st.button(f"💬 {s[:18]}", use_container_width=True, type="secondary"):
                st.session_state.current_session = s
                st.rerun()
        with cols[1]:
            if st.button("🗑️", key=f"del_{s}", use_container_width=True, type="secondary"):
                if len(st.session_state.chat_sessions) > 1:
                    delete_chat_db(st.session_state.user_email, s)
                    del st.session_state.chat_sessions[s]
                    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]
                    st.rerun()
                else:
                    st.warning("Keep at least one chat!")
            
    st.divider()
    
    st.markdown(f"""
    <div style='display:flex; align-items:center; background:#1E1E24; padding:10px; border-radius:10px;'>
        <div style='background:#6366F1; color:white; border-radius:50%; width:30px; height:30px; display:flex; align-items:center; justify-content:center; margin-right:10px;'>👤</div>
        <div style='font-size:12px; color:#E2E8F0; overflow:hidden; text-overflow:ellipsis;'>{st.session_state.user_email}</div>
    </div>
    """, unsafe_allow_html=True)
    
    st.write("")
    if st.button("🚪 Logout", use_container_width=True, type="secondary"):
        st.session_state.logged_in = False
        st.query_params.clear()
        st.rerun()
        
    st.markdown("<div class='footer-text'>Super AI Pro • Ultimate Edition</div>", unsafe_allow_html=True)

# ================= ৯. মেইন অ্যাপ লজিক =================
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

# --- চ্যাট মোড ---
if tool == "Chat":
    col_h1, col_h2, col_h3 = st.columns([3, 1, 1])
    with col_h1:
        st.markdown(f"### 💬 Current Chat: `{st.session_state.current_session}`")
    with col_h2:
        new_name = st.text_input("Rename", value=st.session_state.current_session, label_visibility="collapsed")
        if new_name != st.session_state.current_session and new_name:
            st.session_state.chat_sessions[new_name] = st.session_state.chat_sessions.pop(st.session_state.current_session)
            st.session_state.current_session = new_name
            save_chat(st.session_state.user_email, new_name, st.session_state.chat_sessions[new_name])
            st.rerun()
    with col_h3:
        chat_export_data = json.dumps(current_messages, ensure_ascii=False, indent=2)
        st.download_button("📥 Export", chat_export_data, file_name=f"{st.session_state.current_session}.json", mime="application/json")

    st.divider()

    for m in current_messages:
        avatar = "✨" if m["role"] == "assistant" else "👤"
        with st.chat_message(m["role"], avatar=avatar):
            st.markdown(m["content"])

    if prompt := st.chat_input("Ask anything..."):
        current_messages.append({"role":"user","content":prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
            
        with st.chat_message("assistant", avatar="✨"):
            with st.spinner("Thinking..."):
                system_msg = {"role": "system", "content": persona_prompt}
                stream = groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b", 
                    messages=[system_msg] + current_messages[-10:], 
                    temperature=temperature, max_tokens=max_tokens, stream=True
                )
                reply = st.write_stream(chunk.choices[0].delta.content for chunk in stream if chunk.choices[0].delta.content)
                
            current_messages.append({"role":"assistant","content":reply})
            save_chat(st.session_state.user_email, st.session_state.current_session, current_messages)
            
            audio_data = generate_audio_edge(reply)
            if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)

# --- ইমেজ জেনারেটর ---
elif tool == "Image Gen":
    st.markdown("### 🖼️ AI Image Generator (Pro)")
    img_prompt = st.text_input("Describe your image in detail:")
    aspect_ratio = st.selectbox("Aspect Ratio", ["1024x1024", "1280x720", "720x1280"])
    w, h = aspect_ratio.split("x")
    
    if st.button("Generate Image", type="primary"):
        if img_prompt:
            with st.spinner("Creating masterpiece..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width={w}&height={h}&nologo=true"
                st.image(image_url, use_container_width=True)
                st.markdown(f"[📥 Download Image]({image_url})")

# --- ফাইল এনালাইজার ---
elif tool == "File Analyzer":
    st.markdown("### 📄 Pro File Analyzer (PDF/Image/Docs)")
    uploaded_file = st.file_uploader("Upload a file to analyze", type=["pdf", "png", "jpg", "jpeg", "txt"])
    file_query = st.text_input("What would you like to extract or analyze?")
    
    if st.button("Analyze with Gemini Pro", type="primary") and uploaded_file and file_query:
        with st.spinner("Analyzing document..."):
            try:
                gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                response = gemini_model.generate_content([file_query, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
                st.markdown("### 📝 Analysis Result:")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Error: {str(e)}")

# --- ওয়েব সার্চ ---
elif tool == "Web Search":
    st.markdown("### 🌐 Live Web Search & Summary")
    search_query = st.text_input("Search the live internet:")
    if st.button("Search Web", type="primary") and search_query:
        with st.spinner("Browsing live internet..."):
            try:
                results = list(DDGS().text(search_query, max_results=5))
                if results:
                    context = "\n".join([f"Source: {r['href']}\nSnippet: {r['body']}" for r in results])
                    sys_prompt = f"You are a smart AI web assistant. Provide a structured, accurate summary based strictly on these live search results:\n{context}"
                    res = groq_client.chat.completions.create(
                        model="openai/gpt-oss-120b", 
                        messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": search_query}]
                    )
                    st.markdown(res.choices[0].message.content)
                else:
                    st.warning("No live search results found.")
            except Exception as e:
                st.error(f"Search Error: {str(e)}")
