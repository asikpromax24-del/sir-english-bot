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

# ১. পেজ কনফিগারেশন ও কাস্টম ডার্ক থিম (প্রফেশনাল লুক)
st.set_page_config(page_title="Super AI Pro", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

custom_css = """
<style>
    /* Streamlit ডিফল্ট মেনু হাইড করা */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    /* চ্যাট ইন্টারফেস ডার্ক করা */
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .stChatFloatingInputContainer { background-color: #0E1117; }
    div[data-testid="stChatMessage"] { background-color: #1E232B; border-radius: 10px; padding: 10px; margin-bottom: 10px; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# API Clients
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# অডিও জেনারেটর
def generate_audio_edge(text):
    try:
        lang = detect(text)
        voice_map = {'bn': 'bn-BD-NabanitaNeural', 'en': 'en-US-AriaNeural', 'ru': 'ru-RU-SvetlanaNeural', 'ar': 'ar-SA-ZariyahNeural', 'hi': 'hi-IN-SwaraNeural'}
        voice = voice_map.get(lang, 'en-US-AriaNeural')
    except: voice = 'en-US-AriaNeural'

    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": audio_data += chunk["data"]
        return audio_data
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return io.BytesIO(loop.run_until_complete(_generate()))
    except: return None

# ২. ইউজার লগইন সিস্টেম (সহজ ডেমো)
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔐 Welcome to Super AI Pro")
    st.write("Please log in to continue.")
    password = st.text_input("Enter Password (Demo Password: **admin123**)", type="password")
    if st.button("Login"):
        if password == "admin123":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Wrong Password!")
    st.stop() # পাসওয়ার্ড না দিলে নিচের কোড রান হবে না

# --- সাইডবার মেনু (লগইন করার পর) ---
st.sidebar.title("🧠 Super AI Pro")
st.sidebar.success("Logged in as Admin")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# চ্যাট সেশন ম্যানেজমেন্ট
if "chat_sessions" not in st.session_state: st.session_state.chat_sessions = {"Chat 1": []}
if "current_session" not in st.session_state: st.session_state.current_session = "Chat 1"

if st.sidebar.button("➕ New Chat Session"):
    new_chat_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
    st.session_state.chat_sessions[new_chat_id] = []
    st.session_state.current_session = new_chat_id
    st.rerun()

session_list = list(st.session_state.chat_sessions.keys())
st.session_state.current_session = st.sidebar.selectbox("Select Chat History", session_list, index=session_list.index(st.session_state.current_session))
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

# মোড সিলেকশন (ইউটিউব বাদ দেওয়া হলো)
mode = st.sidebar.radio("Choose a Tool:", ["💬 Chat & Analyze", "🎨 Image Generator", "📊 Data Visualization"])

# সেটিংস
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Settings")
persona_choice = st.sidebar.selectbox("Select AI Persona", ["General Assistant", "Strict English Teacher", "Expert Python Coder"])
persona_prompts = {"General Assistant": "You are a super intelligent AI assistant.", "Strict English Teacher": "You are a strict English teacher.", "Expert Python Coder": "You are a senior Python developer."}
auto_search = st.sidebar.checkbox("🌐 Enable Auto Web Search", value=False)
enable_voice = st.sidebar.checkbox("🔊 Enable Voice Output", value=True)

# ================= মেইন অ্যাপ লজিক =================

# ১. চ্যাট ও অ্যানালাইসিস
if mode == "💬 Chat & Analyze":
    st.title("💬 Chat, Voice & Data Analysis")
    for message in current_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                with st.expander("📋 Copy"):
                    st.code(message["content"], language="text")

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
                        
                        chat_history = [{"role": "system", "content": persona_prompts[persona_choice] + context}] + [{"role": m["role"], "content": m["content"]} for m in current_messages[-20:]]
                        answer = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=chat_history, temperature=0.7, max_tokens=1500).choices[0].message.content
                    
                    st.markdown(answer)
                    current_messages.append({"role": "assistant", "content": answer})
                    if enable_voice:
                        audio_data = generate_audio_edge(answer)
                        if audio_data: st.audio(audio_data, format="audio/mp3")
                except Exception as e: st.error(f"Error: {str(e)}")

# ২. ডেটা ভিজুয়ালাইজেশন (CSV)
elif mode == "📊 Data Visualization":
    st.title("📊 AI Data Visualization")
    st.write("Upload a CSV file, and ask me to draw a chart.")
    csv_file = st.file_uploader("Upload CSV", type=["csv"])
    
    if csv_file:
        df = pd.read_csv(csv_file)
        st.write("### Data Preview:", df.head())
        
        chart_prompt = st.text_input("What kind of chart do you want? (e.g., 'Draw a bar chart of Sales by Region')")
        
        if st.button("Generate Chart"):
            if chart_prompt:
                with st.spinner("Generating Chart..."):
                    try:
                        sys_prompt = f"You are a Python data analyst. The user has a pandas DataFrame named 'df' with columns: {list(df.columns)}. Write ONLY the python code using 'plotly.express as px' to plot what the user asked. The final figure must be stored in a variable named 'fig'. Do not include any markdown formatting, just the pure python code."
                        user_prompt = f"User request: {chart_prompt}"
                        
                        response = groq_client.chat.completions.create(
                            model="openai/gpt-oss-120b",
                            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_prompt}],
                            temperature=0.1
                        )
                        code = response.choices[0].message.content.replace("```python", "").replace("```", "").strip()
                        
                        local_vars = {'df': df, 'px': px}
                        exec(code, globals(), local_vars)
                        fig = local_vars['fig']
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.error(f"চার্ট তৈরিতে সমস্যা হচ্ছে: {str(e)}")

# ৩. ইমেজ জেনারেটর
elif mode == "🎨 Image Generator":
    st.title("🎨 AI Image Generator")
    img_prompt = st.text_input("Image Prompt:")
    if st.button("Generate Image"):
        if img_prompt:
            with st.spinner("Painting..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, use_container_width=True)
