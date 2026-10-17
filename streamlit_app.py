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

# ================= ১. পেজ কনফিগারেশন ও ডার্ক থিম (Gemini স্টাইল) =================
st.set_page_config(page_title="Super AI - Gemini Style", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

custom_css = """
<style>
    /* সাইডবার ডিজাইন */
    [data-testid="stSidebar"] { background-color: #131314; border-right: 1px solid #333; }
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: #E3E3E3 !important; }
    
    /* মেইন ব্যাকগ্রাউন্ড */
    .stApp { background-color: #131314; color: #E3E3E3 !important; }
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; max-width: 900px !important; }
    
    /* বাটন ডিজাইন (Gemini স্টাইল রাউন্ডেড) */
    .stButton > button { 
        color: #E3E3E3 !important; background-color: #1E1F20 !important; 
        border: none !important; border-radius: 20px !important; 
        text-align: left !important; padding: 10px 15px !important;
        transition: background-color 0.2s;
    }
    .stButton > button:hover { background-color: #333537 !important; }
    
    /* চ্যাট ইনপুট বক্স (Gemini স্টাইল) */
    div[data-testid="stChatInput"] { background-color: #1E1F20 !important; border-radius: 30px !important; border: 1px solid #444; }
    div[data-testid="stChatInput"] textarea { color: #E3E3E3 !important; }
    
    /* চ্যাট মেসেজ ডিজাইন */
    div[data-testid="stChatMessage"] { background-color: transparent; padding: 10px 0; }
    div[data-testid="stChatMessage"] p { color: #E3E3E3 !important; font-size: 16px; line-height: 1.6; }
    
    /* ইনপুট ফিল্ড */
    div[data-testid="stTextInput"] input { color: #E3E3E3 !important; background-color: #1E1F20 !important; border-radius: 10px; border: 1px solid #444; }
    
    /* হাইড ডিফল্ট এলিমেন্ট */
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
    except Exception as e: print(f"Save Error: {e}")

def load_chats(email):
    response = supabase.table("chats").select("session_name, messages").eq("user_email", email).execute()
    sessions = {row["session_name"]: row["messages"] for row in response.data}
    return sessions if sessions else {"New Chat": []}

# ================= ৪. অডিও ও স্ট্রিমিং =================
def generate_audio_edge(text, speed="+0%"):
    try:
        lang = detect(text)
        voice_map = {'bn': 'bn-BD-NabanitaNeural', 'en': 'en-US-AriaNeural'}
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

def stream_groq_response(chat_history, persona_prompt):
    system_msg = {
        "role": "system", 
        "content": persona_prompt + "\n\nIMPORTANT: You are a highly intelligent, witty, and friendly AI. Do NOT sound like a robot. Use humor, emojis, and engaging language. Answer in the user's language."
    }
    full_history = [system_msg] + chat_history
    stream = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=full_history, temperature=0.8, max_tokens=1500, stream=True)
    for chunk in stream:
        if chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

# ================= ৫. অটো-লগইন সিস্টেম =================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""

if not st.session_state.logged_in and "email" in st.query_params:
    st.session_state.logged_in = True
    st.session_state.user_email = st.query_params["email"]
    st.rerun()

# ================= ৬. লগইন পেজ =================
if not st.session_state.logged_in:
    st.title("✨ Welcome to Gemini Style AI")
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    with tab1:
        login_email = st.text_input("Email", key="l_email")
        login_pass = st.text_input("Password", type="password", key="l_pass")
        if st.button("Login", use_container_width=True):
            if login_user(login_email, login_pass):
                st.session_state.logged_in = True
                st.session_state.user_email = login_email
                st.query_params["email"] = login_email
                st.rerun()
            else: st.error("Invalid credentials")
    with tab2:
        new_email = st.text_input("Email", key="s_email")
        new_pass = st.text_input("Password", type="password", key="s_pass")
        if st.button("Sign Up", use_container_width=True):
            if create_user(new_email, new_pass): st.success("Account created! Please login.")
            else: st.error("Email already exists.")
    st.stop()

# ================= ৭. সাইডবার (Gemini স্টাইল মেনু) =================
with st.sidebar:
    st.markdown("### ✨ Super AI")
    
    # New Chat Button
    if st.button("✏️ New chat", use_container_width=True):
        new_chat_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
        st.session_state.chat_sessions[new_chat_id] = []
        st.session_state.current_session = new_chat_id
        st.rerun()

    # Chat Search
    search_query = st.text_input("🔍 Search chats", placeholder="Type to search...")
    
    st.markdown("---")
    
    # Modes
    app_mode = st.radio("Select Mode", ["💬 Chat", "🎓 Student (Teacher)", "🎨 Images", "📊 Data"])
    
    st.markdown("---")
    st.markdown("### ⚙️ Customize")
    
    # Personas
    persona_choice = st.selectbox("AI Persona", ["Witty Assistant", "Strict Teacher", "Python Coder", "Custom"])
    if persona_choice == "Custom":
        persona_prompt = st.text_area("Enter custom instructions:")
    elif persona_choice == "Strict Teacher":
        persona_prompt = "You are 'Sir English', a strict English teacher. Correct grammar and explain in Bengali."
    elif persona_choice == "Python Coder":
        persona_prompt = "You are a senior Python developer. Write clean code."
    else:
        persona_prompt = "You are a witty, smart, and helpful AI assistant."

    # Temporary Chat Toggle
    is_temp_chat = st.checkbox("🕵️ Temporary Chat (Not Saved)")
    
    st.markdown("---")
    st.markdown("### 💬 Recent")
    
    # Chat History List (Filtered by search)
    if "chat_sessions" not in st.session_state:
        st.session_state.chat_sessions = load_chats(st.session_state.user_email)
    
    session_list = list(st.session_state.chat_sessions.keys())
    filtered_sessions = [s for s in session_list if search_query.lower() in s.lower()]
    
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

# --- মোড: Chat / Teacher ---
if app_mode in ["💬 Chat", "🎓 Student (Teacher)"]:
    st.title(f"{app_mode} with AI")
    
    for message in current_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    with st.expander("📁 Upload File / 🎤 Voice"):
        uploaded_file = st.file_uploader("Upload", type=["pdf", "png", "jpg"])
        audio_value = st.audio_input("Record voice")

    prompt = st.chat_input("Ask Gemini-style AI anything...")

    if prompt or audio_value:
        if not prompt and audio_value:
            with st.spinner("Transcribing..."):
                with open("temp.wav", "wb") as f: f.write(audio_value.getbuffer())
                with open("temp.wav", "rb") as f:
                    prompt = groq_client.audio.transcriptions.create(file=("temp.wav", f.read()), model="whisper-large-v3").text

        current_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)

        with st.chat_message("assistant"):
            if uploaded_file:
                with st.spinner("Analyzing..."):
                    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                    response = gemini_model.generate_content([prompt, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
                    answer = response.text
                    st.markdown(answer)
            else:
                answer = st.write_stream(stream_groq_response(current_messages[-10:], persona_prompt))
            
            current_messages.append({"role": "assistant", "content": answer})
            
            # সেভ লজিক (Temporary chat হলে সেভ হবে না)
            if not is_temp_chat:
                save_chat(st.session_state.user_email, st.session_state.current_session, current_messages)
            
            # অডিও আউটপুট
            audio_data = generate_audio_edge(answer)
            if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)

# --- মোড: Images ---
elif app_mode == "🎨 Images":
    st.title("🎨 Image Generator")
    img_prompt = st.text_input("Describe your image:")
    if st.button("Generate"):
        if img_prompt:
            with st.spinner("Painting..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, use_container_width=True)

# --- মোড: Data ---
elif app_mode == "📊 Data":
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
