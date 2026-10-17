import streamlit as st
from groq import Groq
import google.generativeai as genai
from ddgs import DDGS
import urllib.parse
import edge_tts
import asyncio
import io
from langdetect import detect

st.set_page_config(page_title="Super AI - Pro", page_icon="🧠", layout="wide")

# API Clients
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# অডিও জেনারেট করার ফাংশন (অটোমেটিক ডিটেকশন)
def generate_audio_edge(text):
    try:
        lang = detect(text)
        voice_map = {
            'bn': 'bn-BD-NabanitaNeural', 'en': 'en-US-AriaNeural', 
            'ru': 'ru-RU-SvetlanaNeural', 'ar': 'ar-SA-ZariyahNeural', 
            'hi': 'hi-IN-SwaraNeural', 'zh-cn': 'zh-CN-XiaoxiaoNeural', 
            'fr': 'fr-FR-DeniseNeural', 'es': 'es-ES-ElviraNeural', 
            'de': 'de-DE-KatjaNeural', 'ja': 'ja-JP-NanamiNeural', 
            'ko': 'ko-KR-SunHiNeural', 'pt': 'pt-BR-FranciscaNeural', 
            'tr': 'tr-TR-EmelNeural', 'fa': 'fa-IR-DilaraNeural', 
            'ur': 'ur-PK-UzmaNeural'
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

# বাংলা থেকে ইংরেজি অনুবাদ করার ফাংশন (ছবি তৈরির জন্য)
def translate_to_english(text):
    prompt = f"Translate the following text into a detailed English image generation prompt. Only output the English translation, nothing else:\n\n{text}"
    try:
        gemini_model = genai.GenerativeModel('gemini-3.8-flash')
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except:
        return text

# লাইভ টাইপিং (Streaming) রেসপন্স জেনারেটর
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

# ---------------- Sidebar Menu ----------------
st.sidebar.title("🧠 Super AI Modes")
mode = st.sidebar.radio("Choose a mode:", ["💬 Chat & Analyze", "🎨 Generate Image", "🌐 Web Search"])

st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Settings")

# পার্সোনা সিলেক্টর (ChatGPT-র কাস্টম ইনস্ট্রাকশনের মতো)
persona_choice = st.sidebar.selectbox(
    "Select AI Persona",
    ["General Assistant", "Strict English Teacher", "Expert Python Coder", "Story Writer"]
)
persona_prompts = {
    "General Assistant": "You are a super intelligent AI assistant. Answer accurately.",
    "Strict English Teacher": "You are a strict English teacher. Correct the user's grammar, explain rules in Bengali if needed, and provide examples.",
    "Expert Python Coder": "You are a senior Python developer. Write clean, efficient code with explanations.",
    "Story Writer": "You are a creative storyteller. Write engaging and descriptive stories."
}

# ভয়েস অন/অফ টগল
enable_voice = st.sidebar.checkbox("🔊 Enable Voice Output", value=True)

# চ্যাট ক্লিয়ার বাটন
if st.sidebar.button("🗑️ Clear Chat History"):
    st.session_state.messages = []
    st.rerun()

# চ্যাট হিস্ট্রি ডাউনলোড
if "messages" not in st.session_state:
    st.session_state.messages = []

if st.session_state.messages:
    chat_text = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.messages])
    st.sidebar.download_button(
        label="💾 Download Chat History",
        data=chat_text,
        file_name="super_ai_chat.txt",
        mime="text/plain"
    )

# ---------------- Main App Logic ----------------
if mode == "💬 Chat & Analyze":
    st.title("💬 Chat, Voice & File Analysis")
    
    # পুরো চ্যাট হিস্ট্রি রেন্ডার
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant":
                with st.expander("📋 Copy Response"):
                    st.code(message["content"], language="text")

    with st.expander("📁 Upload File or 🎤 Record Voice"):
        uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
        audio_value = st.audio_input("Record a voice message")

    prompt = st.chat_input("Type your prompt here...")

    # রিজেনারেট করার বাটন (শুধু আগের মেসেজ থাকলে দেখাবে)
    if len(st.session_state.messages) > 0 and prompt is None and not audio_value:
        if st.button("🔄 Regenerate Last Response"):
            st.session_state.messages.pop() # শেষ উত্তরটা মুছে ফেলবে
            st.rerun()

    if prompt or audio_value:
        user_text = prompt
        
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
            
        st.session_state.messages.append({"role": "user", "content": user_text})
        with st.chat_message("user"):
            st.markdown(user_text)

        with st.chat_message("assistant"):
            # ফাইল থাকলে Gemini, না থাকলে Groq
            if uploaded_file:
                with st.spinner("Analyzing file..."):
                    try:
                        gemini_model = genai.GenerativeModel('gemini-3.8-flash')
                        file_bytes = uploaded_file.getvalue()
                        mime_type = uploaded_file.type
                        response = gemini_model.generate_content([
                            user_text,
                            {"mime_type": mime_type, "data": file_bytes}
                        ])
                        answer = response.text
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                        with st.expander("📋 Copy Response"):
                            st.code(answer, language="text")
                        
                        if enable_voice:
                            audio_data = generate_audio_edge(answer)
                            if audio_data: st.audio(audio_data, format="audio/mp3")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
            else:
                # লাইভ টাইপিং (Streaming) রেসপন্স
                try:
                    chat_history = [{"role": "system", "content": persona_prompts[persona_choice]}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-20:]]
                    
                    # st.write_stream দিয়ে লাইভ টাইপিং দেখানো হচ্ছে
                    answer = st.write_stream(stream_groq_response(chat_history))
                    
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    with st.expander("📋 Copy Response"):
                        st.code(answer, language="text")
                    
                    if enable_voice:
                        audio_data = generate_audio_edge(answer)
                        if audio_data: st.audio(audio_data, format="audio/mp3")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

elif mode == "🎨 Generate Image":
    st.title("🎨 AI Image Generator")
    st.write("Describe the image you want to create.")
    
    img_prompt = st.text_input("Image Prompt:", placeholder="e.g., A beautiful sunset over a calm sea")
    
    if st.button("Generate Image"):
        if img_prompt:
            with st.spinner("Translating prompt and painting your image..."):
                english_prompt = translate_to_english(img_prompt)
                safe_prompt = urllib.parse.quote(english_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, caption=f"Generated from: {english_prompt}", use_container_width=True)
        else:
            st.warning("Please enter a prompt first.")

elif mode == "🌐 Web Search":
    st.title("🌐 Live Web Search")
    st.write("I will search the live internet to answer your question accurately.")
    
    search_query = st.text_input("What do you want to search?", placeholder="e.g., What is the latest news on AI?")
    
    if st.button("Search"):
        if search_query:
            with st.spinner("Searching the web..."):
                try:
                    opt_prompt = f"Extract the best English search engine keywords from this query. Only output the keywords, nothing else.\nQuery: {search_query}"
                    opt_response = groq_client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=[{"role": "user", "content": opt_prompt}],
                        temperature=0.1,
                        max_tokens=50
                    )
                    optimized_query = opt_response.choices[0].message.content.strip()
                    if not optimized_query: optimized_query = search_query
                        
                    ddgs = DDGS()
                    results = list(ddgs.text(optimized_query, max_results=5))
                    if not results: results = list(ddgs.news(optimized_query, max_results=5))
                    
                    if not results:
                        st.warning(f"সার্চ ইঞ্জিন থেকে কোনো তথ্য পাওয়া যায়নি।")
                    else:
                        context = "\n\n".join([f"Title: {r.get('title', '')}\nSnippet: {r.get('body', '')}" for r in results])
                        system_prompt = f"You are a smart AI assistant. Based on the following live web search results, answer the user's question accurately. The user's original question was: '{search_query}'.\n\nSearch Results:\n{context}"
                        
                        response = groq_client.chat.completions.create(
                            model="openai/gpt-oss-120b",
                            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": search_query}],
                            temperature=0.5,
                            max_tokens=1000
                        )
                        final_answer = response.choices[0].message.content
                        st.markdown(final_answer)
                        with st.expander("📋 Copy Search Result"):
                            st.code(final_answer, language="text")

                        if enable_voice:
                            audio_data = generate_audio_edge(final_answer)
                            if audio_data: st.audio(audio_data, format="audio/mp3")
                            
                except Exception as e:
                    st.error(f"সার্চ করতে সমস্যা হচ্ছে: {str(e)}")
        else:
            st.warning("Please enter a search query.")
