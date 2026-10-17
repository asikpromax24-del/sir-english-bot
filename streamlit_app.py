import streamlit as st
from groq import Groq

st.set_page_config(page_title="Super AI - Pro", page_icon="🧠", layout="centered")

st.title("🧠 Super AI - All-in-One Assistant")
st.write("I am an advanced AI. I can teach English, translate any language, write code, and answer anything you ask.")

client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask me anything in any language..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            # সব ক্ষমতা সম্পন্ন সুপার প্রম্পট
            system_prompt = {
                "role": "system", 
                "content": """You are 'Super AI', a highly advanced, omnipotent AI assistant. You have the following capabilities:
                1. You are an expert English Teacher. If the user asks about English or makes grammar mistakes, teach and correct them professionally.
                2. You are a master programmer. You can write code in any language (Python, HTML, C++, etc.).
                3. You are an expert translator. You understand and can reply in Bengali, English, Hindi, Arabic, Spanish, and all other languages.
                4. You can write essays, stories, emails, and solve complex problems.
                5. Answer based on what the user asks. If they ask in Bengali, reply in Bengali (but gently encourage learning English if the context is teaching). 
                Be smart, be helpful, and be extremely capable. Do not limit yourself to just being a teacher; you are a genius assistant."""
            }
            
            # আগের ১০টি মেসেজ মনে রাখবে (Memory)
            chat_history = [system_prompt] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]]
            
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=chat_history,
                temperature=0.7, # বুদ্ধিমত্তা এবং ক্রিয়েটিভিটির জন্য একটু বাড়ানো হলো
                max_tokens=1500 # লম্বা উত্তর দেওয়ার জন্য
            )
            
            answer = response.choices[0].message.content
            st.markdown(answer)
            
    st.session_state.messages.append({"role": "assistant", "content": answer})
