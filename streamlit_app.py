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

# ================= ১. পেজ কনফিগারেশন ও ডার্ক থিম ফিক্স =================
st.set_page_config(page_title="Super AI & Sir English", page_icon="🧠", layout="wide", initial_sidebar_state="expanded")

# নতুন এবং নিখুঁত CSS (সব লেখা ও বাটন দৃশ্যমান)
custom_css = """
<style>
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;} 
    header[data-testid="stHeader"] { background-color: transparent !important; }
    
    .stApp { background-color: #0E1117; color: #FAFAFA !important; }
    
    /* চ্যাট মেসেজ ডিজাইন */
    div[data-testid="stChatMessage"] { 
        background-color: #1E232B; border-radius: 10px; padding: 15px; margin-bottom: 10px; color: #FAFAFA !important;
    }
    div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li, div[data-testid="stChatMessage"] span,
    div[data-testid="stChatMessage"] h1, div[data-testid="stChatMessage"] h2, div[data-testid="stChatMessage"] h3,
    div[data-testid="stChatMessage"] strong { 
        color: #FAFAFA !important; 
    }
    div[data-testid="stChatMessage"] table { border-collapse: collapse; width: 100%; margin: 10px 0; }
    div[data-testid="stChatMessage"] th, div[data-testid="stChatMessage"] td { color: #FAFAFA !important; border: 1px solid #555 !important; padding: 8px; }
    
    /* চ্যাট ইনপুট বক্স ফিক্স */
    div[data-testid="stChatInput"] { background-color: #1E232B !important; border-radius: 10px; }
    div[data-testid="stChatInput"] > div { background-color: #1E232B !important; border: 1px solid #444 !important; border-radius: 10px; }
    div[data-testid="stChatInput"] textarea { color: #FAFAFA !important; background-color: transparent !important; }
    div[data-testid="stChatInput"] textarea::placeholder { color: #888 !important; }
    div[data-testid="stChatInput"] button { background-color: #2B313A !important; border-radius: 5px !important; }
    div[data-testid="stChatInput"] button svg { fill: #FAFAFA !important; }
    
    /* ================= লগইন এবং ইনপুট বক্স ফিক্স ================= */
    div[data-testid="stTextInput"] input, 
    div[data-testid="stTextArea"] textarea {
        color: #FAFAFA !important; /* লেখা সাদা */
        background-color: #1E232B !important; /* ব্যাকগ্রাউন্ড ডার্ক */
        border: 1px solid #555 !important;
    }
    div[data-testid="stTextInput"] label, 
    div[data-testid="stTextArea"] label,
    div[data-testid="stSelectbox"] label {
        color: #FAFAFA !important;
    }
    
    /* ================= বাটন ফিক্স ================= */
    .stButton > button {
        color: #FAFAFA !important; 
        background-color: #2B313A !important; 
        border: 1px solid #555 !important;
        width: 100%;
    }
    .stButton > button:hover {
        background-color: #444 !important;
        border: 1px solid #FAFAFA !important;
    }
    
    /* সাইডবার স্টাইল */
    section[data-testid="stSidebar"] { background-color: #0E1117; border-right: 1px solid #333; }
    section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3 {
        color: #FAFAFA !important;
    }
    
    /* এক্সপ্যান্ডার ফিক্স */
    .streamlit-expanderHeader { color: #FAFAFA !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# ================= ২. API Clients & DB Setup =================
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

def init_db():
    conn = sqlite3.connect('super_ai.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chats (username TEXT, session_name TEXT, messages TEXT)''')
    conn.commit()
    return conn

conn = init_db()

def save_chat(username, session_name, messages):
    c = conn.cursor()
    c.execute("DELETE FROM chats WHERE username=? AND session_name=?", (username, session_name))
    c.execute("INSERT INTO chats (username, session_name, messages) VALUES (?, ?, ?)", (username, session_name, json.dumps(messages)))
    conn.commit()

def load_chats(username):
    c = conn.cursor()
    c.execute("SELECT session_name, messages FROM chats WHERE username=?", (username,))
    rows = c.fetchall()
    sessions = {row[0]: json.loads(row[1]) for row in rows}
    return sessions if sessions else {"Chat 1": []}

# ================= ৩. ফাংশনসমূহ (Audio, Stream) =================
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

def stream_groq_response(chat_history):
    stream = groq_client.chat.completions.create(
        model="openai/gpt-oss-120b", messages=chat_history, temperature=0.7, max_tokens=1500, stream=True
    )
    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

# ================= ৪. ইউজার অথেনটিকেশন (লগইন) =================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username" not in st.session_state: st.session_state.username = ""

if not st.session_state.logged_in:
    st.title("🔐 Welcome to Super AI & Sir English")
    st.markdown("Please log in to continue.")
    user = st.text_input("Username (e.g., admin)")
    pwd = st.text_input("Password (Demo: **admin123**)", type="password")
    if st.button("Login"):
        if user and pwd == "admin123":
            st.session_state.logged_in = True
            st.session_state.username = user
            st.rerun()
        else: st.error("Wrong Username or Password!")
    st.stop()

# ================= ৫. সাইডবার ও নেভিগেশন =================
st.sidebar.title("🧠 Navigation")
st.sidebar.success(f"User: {st.session_state.username}")
if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.rerun()

# মোড সিলেকশন
app_mode = st.sidebar.radio("Select App Mode", ["🤖 Super AI (General)", "🎓 Sir English (Teacher)"])

# চ্যাট সেশন ম্যানেজমেন্ট (সাইডবারে)
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

# সেটিংস
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Settings")

if app_mode == "🤖 Super AI (General)":
    tool = st.sidebar.selectbox("Choose Tool", ["💬 Chat & Analyze", "🎨 Image Generator", "📊 Data Visualization"])
    persona_prompt = "You are a super intelligent AI assistant."
    auto_search = st.sidebar.checkbox("🌐 Enable Auto Web Search")
else:
    tool = st.sidebar.selectbox("Teacher Tool", ["💬 Chat with Teacher", "📝 Placement Test", "🎤 Spoken Practice"])
    persona_prompt = "You are 'Sir English', a highly professional, strict, and expert English teacher. You understand Bengali. Your goal is to correct the user's English, point out mistakes immediately, explain the rules in Bengali, and provide high-level examples. Be encouraging but strict."
    auto_search = False

enable_voice = st.sidebar.checkbox("🔊 Enable Auto Voice Output", value=True)
voice_speed = st.sidebar.select_slider("Voice Speed", options=["-50%", "-25%", "+0%", "+25%", "+50%"], value="+0%")

if st.sidebar.button("🗑️ Clear Current Chat"):
    st.session_state.chat_sessions[st.session_state.current_session] = []
    save_chat(st.session_state.username, st.session_state.current_session, [])
    st.rerun()

# প্রোগ্রেস ড্যাশবোর্ড (সাইডবারে)
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Progress Dashboard")
total_msgs = sum(len(msgs) for msgs in st.session_state.chat_sessions.values())
st.sidebar.metric("Total Messages Sent", total_msgs)
st.sidebar.metric("Active Chat Sessions", len(st.session_state.chat_sessions))

# ================= ৬. মেইন অ্যাপ লজিক =================

if app_mode == "🎓 Sir English (Teacher)" and tool == "📝 Placement Test":
    st.title("📝 English Placement Test")
    st.write("Answer these 5 questions. The AI will determine your CEFR level (A1 to C2).")
    
    q1 = st.text_input("1. What is the past tense of 'go'?")
    q2 = st.text_input("2. Write a sentence using 'because'.")
    q3 = st.text_input("3. Correct this sentence: 'She don't like apples.'")
    q4 = st.text_input("4. What is the difference between 'affect' and 'effect'?")
    q5 = st.text_area("5. Write a short paragraph (3-4 sentences) about your favorite hobby.")
    
    if st.button("Submit Test & Get Level"):
        if q1 and q2 and q3 and q4 and q5:
            with st.spinner("Evaluating your level..."):
                eval_prompt = f"You are an English examiner. Evaluate these answers and determine the user's CEFR level (A1, A2, B1, B2, C1, or C2). Give the level first, then explain why in Bengali. \nAnswers:\n1: {q1}\n2: {q2}\n3: {q3}\n4: {q4}\n5: {q5}"
                response = groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=[{"role": "user", "content": eval_prompt}]
                )
                st.success(response.choices[0].message.content)
        else:
            st.warning("Please answer all questions.")

elif tool in ["💬 Chat & Analyze", "💬 Chat with Teacher", "🎤 Spoken Practice"]:
    st.title("💬 " + tool)
    
    # চ্যাট হিস্ট্রি রেন্ডার
    for message in current_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                with st.expander("📋 Copy"):
                    st.code(message["content"], language="text")

    # রিজেনারেট বাটন
    if current_messages and current_messages[-1]["role"] == "assistant":
        if st.button("🔄 Regenerate Last Response"):
            current_messages.pop()
            save_chat(st.session_state.username, st.session_state.current_session, current_messages)
            st.session_state.trigger_regen = True
            st.rerun()

    with st.expander("📁 Upload File (PDF, Image) / 🎤 Voice Input"):
        uploaded_file = st.file_uploader("Upload File", type=["pdf", "png", "jpg", "jpeg"])
        audio_value = st.audio_input("Record a voice message")

    placeholder_text = "Type your English sentence here for correction..." if app_mode == "🎓 Sir English (Teacher)" else "Type your prompt here..."
    prompt = st.chat_input(placeholder_text)

    if prompt or audio_value or st.session_state.get("trigger_regen", False):
        st.session_state.trigger_regen = False
        
        if prompt:
            user_text = prompt
        elif current_messages and current_messages[-1]["role"] == "user":
            user_text = current_messages[-1]["content"]
        else:
            user_text = "Please analyze this file."

        if audio_value:
            with st.spinner("Transcribing..."):
                with open("temp_audio.wav", "wb") as f: f.write(audio_value.getbuffer())
                with open("temp_audio.wav", "rb") as f:
                    user_text = groq_client.audio.transcriptions.create(file=("temp_audio.wav", f.read()), model="whisper-large-v3").text

        if prompt or audio_value:
            current_messages.append({"role": "user", "content": user_text})
            save_chat(st.session_state.username, st.session_state.current_session, current_messages)
            with st.chat_message("user"): st.markdown(user_text)

        with st.chat_message("assistant"):
            if uploaded_file:
                with st.spinner("Analyzing file..."):
                    try:
                        gemini_model = genai.GenerativeModel('gemini-3.8-flash')
                        response = gemini_model.generate_content([user_text, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
                        answer = response.text
                        st.markdown(answer)
                        current_messages.append({"role": "assistant", "content": answer})
                        save_chat(st.session_state.username, st.session_state.current_session, current_messages)
                        
                        if enable_voice:
                            audio_data = generate_audio_edge(answer, voice_speed)
                            if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)
                    except Exception as e: st.error(f"Error: {str(e)}")
            else:
                try:
                    context = ""
                    if auto_search:
                        results = list(DDGS().text(user_text, max_results=3))
                        if results: context = "\n".join([f"Snippet: {r['body']}" for r in results])
                    
                    final_prompt = persona_prompt + context + "\n\nIMPORTANT: Reply in clear text. Use standard Markdown tables. Reply in the user's language."
                    chat_history = [{"role": "system", "content": final_prompt}] + [{"role": m["role"], "content": m["content"]} for m in current_messages[-20:]]
                    
                    answer = st.write_stream(stream_groq_response(chat_history))
                    
                    current_messages.append({"role": "assistant", "content": answer})
                    save_chat(st.session_state.username, st.session_state.current_session, current_messages)
                    
                    if enable_voice:
                        audio_data = generate_audio_edge(answer, voice_speed)
                        if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)
                except Exception as e: st.error(f"Error: {str(e)}")

elif tool == "🎨 Image Generator":
    st.title("🎨 AI Image Generator")
    img_prompt = st.text_input("Image Prompt:")
    if st.button("Generate Image"):
        if img_prompt:
            with st.spinner("Painting..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, use_container_width=True)

elif tool == "📊 Data Visualization":
    st.title("📊 AI Data Visualization")
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
