import streamlit as st
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch
import os

@st.cache_resource
def load_model():
    # আপনার Hugging Face মডেলের নাম
    hf_adapter_id = "Tafik/sir-english-lora" 
    
    base_model_name = "Qwen/Qwen2.5-0.5B-Instruct"
    tokenizer = AutoTokenizer.from_pretrained(base_model_name)
    
    model = AutoModelForCausalLM.from_pretrained(
        base_model_name, 
        torch_dtype=torch.float16
    )
    
    # সরাসরি Hugging Face থেকে লোড
    model = PeftModel.from_pretrained(model, hf_adapter_id)
    return model, tokenizer

st.title("স্যার ইংলিশ - AI Teacher")
st.write("আমাকে ইংরেজিতে প্রশ্ন করুন!")

model, tokenizer = load_model()

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
        with st.spinner("উত্তর তৈরি করছি..."):
            messages = [{"role": "user", "content": prompt}]
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(text, return_tensors="pt")
            outputs = model.generate(**inputs, max_new_tokens=128)
            response = tokenizer.decode(outputs[0], skip_special_tokens=True)
            if "assistant" in response:
                response = response.split("assistant")[-1].strip()
            st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
