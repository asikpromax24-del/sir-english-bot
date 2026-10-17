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

st.set_page_config(page_title="Super AI - Pro", page_icon="🧠", layout="wide")

# API Clients
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# --- Voice Generation ---
def generate_audio_edge(text):
    try:
        lang = detect(text)
        voice_map = {
            'bn': 'bn-BD-NabanitaNeural', 'en': 'en-US-AriaNeural', 
            'ru': 'ru-RU-SvetlanaNeural', 'ar': 'ar-SA-ZariyahNeural', 
            'hi': 'hi-IN-SwaraNeural', 'zh-cn': 'zh-CN-XiaoxiaoNeural'
        }
        voice = voice_map.get(lang, 'en-US-AriaNeural')
    except:
        voice = 'en-US-AriaNeural'

    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return audio_data

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_bytes = loop.run_until_complete(_generate())
        return io.BytesIO(audio_bytes)
    except:
        return None

# --- Chat Session Management ---
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {"Chat 1": []}
if "current_session" not in st.session_state:
    st.session_state.current_session = "Chat 1"

# --- Sidebar Menu ---
st.sidebar.title("🧠 Super AI Modes")

# New Chat Button
if st.sidebar.button("➕ New Chat Session"):
    new_chat_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
    st.session_state.chat_sessions[new_chat_id] = []
    st.session_state.current_session = new_chat_id
    st.rerun()

# Select Session
session_list = list(st.session_state.chat_sessions.keys())
st.session_state.current_session = st.sidebar.selectbox("Select Chat History", session_list, index=session_list.index(st.session_state.current_session))
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

mode = st.sidebar.radio("Choose a mode:", ["💬 Chat & Analyze", "🎨 Generate Image"])

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Settings")

persona_choice = st.sidebar.selectbox(
    "Select AI Persona",
    ["General Assistant", "Strict English Teacher", "Expert Python Coder"]
)
persona_prompts = {
    "General Assistant": "You are a super intelligent AI assistant. Answer accurately.",
    "Strict English Teacher": "You are a strict English teacher. Correct grammar, explain in Bengali if needed.",
    "Expert Python Coder": "You are a senior Python developer. Write clean code with explanations."
}

auto_search = st.sidebar.checkbox("🌐 Enable Auto Web Search", value=False)
enable_voice = st.sidebar.checkbox("🔊 Enable Voice Output", value=True)

if st.sidebar.button("🗑️ Clear Current Chat"):
    st.session_state.chat_sessions[st.session_state.current_session] = []
    st.rerun()

# --- Main Chat Interface ---
if mode == "💬 Chat & Analyze":
    st.title("💬 Chat, Voice & Data Analysis")
    
    # Render history
    for message in current_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                with st.expander("📋 Copy Response"):
                    st.code(message["content"], language="text")

    # File Uploaders
    with st.expander("📁 Upload Files (PDF, Image, CSV)"):
        uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
        csv_file = st.file_uploader("Upload CSV for Data Analysis", type=["csv"])
        audio_value = st.audio_input("Record a voice message")

    prompt = st.chat_input("Type your prompt here...")

    if prompt or audio_value:
        user_text = prompt
        
        # Audio input processing
        if audio_value:
            st.info("Transcribing audio...")
            with open("temp_audio.wav", "wb") as f:
                f.write(audio_value.getbuffer())
            with open("temp_audio.wav", "rb") as f:
                transcription = groq_client.audio.transcriptions.create(
                    file=("temp_audio.wav", f.read()),
                    model="whisper-large-v3",
                )
            user_text = transcription.text
            st.success(f"**You said:** {user_text}")

        if not user_text:
            user_text = "Please analyze this file."
            
        current_messages.append({"role": "user", "content": user_text})
        with st.chat_message("user"):
            st.markdown(user_text)

        with st.chat_message("assistant"):
            # 1. Data Analysis (CSV)
            if csv_file:
                with st.spinner("Analyzing CSV Data..."):
                    try:
                        df = pd.read_csv(csv_file)
                        data_context = f"Here is a summary of the uploaded CSV data:\n{df.head(10).to_string()}\n\nTotal rows: {len(df)}"
                        
                        chat_history = [
                            {"role": "system", "content": f"{persona_prompts[persona_choice]}\n\nData Context:\n{data_context}"},
                            {"role": "user", "content": user_text}
                        ]
                        response = groq_client.chat.completions.create(
                            model="openai/gpt-oss-120b",
                            messages=chat_history,
                            temperature=0.5,
                            max_tokens=1500
                        )
                        answer = response.choices[0].message.content
                        st.markdown(answer)
                        current_messages.append({"role": "assistant", "content": answer})
                        with st.expander("📋 Copy Response"):
                            st.code(answer, language="text")
                        
                        if enable_voice:
                            audio_data = generate_audio_edge(answer)
                            if audio_data: st.audio(audio_data, format="audio/mp3")
                        st.rerun()
                    except Exception as e:
                        st.error(f"CSV Analysis Error: {str(e)}")

            # 2. File Analysis (PDF/Image)
            elif uploaded_file:
                with st.spinner("Analyzing file..."):
                    try:
                        gemini_model = genai.GenerativeModel('gemini-3.8-flash')
                        file_bytes = uploaded_file.getvalue()
                        mime_type = uploaded_file.type
                        response = gemini_model.generate_content([user_text, {"mime_type": mime_type, "data": file_bytes}])
                        answer = response.text
                        st.markdown(answer)
                        current_messages.append({"role": "assistant", "content": answer})
                        with st.expander("📋 Copy Response"):
                            st.code(answer, language="text")
                        
                        if enable_voice:
                            audio_data = generate_audio_edge(answer)
                            if audio_data: st.audio(audio_data, format="audio/mp3")
                        st.rerun()
                    except Exception as e:
                        st.error(f"File Error: {str(e)}")

            # 3. Auto Web Search or Normal Chat
            else:
                with st.spinner("Thinking..."):
                    try:
                        context = ""
                        # Auto Web Search Logic
                        if auto_search:
                            st.info("🔍 Searching the web...")
                            ddgs = DDGS()
                            results = list(ddgs.text(user_text, max_results=3))
                            if results:
                                context = "\n".join([f"Snippet: {r['body']}" for r in results])
                                context = f"\n\nLive Web Search Results:\n{context}\n\nUse these results to answer."

                        chat_history = [{"role": "system", "content": persona_prompts[persona_choice] + context}] + [{"role": m["role"], "content": m["content"]} for m in current_messages[-20:]]
                        
                        response = groq_client.chat.completions.create(
                            model="openai/gpt-oss-120b",
                            messages=chat_history,
                            temperature=0.7,
                            max_tokens=1500
                        )
                        answer = response.choices[0].message.content
                        st.markdown(answer)
                        current_messages.append({"role": "assistant", "content": answer})
                        with st.expander("📋 Copy Response"):
                            st.code(answer, language="text")

                        if enable_voice:
                            audio_data = generate_audio_edge(answer)
                            if audio_data: st.audio(audio_data, format="audio/mp3")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

# --- Image Generation ---
elif mode == "🎨 Generate Image":
    st.title("🎨 AI Image Generator")
    img_prompt = st.text_input("Image Prompt:", placeholder="e.g., A beautiful sunset")
    if st.button("Generate Image"):
        if img_prompt:
            with st.spinner("Painting..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, use_container_width=True)
