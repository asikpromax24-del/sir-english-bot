import streamlit as st
from groq import Groq
import google.generativeai as genai
from ddgs import DDGS
import urllib.parse
import edge_tts
import asyncio
import io
from langdetect import detect
import pandas as pd
import plotly.express as px
import json
import hashlib
from supabase import create_client, Client

# ================= ১. পেজ কনফিগারেশন ও UI =================
st.set_page_config(page_title="Super AI - Ultimate", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

custom_css = """
<style>
    .stApp { background-color: #131314; color: #E3E3E3 !important; }
    [data-testid="stSidebar"] { background-color: #1E1F20; border-right: 1px solid #333; }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #E3E3E3 !important; }
    section[data-testid="stSidebar"] .stButton > button { border-radius: 20px; text-align: left; }
    .block-container { padding-top: 2rem !important; max-width: 900px !important; }
    div[data-testid="stChatMessage"] { background-color: transparent; padding: 10px 0; border-bottom: 1px solid #333; }
    div[data-testid="stChatMessage"] p { color: #E3E3E3 !important; font-size: 16px; line-height: 1.6; }
    div[data-testid="stChatInput"] { background-color: #1E1F20 !important; border-radius: 30px !important; border: 1px solid #444; }
    div[data-testid="stChatInput"] textarea { color: #E3E3E3 !important; }
    .stButton > button { color: #E3E3E3 !important; background-color: #2B2D31 !important; border: none !important; border-radius: 15px !important; padding: 15px 20px !important; text-align: left !important; transition: all 0.3s; }
    .stButton > button:hover { background-color: #3F4147 !important; }
    div[data-testid="stTextInput"] input { color: #E3E3E3 !important; background-color: #1E1F20 !important; border-radius: 10px; border: 1px solid #444; }
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
    except: 
        return False

def login_user(email, password):
    response = supabase.table("users").select("password").eq("email", email).execute()
    if response.data and response.data[0]["password"] == make_hashes(password): 
        return True
    return False

def save_chat(email, session_name, messages):
    try:
        supabase.table("chats").delete().eq("user_email", email).eq("session_name", session_name).execute()
        supabase.table("chats").insert({"user_email": email, "session_name": session_name, "messages": messages}).execute()
    except: 
        pass

def load_chats(email):
    response = supabase.table("chats").select("session_name, messages").eq("user_email", email).execute()
    sessions = {row["session_name"]: row["messages"] for row in response.data}
    return sessions if sessions else {"New Chat": []}

# ================= ৪. অডিও ও স্ট্রিমিং =================
def generate_audio_edge(text, speed="+0%"):
    try:
        lang = detect(text)
        voice = 'bn-BD-NabanitaNeural' if lang == 'bn' else 'en-US-AriaNeural'
    except: 
        voice = 'en-US-AriaNeural'
    async def _generate():
        communicate = edge_tts.Communicate(text, voice, rate=speed)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": 
                audio_data += chunk["data"]
        return audio_data
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return io.BytesIO(loop.run_until_complete(_generate()))
    except: 
        return None

def stream_groq_response(chat_history, persona_prompt):
    system_msg = {"role": "system", "content": persona_prompt}
    stream = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=[system_msg] + chat_history, temperature=0.7, max_tokens=1500, stream=True)
    for chunk in stream:
        if chunk.choices[0].delta.content: 
            yield chunk.choices[0].delta.content

# ================= ৫. অটো-লগইন সিস্টেম =================
if "logged_in" not in st.session_state: 
    st.session_state.logged_in = False
if "user_email" not in st.session_state: 
    st.session_state.user_email = ""
if not st.session_state.logged_in and "email" in st.query_params:
    st.session_state.logged_in = True
    st.session_state.user_email = st.query_params["email"]
    st.rerun()

# ================= ৬. লগইন পেজ =================
if not st.session_state.logged_in:
    st.title("✨ Welcome to Ultimate AI")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab1:
        l_email = st.text_input("Email", key="l_email")
        l_pass = st.text_input("Password", type="password", key="l_pass")
        if st.button("Login", use_container_width=True):
            if login_user(l_email, l_pass):
                st.session_state.logged_in = True
                st.session_state.user_email = l_email
                st.query_params["email"] = l_email
                st.rerun()
            else: 
                st.error("Invalid credentials")
    with tab2:
        s_email = st.text_input("Email", key="s_email")
        s_pass = st.text_input("Password", type="password", key="s_pass")
        if st.button("Sign Up", use_container_width=True):
            if create_user(s_email, s_pass): 
                st.success("Account created! Please login.")
            else: 
                st.error("Email already exists.")
    st.stop()

# ================= ৭. সাইডবার (মেনু) =================
with st.sidebar:
    st.markdown("### ✨ Super AI")
    if st.button("✏️ New Chat", use_container_width=True):
        new_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
        st.session_state.chat_sessions[new_id] = []
        st.session_state.current_session = new_id
        st.rerun()
    
    search_query = st.text_input("🔍 Search chats", placeholder="Type to search...")
    st.markdown("---")
    
    st.markdown("#### 🎭 AI Personalities")
    persona_choice = st.radio("Choose AI Version", [
        "🚀 Nova (Smart & Fast)",
        "😎 Vibe (Friendly & Witty)",
        "🧠 Pro (Professional & Detailed)",
        "🎓 Sir English (Strict Teacher)",
        "⚙️ Custom Persona"
    ])
    
    # এখানে স্পেসিং (Indentation) ঠিক করা হয়েছে
    if persona_choice == "⚙️ Custom Persona":
        persona_prompt = st.text_area("Custom Instructions:", "You are a helpful AI.")
    elif persona_choice == "🎓 Sir English (Strict Teacher)":
        persona_prompt = "You are 'Sir English', a highly professional, strict English teacher. Correct grammar, explain in Bengali, be encouraging but strict."
    elif persona_choice == "😎 Vibe (Friendly & Witty)":
        persona_prompt = "You are Vibe AI. Be friendly, slightly humorous, and use emojis. Keep answers concise and fun."
    elif persona_choice == "🧠 Pro (Professional & Detailed)":
        persona_prompt = "You are Pro AI, a professional, highly intelligent AI assistant. Provide detailed, structured, and accurate answers."
    else:
        persona_prompt = "You are Nova, an incredibly smart and fast AI. Answer clearly and efficiently."

    st.markdown("---")
    st.markdown("#### 🛠️ Tools")
    tool = st.selectbox("Choose Tool", ["💬 Chat", "🎨 Image Gen", "📊 Data Viz"])
    
    st.markdown("---")
    st.markdown("#### 💬 Recent")
    
    if "chat_sessions" not in st.session_state:
        st.session_state.chat_sessions = load_chats(st.session_state.user_email)
    
    filtered_sessions = [s for s in st.session_state.chat_sessions.keys() if search_query.lower() in s.lower()]
    for s in filtered_sessions:
        if st.button(f"💬 {s}", use_container_width=True):
            st.session_state.current_session = s
            st.rerun()

    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.query_params.clear()
        st.rerun()

# ================= ৮. মেইন অ্যাপ লজিক =================
if "current_session" not in st.session_state:
    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

# --- টুল: চ্যাট ---
if tool == "💬 Chat":
    for message in current_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if len(current_messages) == 0:
        st.markdown("<h3 style='text-align: center; margin-top: 50px;'>What are you thinking today?</h3>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🎨 Create an image"):
                st.session_state.quick_prompt = "Generate an image of a futuristic city"
                st.rerun()
        with col2:
            if st.button("📰 Today's headlines"):
                st.session_state.quick_prompt = "What are the top tech news today?"
                st.rerun()
        with col3:
            if st.button("📚 Explain Pythagoras"):
                st.session_state.quick_prompt = "Explain the Pythagorean theorem simply."
                st.rerun()

    prompt = st.chat_input("Ask anything...")
    if "quick_prompt" in st.session_state and st.session_state.quick_prompt:
        prompt = st.session_state.quick_prompt
        st.session_state.quick_prompt = None

    if prompt:
        current_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): 
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                answer = st.write_stream(stream_groq_response(current_messages[-10:], persona_prompt))
            current_messages.append({"role": "assistant", "content": answer})
            save_chat(st.session_state.user_email, st.session_state.current_session, current_messages)

# --- টুল: ইমেজ জেনারেটর ---
elif tool == "🎨 Image Gen":
    st.title("🎨 AI Image Generator")
    img_prompt = st.text_input("Describe your image:")
    if st.button("Generate Image"):
        if img_prompt:
            with st.spinner("Painting..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, use_container_width=True)

# --- টুল: ডেটা ভিজুয়ালাইজার ---
elif tool == "📊 Data Viz":
    st.title("📊 Data Visualization")
    csv_file = st.file_uploader("Upload CSV", type=["csv"])
    if csv_file:
        df = pd.read_csv(csv_file)
        st.write("Preview:", df.head())
        chart_prompt = st.text_input("Ask AI to draw a chart (e.g., 'Draw a bar chart of Sales')")
        if st.button("Generate Chart"):
            if chart_prompt:
                with st.spinner("Generating Chart..."):
                    sys_prompt = f"You are a data analyst. The df has columns: {list(df.columns)}. Write ONLY python code using 'plotly.express as px' to plot. Store result in 'fig'."
                    response = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": chart_prompt}], temperature=0.1)
                    code = response.choices[0].message.content.replace("```python", "").replace("```", "").strip()
                    local_vars = {'df': df, 'px': px}
                    exec(code, globals(), local_vars)
                    st.plotly_chart(local_vars['fig'], use_container_width=True)
