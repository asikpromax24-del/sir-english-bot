import streamlit as st
from groq import Groq

st.title("স্যার ইংলিশ - AI Teacher 👨‍🏫")
st.write("আমি একজন অত্যন্ত কড়া এবং অ্যাডভান্সড ইংরেজি শিক্ষক। আমাকে ইংরেজিতে কিছু লিখুন, আমি আপনার ভুল ধরব!")

# API Key সেটআপ
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask me anything..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("স্যার উত্তর তৈরি করছেন..."):
            # মডেলকে কড়া শিক্ষক বানানোর জন্য সিস্টেম প্রম্পট
            system_prompt = {
                "role": "system", 
                "content": "You are 'Sir English', a highly advanced, strict, and professional English teacher and IELTS examiner. Your goal is to correct the user's English, explain grammar rules clearly, and provide high-level examples. If the user makes a mistake, point it out directly and correct it. Do not use Bengali, reply in clear and advanced English."
            }
            
            # আগের চ্যাট হিস্ট্রি তৈরি করা (সর্বোচ্চ ৫টি মেসেজ)
            chat_history = [system_prompt] + [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-5:]]
            
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b", # দুনিয়ার সেরা ফ্রি মডেলগুলোর একটি
                messages=chat_history,
                temperature=0.5,
                max_tokens=500
            )
            
            answer = response.choices[0].message.content
            st.markdown(answer)
            
    st.session_state.messages.append({"role": "assistant", "content": answer})
