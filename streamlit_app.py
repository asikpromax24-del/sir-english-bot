import streamlit as st
from groq import Groq
import google.generativeai as genai
import os

st.set_page_config(page_title="Super AI - Pro", page_icon="🧠", layout="centered")
st.title("🧠 Super AI - Multimodal Assistant")
st.write("I can teach, translate, write code, and now I can see your images and read your PDFs!")

# API Keys Setup
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])

# Gemini Model for Files
gemini_model = genai.GenerativeModel('gemini-3.8-flash')
# Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# File Uploader (Image & PDF)
uploaded_file = st.file_uploader("Upload an Image or PDF to analyze", type=["pdf", "png", "jpg", "jpeg"])

# Chat Input
prompt = st.chat_input("Ask anything...")

if prompt or uploaded_file:
    user_content = prompt if prompt else "Please analyze this file and explain it to me."
    
    if uploaded_file:
        user_content += f"\n*[Uploaded File: {uploaded_file.name}]*"

    st.session_state.messages.append({"role": "user", "content": user_content})
    with st.chat_message("user"):
        st.markdown(user_content)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            try:
                if uploaded_file:
                    # Use Gemini for File (Image/PDF)
                    file_bytes = uploaded_file.getvalue()
                    mime_type = uploaded_file.type
                    
                    gemini_prompt = prompt if prompt else "Analyze this file carefully. If it's an English text, correct errors and explain in Bengali. If it's an image, describe it and translate any text."
                    
                    response = gemini_model.generate_content([
                        gemini_prompt,
                        {"mime_type": mime_type, "data": file_bytes}
                    ])
                    answer = response.text
                else:
                    # Use Groq for Text (Faster)
                    system_prompt = {
                        "role": "system", 
                        "content": "You are 'Super AI', a highly advanced AI assistant. You teach English, write code, translate, and answer anything. Be smart and helpful."
                    }
                    chat_history = [system_prompt] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]]
                    
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
                st.error(f"Oops! Something went wrong: {str(e)}")
