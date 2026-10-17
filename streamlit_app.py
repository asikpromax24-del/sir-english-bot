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
import re
import sqlite3
import json

# ১. পেজ কনফিগারেশন ও ডার্ক থিম
st.set_page_config(page_title="Super AI Pro", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .stChatFloatingInputContainer { background-color: #0E1117; }
    div[data-testid="stChatMessage"] { background-color: #1E232B; border-radius: 10px; padding: 10px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# API Clients
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ২. ডেটাবেস সেটআপ (চ্যাট সেভ করার জন্য)
def init_db():
    conn = sqlite3.connect('super_ai.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chats 
                 (username TEXT, session_name TEXT, messages TEXT)''')
    conn.commit()
    return conn

conn = init_db()

def save_chat(username, session_name, messages):
    c = conn.cursor()
    messages_json = json.dumps(messages)
    c.execute("DELETE FROM chats WHERE username=? AND session_name=?", (username, session_name))
    c.execute("INSERT INTO chats (username, session_name, messages) VALUES (?, ?, ?)", (username, session_name, messages_json))
    conn.commit()

def load_chats(username):
    c = conn.cursor()
    c.execute("SELECT session_name, messages FROM chats WHERE username=?", (username,))
    rows = c.fetchall()
    sessions = {}
    for row in rows:
        sessions[row[0]] = json.loads(row[1])
    return sessions if sessions else {"Chat 1": []}

# অডিও জেনারেটর (স্পিড কন্ট্রোলসহ)
def generate_audio_edge(text, speed="+0%"):
    try:
        lang = detect(text)
        voice_map = {'bn': 'bn-BD-NabanitaNeural', 'en': 'en-US-AriaNeural', 'ru': 'ru-RU-SvetlanaNeural', 'ar': 'ar-SA-ZariyahNeural', 'hi': 'hi-IN-SwaraNeural'}
        voice = voice_map.get(lang, 'en-US-AriaNeural')
    except: voice = 'en-US-AriaNeural'

    async def _generate():
        communicate = edge_tts.Communicate(text, voice, rate=speed)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": audio_data += chunk["data"]
        return audio_data
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return io.BytesIO(loop.run_until_complete(_generate()))
    except: return None

# ৩. লগইন সিস্টেম
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = "admin"

if not st.session_state.logged_in:
    st.title("🔐 Welcome to Super AI Pro")
    password = st.text_input("Enter Password (Demo Password: **admin123**)", type="password")
    if st.button("Login"):
        if password == "admin123":
            st.session_state.logged_in = True
            st.rerun()
        else: st.error("Wrong Password!")
    st.stop()

# --- সাইডবার ---
st.sidebar.title("🧠 Super AI Pro")
st.sidebar.success(f"User: {st.session_state.username}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# ডেটাবেস থেকে চ্যাট লোড করা
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_chats(st.session_state.username)
if "current_session" not in st.session_state:
    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]

if st.sidebar.button("➕ New Chat Session"):
    new_chat_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
    st.session_state.chat_sessions[new_chat_id] = []
    st.session_state.current_session = new_chat_id
    st.rerun()

session_list = list(st.session_state.chat_sessions.keys())
st.session_state.current_session = st.sidebar.selectbox("Select Chat History", session_list, index=session_list.index(st.session_state.current_session))
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

mode = st.sidebar.radio("Choose a Tool:", ["💬 Chat & Analyze", "🎨 Image Generator", "📊 Data Visualization"])

# সেটিংস
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Settings")
persona_choice = st.sidebar.selectbox("Select AI Persona", ["General Assistant", "Strict English Teacher", "Expert Python Coder", "Custom Persona"])
if persona_choice == "Custom Persona":
    custom_prompt = st.sidebar.text_area("Enter Custom Instructions (e.g., 'You are a doctor')", "You are a helpful AI.")
    persona_prompt = custom_prompt
else:
    persona_prompts = {"General Assistant": "You are a super intelligent AI assistant.", "Strict English Teacher": "You are a strict English teacher.", "Expert Python Coder": "You are a senior Python developer."}
    persona_prompt = persona_prompts[persona_choice]

auto_search = st.sidebar.checkbox("🌐 Enable Auto Web Search", value=False)
enable_voice = st.sidebar.checkbox("🔊 Enable Voice Output", value=True)
voice_speed = st.sidebar.select_slider("Voice Speed", options=["-50%", "-25%", "+0%", "+25%", "+50%"], value="+0%")

# ================= মেইন অ্যাপ লজিক =================
if mode == "💬 Chat & Analyze":
    st.title("💬 Chat, Voice & Data Analysis")
    for message in current_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                with st.expander("📋 Copy"): st.code(message["content"], language="text")

    with st.expander("📁 Upload File (PDF, Image)"):
        uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
        audio_value = st.audio_input("Record a voice message")

    prompt = st.chat_input("Type your prompt here...")

    if prompt or audio_value:
        user_text = prompt
        if audio_value:
            with st.spinner("Transcribing..."):
                with open("temp_audio.wav", "wb") as f: f.write(audio_value.getbuffer())
                with open("temp_audio.wav", "rb") as f:
                    user_text = groq_client.audio.transcriptions.create(file=("temp_audio.wav", f.read()), model="whisper-large-v3").text

        current_messages.append({"role": "user", "content": user_text})
        save_chat(st.session_state.username, st.session_state.current_session, current_messages)
        
        with st.chat_message("user"): st.markdown(user_text)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    if uploaded_file:
                        gemini_model = genai.GenerativeModel('gemini-3.8-flash')
                        response = gemini_model.generate_content([user_text, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
                        answer = response.text
                    else:
                        context = ""
                        if auto_search:
                            results = list(DDGS().text(user_text, max_results=3))
                            if results: context = "\n".join([f"Snippet: {r['body']}" for r in results])
                        
                        chat_history = [{"role": "system", "content": persona_prompt + context}] + [{"role": m["role"], "content": m["content"]} for m in current_messages[-20:]]
                        answer = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=chat_history, temperature=0.7, max_tokens=1500).choices[0].message.content
                    
                    st.markdown(answer)
                    current_messages.append({"role": "assistant", "content": answer})
                    save_chat(st.session_state.username, st.session_state.current_session, current_messages)
                    
                    if enable_voice:
                        audio_data = generate_audio_edge(answer, voice_speed)
                        if audio_data: st.audio(audio_data, format="audio/mp3")
                except Exception as e: st.error(f"Error: {str(e)}")

# ডেটা ভিজুয়ালাইজেশন ও ইমেজ জেনারেটর আগের মতোই থাকবে...
elif mode == "📊 Data Visualization":
    st.title("📊 AI Data Visualization")
    csv_file = st.file_uploader("Upload CSV", type=["csv"])
    if csv_file:
        df = pd.read_csv(csv_file)
        st.write("### Data Preview:", df.head())
        chart_prompt = st.text_input("What kind of chart do you want? (e.g., 'Draw a bar chart of Sales by Region')")
        if st.button("Generate Chart"):
            if chart_prompt:
                with st.spinner("Generating Chart..."):
                    try:
                        sys_prompt = f"You are a Python data analyst. The user has a pandas DataFrame named 'df' with columns: {list(df.columns)}. Write ONLY the python code using 'plotly.express as px' to plot what the user asked. The final figure must be stored in a variable named 'fig'. Do not include any markdown formatting."
                        response = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": chart_prompt}], temperature=0.1)
                        code = response.choices[0].message.content.replace("```python", "").replace("```", "").strip()
                        local_vars = {'df': df, 'px': px}
                        exec(code, globals(), local_vars)
                        st.plotly_chart(local_vars['fig'], use_container_width=True)
                    except Exception as e: st.error(f"চার্ট তৈরিতে সমস্যা: {str(e)}")

elif mode == "🎨 Image Generator":
    st.title("🎨 AI Image Generator")
    img_prompt = st.text_input("Image Prompt:")
    if st.button("Generate Image"):
        if img_prompt:
            with st.spinner("Painting..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, use_container_width=True)
