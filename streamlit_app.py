import streamlit as st
from groq import Groq
import google.generativeai as genai
from duckduckgo_search import DDGS
import urllib.parse
import os

st.set_page_config(page_title="Super AI - Pro", page_icon="🧠", layout="wide")

# API Clients
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Sidebar Menu
st.sidebar.title("🧠 Super AI Modes")
mode = st.sidebar.radio("Choose a mode:", ["💬 Chat & Analyze", "🎨 Generate Image", "🌐 Web Search"])

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

if mode == "💬 Chat & Analyze":
    st.title("💬 Chat, Voice & File Analysis")
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # File Uploader & Audio Input
    with st.expander("📁 Upload File or 🎤 Record Voice"):
        uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
        audio_value = st.audio_input("Record a voice message")

    # Chat Input
    prompt = st.chat_input("Type your prompt here...")

    if prompt or audio_value:
        user_text = prompt
        
        # Handle Audio (Speech to Text via Groq)
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
            with st.spinner("Thinking..."):
                try:
                    if uploaded_file:
                        # File Analysis via Gemini
                        gemini_model = genai.GenerativeModel('gemini-3.8-flash')
                        file_bytes = uploaded_file.getvalue()
                        mime_type = uploaded_file.type
                        
                        response = gemini_model.generate_content([
                            user_text,
                            {"mime_type": mime_type, "data": file_bytes}
                        ])
                        answer = response.text
                    else:
                        # Normal Chat via Groq
                        chat_history = [{"role": "system", "content": "You are a super intelligent AI assistant. You teach English, write code, translate, and answer everything accurately."}] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]]
                        response = groq_client.chat.completions.create(
                            model="openai/gpt-oss-120b",
                            messages=chat_history,
                            temperature=0.7,
                            max_tokens=1500
                        )
                        answer = response.choices[0].message.content
                    
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                except Exception as e:
                    st.error(f"Error: {str(e)}")

elif mode == "🎨 Generate Image":
    st.title("🎨 AI Image Generator")
    st.write("Describe the image you want to create.")
    
    img_prompt = st.text_input("Image Prompt:", placeholder="e.g., A beautiful sunset over a calm sea, digital art")
    
    if st.button("Generate Image"):
        if img_prompt:
            with st.spinner("Painting your image..."):
                # Using Pollinations AI (Free, No API key needed)
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, caption=img_prompt, use_container_width=True)
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
                    # Search DuckDuckGo
                    results = DDGS().text(search_query, max_results=5)
                    context = "\n\n".join([f"Title: {r['title']}\nSnippet: {r['body']}" for r in results])
                    
                    # Summarize with Groq
                    system_prompt = f"You are a smart AI. Use the following web search results to answer the user's question. Be accurate and mention where the info came from if possible.\n\nSearch Results:\n{context}"
                    
                    response = groq_client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": search_query}
                        ],
                        temperature=0.5,
                        max_tokens=1000
                    )
                    st.markdown(response.choices[0].message.content)
                except Exception as e:
                    st.error(f"Search Error: {str(e)}")
        else:
            st.warning("Please enter a search query.")
