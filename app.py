import os
import gdown
import gradio as gr
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch

# Drive থেকে মডেল ডাউনলোড (ফোল্ডার আইডি দিয়ে)
folder_id = "1L-beiQXuaQ-BBZ5DU7o4UaJRRmCUIQRV"
gdown.download_folder(id=folder_id, output="./lora_model", quiet=False)

base_model_name = "Qwen/Qwen2.5-0.5B-Instruct"
adapter_path = "./lora_model"

tokenizer = AutoTokenizer.from_pretrained(base_model_name)
model = AutoModelForCausalLM.from_pretrained(base_model_name, torch_dtype=torch.float32)
model = PeftModel.from_pretrained(model, adapter_path)
model = model.merge_and_unload()

def chat_with_model(message, history):
    messages = [{"role": "user", "content": message}]
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(text, return_tensors="pt")
    outputs = model.generate(**inputs, max_new_tokens=128)
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    if "assistant" in response:
        response = response.split("assistant")[-1].strip()
    return response

gr.ChatInterface(fn=chat_with_model).launch(
    server_name="0.0.0.0", 
    server_port=int(os.environ.get("PORT", 7860))
)
