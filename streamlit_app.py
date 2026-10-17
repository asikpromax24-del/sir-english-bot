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
st.set_page_config(page_title="Super AI Pro", page_icon="🧠", layout="wide", initial_sidebar_state="collapsed")

custom_css = """
<style>
    #MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}
    .stApp { background-color: #0E1117; color: #FAFAFA !important; }
    
    /* চ্যাট মেসেজ বক্স */
    div[data-testid="stChatMessage"] { 
        background-color: #1E232B; border-radius: 10px; padding: 15px; margin-bottom: 10px; color: #FAFAFA !important;
    }
    div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li, div[data-testid="stChatMessage"] span,
    div[data-testid="stChatMessage"] h1, div[data-testid="stChatMessage"] h2, div[data-testid="stChatMessage"] h3 { 
        color: #FAFAFA !important; 
    }
    div[data-testid="stChatMessage"] table { border-collapse: collapse; width: 100%; margin: 10px 0; }
    div[data-testid="stChatMessage"] th, div[data-testid="stChatMessage"] td { color: #FAFAFA !important; border: 1px solid #555 !important; padding: 8px; }
    
    /* ইনপুট বক্স ফিক্স */
    div[data-testid="stChatInput"] { background-color: #1E232B !important; border-radius: 10px; }
    div[data-testid="stChatInput"] > div { background-color: #1E232B !important; border: 1px solid #444 !important; border-radius: 10px; }
    div[data-testid="stChatInput"] textarea { color: #FAFAFA !important; background-color: transparent !important; }
    div[data-testid="stChatInput"] textarea::placeholder { color: #888 !important; }
    div[data-testid="stChatInput"] button { background-color: #2B313A !important; border-radius: 5px !important; }
    div[data-testid="stChatInput"] button svg { fill: #FAFAFA !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# API Clients
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# ================= ডেটাবেস সেটআপ (চ্যাট সেভের জন্য) =================
def init_db():
    conn = sqlite3.connect('super_ai.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chats (session_name TEXT, messages TEXT)''')
    conn.commit()
    return conn

conn = init_db()

def save_chat(session_name, messages):
    c = conn.cursor()
    messages_json = json.dumps(messages)
    c.execute("DELETE FROM chats WHERE session_name=?", (session_name,))
    c.execute("INSERT INTO chats (session_name, messages) VALUES (?, ?)", (session_name, messages_json))
    conn.commit()

def load_chats():
    c = conn.cursor()
    c.execute("SELECT session_name, messages FROM chats")
    rows = c.fetchall()
    sessions = {}
    for row in rows:
        sessions[row[0]] = json.loads(row[1])
    return sessions if sessions else {"Chat 1": []}

# ================= অডিও জেনারেটর =================
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

# ================= লাইভ টাইপিং ফাংশন =================
def stream_groq_response(chat_history):
    stream = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=chat_history,
        temperature=0.7,
        max_tokens=1500,
        stream=True
    )
    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

# ================= মেইন অ্যাপ =================
st.title("🧠 Super AI Pro")

# সেশন ম্যানেজমেন্ট
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_chats()
if "current_session" not in st.session_state:
    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]

# সেটিংস ও টুলস
with st.expander("⚙️ Settings & Tools", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        mode = st.selectbox("Choose Tool", ["💬 Chat & Analyze", "🎨 Image Generator", "📊 Data Visualization"])
    with col2:
        persona_choice = st.selectbox("AI Persona", ["General Assistant", "Strict English Teacher", "Expert Python Coder"])
        persona_prompts = {"General Assistant": "You are a super intelligent AI assistant.", "Strict English Teacher": "You are a strict English teacher.", "Expert Python Coder": "You are a senior Python developer."}
        persona_prompt = persona_prompts[persona_choice]
    
    auto_search = st.checkbox("🌐 Enable Auto Web Search")
    enable_voice = st.checkbox("🔊 Enable Auto Voice Output", value=True)
    voice_speed = st.select_slider("Voice Speed", options=["-50%", "-25%", "+0%", "+25%", "+50%"], value="+0%")

# চ্যাট সেশন ম্যানেজার
with st.expander("🗂️ Chat Sessions", expanded=False):
    session_list = list(st.session_state.chat_sessions.keys())
    selected_session = st.selectbox("Select Chat", session_list, index=session_list.index(st.session_state.current_session))
    
    colA, colB = st.columns(2)
    with colA:
        if st.button("➕ New Chat"):
            new_chat_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
            st.session_state.chat_sessions[new_chat_id] = []
            st.session_state.current_session = new_chat_id
            st.rerun()
    with colB:
        if st.button("🗑️ Clear Chat"):
            st.session_state.chat_sessions[st.session_state.current_session] = []
            save_chat(st.session_state.current_session, [])
            st.rerun()
            
    if selected_session != st.session_state.current_session:
        st.session_state.current_session = selected_session
        st.rerun()

# ================= অ্যাপ লজিক =================
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

if mode == "💬 Chat & Analyze":
    # চ্যাট হিস্ট্রি রেন্ডার
    for message in current_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    with st.expander("📁 Upload File (PDF, Image)"):
        uploaded_file = st.file_uploader("Upload File", type=["pdf", "png", "jpg", "jpeg"])
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
        save_chat(st.session_state.current_session, current_messages)
        
        with st.chat_message("user"): st.markdown(user_text)

        with st.chat_message("assistant"):
            if uploaded_file:
                # ইমেজ ভিশন (Gemini)
                with st.spinner("Analyzing file..."):
                    try:
                        gemini_model = genai.GenerativeModel('gemini-3.8-flash')
                        response = gemini_model.generate_content([user_text, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
                        answer = response.text
                        st.markdown(answer)
                        current_messages.append({"role": "assistant", "content": answer})
                        save_chat(st.session_state.current_session, current_messages)
                        
                        if enable_voice:
                            audio_data = generate_audio_edge(answer, voice_speed)
                            if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)
                    except Exception as e: st.error(f"Error: {str(e)}")
            else:
                # লাইভ টাইপিং (Groq)
                try:
                    context = ""
                    if auto_search:
                        results = list(DDGS().text(user_text, max_results=3))
                        if results: context = "\n".join([f"Snippet: {r['body']}" for r in results])
                    
                    final_prompt = persona_prompt + context + "\n\nIMPORTANT: Reply in clear text. Use standard Markdown tables. Reply in the user's language."
                    chat_history = [{"role": "system", "content": final_prompt}] + [{"role": m["role"], "content": m["content"]} for m in current_messages[-20:]]
                    
                    # st.write_stream দিয়ে লাইভ টাইপিং দেখানো
                    answer = st.write_stream(stream_groq_response(chat_history))
                    
                    current_messages.append({"role": "assistant", "content": answer})
                    save_chat(st.session_state.current_session, current_messages)
                    
                    if enable_voice:
                        audio_data = generate_audio_edge(answer, voice_speed)
                        if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)
                except Exception as e: st.error(f"Error: {str(e)}")

elif mode == "🎨 Image Generator":
    img_prompt = st.text_input("Image Prompt:")
    if st.button("Generate Image"):
        if img_prompt:
            with st.spinner("Painting..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, use_container_width=True)

elif mode == "📊 Data Visualization":
    csv_file = st.file_uploader("Upload CSV", type=["csv"])
    if csv_file:
        df = pd.read_csv(csv_file)
        st.write("### Data Preview:", df.head())
        chart_prompt = st.text_input("What kind of chart do you want?")
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
                    except Exception as e: st.error(f"Error: {str(e)}")
