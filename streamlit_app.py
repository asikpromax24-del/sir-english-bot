import streamlit as st
from groq import Groq
import google.generativeai as genai
from duckduckgo_search import DDGS
import urllib.parse
import streamlit.components.v1 as components

st.set_page_config(page_title="Super AI - Pro", page_icon="🧠", layout="wide")

# API Clients
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# বাংলা থেকে ইংরেজি অনুবাদ করার ফাংশন (Gemini ব্যবহার করে)
def translate_to_english(text):
    prompt = f"Translate the following Bengali or mixed text into a detailed English image generation prompt. Only output the English translation, nothing else:\n\n{text}"
    try:
        # ট্রান্সলেশনের জন্য Gemini ব্যবহার করা হলো (কম রেস্ট্রিক্টিভ)
        gemini_model = genai.GenerativeModel('gemini-3.8-flash')
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return text # অনুবাদ ব্যর্থ হলে আসল টেক্সটই পাঠাবে

# Sidebar Menu
st.sidebar.title("🧠 Super AI Modes")
mode = st.sidebar.radio("Choose a mode:", ["💬 Chat & Analyze", "🎨 Generate Image", "🌐 Web Search"])

if "messages" not in st.session_state:
    st.session_state.messages = []

if mode == "💬 Chat & Analyze":
    st.title("💬 Chat, Voice & File Analysis")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    with st.expander("📁 Upload File or 🎤 Record Voice"):
        uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
        audio_value = st.audio_input("Record a voice message")

    prompt = st.chat_input("Type your prompt here...")

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
            with st.spinner("Thinking..."):
                try:
                    if uploaded_file:
                        gemini_model = genai.GenerativeModel('gemini-3.8-flash')
                        file_bytes = uploaded_file.getvalue()
                        mime_type = uploaded_file.type
                        
                        response = gemini_model.generate_content([
                            user_text,
                            {"mime_type": mime_type, "data": file_bytes}
                        ])
                        answer = response.text
                    else:
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
    st.write("Describe the image you want to create (English or Bengali).")
    
    img_prompt = st.text_input("Image Prompt:", placeholder="e.g., A beautiful sunset over a calm sea, digital art")
    
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
                    from ddgs import DDGS
                    ddgs = DDGS()
                    
                    # নতুন ddgs লাইব্রেরি দিয়ে সার্চ
                    results = list(ddgs.text(search_query, max_results=5))
                    
                    # যদি সাধারণ সার্চে কিছু না পাওয়া যায়, তবে নিউজ সার্চ করবে
                    if not results:
                        results = list(ddgs.news(search_query, max_results=5))
                    
                    if not results:
                        st.warning("সার্চ ইঞ্জিন থেকে কোনো তথ্য পাওয়া যায়নি। অনুগ্রহ করে অন্য কোনো প্রশ্ন লিখে চেষ্টা করুন।")
                    else:
                        context = "\n\n".join([f"Title: {r.get('title', '')}\nSnippet: {r.get('body', '')}" for r in results])
                        
                        system_prompt = f"You are a smart AI assistant. Based on the following live web search results, answer the user's question accurately. If the results don't contain the answer, say 'I couldn't find the specific answer in the latest web results.'\n\nSearch Results:\n{context}"
                        
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
                    st.error(f"সার্চ করতে সমস্যা হচ্ছে: {str(e)}")
        else:
            st.warning("Please enter a search query.")
