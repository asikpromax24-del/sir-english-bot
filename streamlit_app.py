import streamlit as st
from groq import Groq
import google.generativeai as genai
from ddgs import DDGS
import urllib.parse
import edge_tts
import asyncio
import io
from langdetect import detect
import json
import hashlib
import pandas as pd
import plotly.express as px
from supabase import create_client, Client
import requests
from bs4 import BeautifulSoup
import datetime

# ================= ১. পেজ কনফিগারেশন ও API ক্লায়েন্ট =================
st.set_page_config(page_title="ASIKERA AI", page_icon="logo.png", layout="wide", initial_sidebar_state="expanded")

groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# ================= ২. ডেটাবেস ফাংশন (Supabase) =================
def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()

def create_user(email, password):
    try: 
        supabase.table("users").insert({"email": email, "password": make_hashes(password)}).execute()
        return True
    except: return False

def login_user(email, password):
    try:
        response = supabase.table("users").select("password").eq("email", email).execute()
        return bool(response.data and response.data[0]["password"] == make_hashes(password))
    except: return False

def save_chat(email, session_name, messages):
    try:
        supabase.table("chats").delete().eq("user_email", email).eq("session_name", session_name).execute()
        supabase.table("chats").insert({"user_email": email, "session_name": session_name, "messages": messages}).execute()
    except: pass

def load_chats(email):
    try:
        response = supabase.table("chats").select("session_name, messages").eq("user_email", email).execute()
        sessions = {row["session_name"]: row["messages"] for row in response.data}
        return sessions if sessions else {"New Chat": []}
    except: return {"New Chat": []}

# ================= ৩. ভয়েস ও অডিও জেনারেটর (Edge-TTS) =================
def generate_audio_edge(text, voice_type="Female"):
    try:
        lang = detect(text)
        if lang == 'bn':
            voice = 'bn-BD-NabanitaNeural' if voice_type == "Female" else 'bn-BD-PradeepNeural'
        else:
            voice = 'en-US-AriaNeural' if voice_type == "Female" else 'en-US-GuyNeural'
    except: voice = 'en-US-AriaNeural'
        
    async def _generate():
        communicate = edge_tts.Communicate(text, voice)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": audio_data += chunk["data"]
        return audio_data
    try:
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        return io.BytesIO(loop.run_until_complete(_generate()))
    except: return None

# ================= ৪. থিম সেটিংস (লাইট ও ডার্ক মোড) =================
if "theme" not in st.session_state: st.session_state.theme = "Light"

if st.session_state.theme == "Light":
    bg_color, text_color, sidebar_bg, card_bg = "#F4F6F8", "#1A1A1A", "#FFFFFF", "#FFFFFF"
    border_color, input_bg = "#E5E7EB", "#F9FAFB"
else:
    bg_color, text_color, sidebar_bg, card_bg = "#1E1E1E", "#E0E0E0", "#191919", "#25252D"
    border_color, input_bg = "#333333", "#2A2A2A"

custom_css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
.stApp {{ background: {bg_color}; font-family: 'Inter', sans-serif; color: {text_color}; }}
[data-testid="stSidebar"] {{ background: {sidebar_bg}; border-right: 1px solid {border_color}; width: 280px !important; }}

/* ================= হেডার ও টুলবার ফিক্স ================= */
#MainMenu {{visibility: hidden;}} 
footer {{visibility: hidden;}} 
[data-testid="stHeader"] {{ background: transparent !important; }}
[data-testid="stToolbar"] {{ display: none !important; }} /* Share, Edit, Fork বাটন হাইড */
[data-testid="stDecoration"] {{ display: none !important; }}

/* মোবাইলে সাইডবার ওপেন করার বাটন (>>) দৃশ্যমান রাখা */
[data-testid="collapsedControl"] {{
    display: flex !important; visibility: visible !important;
    color: {text_color} !important; background-color: {border_color} !important;
    border-radius: 8px !important; position: fixed !important;
    top: 15px !important; left: 15px !important; z-index: 1000000 !important;
}}

.block-container {{ padding-top: 2rem !important; padding-bottom: 6rem !important; max-width: 850px !important; margin: 0 auto !important; }}
.stButton>button[kind="primary"] {{ background: #4D6BFE; border-radius: 10px; height: 40px; font-weight: 600; border: 0; color: white; }}
.stButton>button[kind="secondary"] {{ background: {input_bg}; border: 1px solid {border_color}; border-radius: 10px; color: {text_color}; padding: 5px; font-size: 13px; }}

div[data-testid="stChatMessage"] {{ background-color: transparent; padding: 10px 0; border: none; }}
div[data-testid="stChatMessage"] h1, div[data-testid="stChatMessage"] h2, div[data-testid="stChatMessage"] h3, div[data-testid="stChatMessage"] h4, div[data-testid="stChatMessage"] strong {{ color: {text_color} !important; margin-top: 15px !important; margin-bottom: 10px !important; }}
div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li {{ color: {text_color} !important; font-size: 15px !important; line-height: 1.6; }}

div[data-testid="stChatMessage"] table {{ display: block !important; overflow-x: auto !important; border-collapse: collapse !important; margin: 15px 0 !important; width: 100% !important; }}
div[data-testid="stChatMessage"] table th, div[data-testid="stChatMessage"] table td {{ color: {text_color} !important; border: 1px solid {border_color} !important; padding: 10px !important; background-color: {input_bg} !important; }}

div[data-testid="stChatMessage"] pre {{ background-color: {input_bg} !important; border: 1px solid {border_color} !important; border-radius: 8px !important; padding: 12px !important; }}
div[data-testid="stChatMessage"] code {{ color: #DC2626 !important; background-color: transparent !important; font-family: 'Courier New', monospace !important; }}

div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) {{ flex-direction: row-reverse; text-align: right; margin-left: auto; margin-right: 0; width: fit-content; max-width: 85%; }}
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) .stMarkdown {{ background: {input_bg}; border: 1px solid {border_color}; padding: 12px 18px; border-radius: 20px 20px 4px 20px; display: inline-block; }}
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) {{ margin-right: auto; margin-left: 0; width: 100%; }}
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) .stMarkdown {{ background: {card_bg}; border: 1px solid {border_color}; padding: 18px 20px; border-radius: 20px 20px 20px 4px; display: inline-block; box-shadow: 0 2px 8px rgba(0,0,0,0.04); width: 100%; }}

div[data-testid="stTextInput"] input {{ background-color: {input_bg} !important; color: {text_color} !important; border: 1px solid {border_color} !important; border-radius: 10px !important; }}
div[data-testid="stChatInput"] {{ background-color: {card_bg} !important; border-radius: 12px !important; border: 1px solid {border_color} !important; box-shadow: 0 4px 15px rgba(0,0,0,0.05); }}
div[data-testid="stChatInput"] > div {{ background-color: {card_bg} !important; }}
div[data-testid="stChatInput"] textarea {{ color: {text_color} !important; background-color: transparent !important; }}
div[data-testid="stChatInput"] button {{ background: #4D6BFE !important; border-radius: 8px !important; }}
div[data-testid="stChatInput"] button svg {{ fill: white !important; }}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {{ background-color: {input_bg} !important; color: {text_color} !important; border: 1px solid {border_color} !important; }}

.sidebar-title {{ font-size: 20px; font-weight: 700; color: {text_color}; margin: 0; }}
.sidebar-subtitle {{ font-size: 10px; color: #6B7280; letter-spacing: 1.5px; margin-top: 5px; }}
.divider {{ border-top: 1px solid {border_color}; margin: 15px 0; }}
.label-text {{ font-size: 12px; color: #6B7280; margin-bottom: 8px; font-weight: 600; text-transform: uppercase; }}
.user-card {{ display: flex; align-items: center; background: {input_bg}; padding: 10px; border-radius: 10px; border: 1px solid {border_color}; margin-bottom: 10px; }}
.user-avatar {{ background: #4D6BFE; color: white; border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; margin-right: 12px; }}
.user-email {{ font-size: 12px; color: {text_color}; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
</style>
"""

# ================= ৫. লগইন পেজ =================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if not st.session_state.logged_in and "email" in st.query_params:
    st.session_state.logged_in = True
    st.session_state.user_email = st.query_params["email"]
    st.rerun()

if not st.session_state.logged_in:
    st.markdown(f"""
    <style>
    .stApp {{ background: radial-gradient(circle at 10% 20%, rgba(139, 92, 246, 0.15), transparent 40%), radial-gradient(circle at 90% 80%, rgba(59, 130, 246, 0.15), transparent 40%), {bg_color} !important; }}
    div[data-testid="stForm"] {{ background: rgba(255, 255, 255, 0.8) !important; backdrop-filter: blur(20px) !important; border: 1px solid rgba(0, 0, 0, 0.05) !important; border-radius: 20px !important; padding: 40px !important; box-shadow: 0 10px 40px rgba(0, 0, 0, 0.08) !important; }}
    div[data-testid="stTextInput"] input {{ background-color: #FFFFFF !important; color: #111827 !important; border: 1px solid #D1D5DB !important; }}
    div[data-testid="stFormSubmitButton"] > button {{ background: linear-gradient(135deg, #8B5CF6, #3B82F6) !important; border: none !important; color: white !important; font-weight: 600 !important; }}
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center; font-weight: 800;'>⚡ ASIKERA</h1><p style='text-align: center; color: #6B7280; letter-spacing: 2px; font-size: 11px;'>ASIKUL'S KNOWLEDGE ERA</p>", unsafe_allow_html=True)
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        with tab1:
            with st.form("login_form"):
                l_email = st.text_input("Email", placeholder="you@company.com")
                l_pass = st.text_input("Password", type="password", placeholder="••••••••")
                if st.form_submit_button("Login", use_container_width=True):
                    if login_user(l_email, l_pass):
                        st.session_state.logged_in = True
                        st.session_state.user_email = l_email
                        st.query_params["email"] = l_email
                        st.rerun()
                    else: st.error("Invalid credentials.")
        with tab2:
            with st.form("signup_form"):
                s_email = st.text_input("Email", placeholder="you@company.com")
                s_pass = st.text_input("Password", type="password", placeholder="Min 6 characters")
                if st.form_submit_button("Sign Up", use_container_width=True):
                    if len(s_pass) < 6: st.warning("Password too short.")
                    elif create_user(s_email, s_pass): st.success("Account created! Please login.")
                    else: st.error("Email already registered.")
    st.stop()

# ================= ৬. মেইন অ্যাপ লজিক =================
st.markdown(custom_css, unsafe_allow_html=True)

if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_chats(st.session_state.user_email)
if "current_session" not in st.session_state:
    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]

CATEGORIES = [
    "💬 General Chat", "🎓 English Tutor", "👨‍💻 Coding Assistant", 
    "📚 Learning & Study", "✍️ Writing & Editing", "🔍 Deep Research", 
    "🎨 Image Generation", "📄 File/PDF Analyzer", "🌐 Web Search", 
    "📊 Data Analysis", "🌍 Translator", "🔗 URL Reader", 
    "🤖 Custom Persona", "📝 Text Summarizer", "💡 Idea Generator",
    "📧 Email Writer", "📱 Social Media Post", "📖 Story Writer",
    "🎯 IELTS Writing Evaluator", "🗣️ Interview Preparer",
    "✈️ Travel Planner", "🍳 Recipe Creator", "💪 Fitness Coach",
    "🧠 Psychology Advisor", "⚖️ Legal Advisor (Basic)",
    "🎬 Movie Recommender", "🎵 Music Recommender",
    "💰 Finance Advisor", "📈 Marketing Strategist",
    "🛠️ Task Automation"
]

with st.sidebar:
    col_logo, col_text = st.columns([1, 3])
    with col_logo:
        try: st.image("logo.png", use_container_width=True)
        except: st.markdown("⚡")
    with col_text:
        st.markdown(f"""<div style='padding-top: 5px;'><div class="sidebar-title">ASIKERA</div><div class="sidebar-subtitle">KNOWLEDGE ERA</div></div>""", unsafe_allow_html=True)
        
    st.write("") 
    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        new_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
        st.session_state.chat_sessions[new_id] = []
        st.session_state.current_session = new_id
        st.rerun()
        
    search_query = st.text_input("Search", placeholder="Search chats...", label_visibility="collapsed")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="label-text">✨ 30+ Modes</div>', unsafe_allow_html=True)
    selected_category = st.selectbox("Select Mode", CATEGORIES, label_visibility="collapsed")
    
    theme_toggle = st.checkbox("🌙 Dark Mode" if st.session_state.theme == "Light" else "☀️ Light Mode")
    if theme_toggle:
        st.session_state.theme = "Dark" if st.session_state.theme == "Light" else "Light"
        st.rerun()
        
    voice_gender = st.radio("Voice", ["Female", "Male"], horizontal=True)
    
    custom_persona = ""
    if selected_category == "🤖 Custom Persona":
        custom_persona = st.text_area("Define AI Personality:", "You are a helpful assistant.")
    
    # প্রম্পট ইঞ্জিন
    base_identity = "You are ASIKERA. Do not mention OpenAI or Google. "
    prompts = {
        "🎓 English Tutor": "You are Sir English, an elite IELTS examiner. Correct grammar, explain in Bengali.",
        "👨‍💻 Coding Assistant": "You are an expert programmer. Write clean, optimized code.",
        "📚 Learning & Study": "You are a brilliant tutor. Explain concepts simply.",
        "✍️ Writing & Editing": "You are a professional editor. Fix grammar and improve tone.",
        "🔍 Deep Research": "You are a deep research agent. Synthesize detailed reports.",
        "📝 Text Summarizer": "You are an expert summarizer. Extract key points into bullet points.",
        "💡 Idea Generator": "You are a creative brainstormer. Generate 10 unique ideas.",
        "📧 Email Writer": "You are a professional email writer. Write clear and polite emails.",
        "📱 Social Media Post": "You are a viral social media manager. Write engaging posts with emojis.",
        "📖 Story Writer": "You are a creative novelist. Write engaging stories.",
        "🎯 IELTS Writing Evaluator": "You are an IELTS examiner. Grade the writing on a 1-9 scale and explain errors.",
        "🗣️ Interview Preparer": "You are an HR manager. Ask interview questions and evaluate the answers.",
        "✈️ Travel Planner": "You are a travel agent. Create detailed itineraries.",
        "🍳 Recipe Creator": "You are a master chef. Provide recipes with ingredients and steps.",
        "💪 Fitness Coach": "You are a fitness coach. Provide workout plans and diet advice.",
        "🧠 Psychology Advisor": "You are a compassionate psychologist. Provide emotional support.",
        "⚖️ Legal Advisor (Basic)": "You are a legal advisor. Provide general legal information.",
        "🎬 Movie Recommender": "You are a movie buff. Recommend movies based on preferences.",
        "🎵 Music Recommender": "You are a music expert. Recommend songs.",
        "💰 Finance Advisor": "You are a financial advisor. Provide money-saving and investment tips.",
        "📈 Marketing Strategist": "You are a marketing expert. Create marketing plans.",
        "🛠️ Task Automation": "You are an automation expert. Create step-by-step workflows.",
        "🤖 Custom Persona": custom_persona if custom_persona else "You are a smart AI."
    }
    persona_prompt = base_identity + prompts.get(selected_category, "You are a smart and helpful AI.")

    if st.session_state.chat_sessions[st.session_state.current_session]:
        chat_text = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in st.session_state.chat_sessions[st.session_state.current_session]])
        st.download_button("📥 Export Chat (TXT)", data=chat_text, file_name="asikera_chat.txt", use_container_width=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="label-text">Recent</div>', unsafe_allow_html=True)
    
    filtered_sessions = [s for s in st.session_state.chat_sessions.keys() if search_query.lower() in s.lower()]
    for s in filtered_sessions:
        if st.button(f"💬 {s}", use_container_width=True, type="secondary"):
            st.session_state.current_session = s
            st.rerun()
            
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown(f"""<div class="user-card"><div class="user-avatar">👤</div><div class="user-email">{st.session_state.user_email}</div></div>""", unsafe_allow_html=True)
    
    if st.button("Logout", use_container_width=True, type="secondary"):
        st.session_state.logged_in = False
        st.query_params.clear()
        st.rerun()

# ================= ৭. ডাইনামিক টুলস এক্সিকিউশন =================
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

if selected_category == "🎨 Image Generation":
    st.markdown("### 🎨 AI Image Generator")
    img_prompt = st.text_input("Describe your image:")
    if st.button("Generate Image", type="primary") and img_prompt:
        with st.spinner("Painting..."):
            image_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(img_prompt)}?width=1024&height=1024&nologo=true"
            st.image(image_url, use_container_width=True)

elif selected_category == "📄 File/PDF Analyzer":
    st.markdown("### 📄 File Analyzer")
    uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
    file_query = st.text_input("What do you want to know about this file?")
    if st.button("Analyze File", type="primary") and uploaded_file and file_query:
        with st.spinner("Analyzing..."):
            try:
                gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                response = gemini_model.generate_content([file_query, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
                st.markdown(response.text)
            except Exception as e: st.error(f"Error: {e}")

elif selected_category == "📊 Data Analysis":
    st.markdown("### 📊 Data Visualization")
    csv_file = st.file_uploader("Upload CSV", type=["csv"])
    if csv_file:
        df = pd.read_csv(csv_file)
        st.write("Data Preview:", df.head())
        chart_prompt = st.text_input("Ask AI to draw a chart (e.g., 'Draw a bar chart of Sales')")
        if st.button("Generate Chart", type="primary") and chart_prompt:
            with st.spinner("Generating..."):
                try:
                    sys_prompt = f"Write ONLY Python code using 'plotly.express as px' for DataFrame 'df' with columns {list(df.columns)}. Store result in 'fig'."
                    res = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": chart_prompt}], temperature=0.1)
                    code = res.choices[0].message.content.replace("```python", "").replace("```", "").strip()
                    local_vars = {'df': df, 'px': px}
                    exec(code, globals(), local_vars)
                    st.plotly_chart(local_vars['fig'], use_container_width=True)
                except Exception as e: st.error(f"Error: {e}")

elif selected_category == "🌐 Web Search":
    st.markdown("### 🌐 Live Web Search")
    search_query = st.text_input("Search the web:")
    if st.button("Search", type="primary") and search_query:
        with st.spinner("Searching..."):
            try:
                results = list(DDGS().text(search_query, max_results=4))
                if results:
                    context = "\n".join([f"Snippet: {r['body']}" for r in results])
                    res = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "system", "content": f"Answer based on these search results:\n{context}"}, {"role": "user", "content": search_query}])
                    st.markdown(res.choices[0].message.content)
            except Exception as e: st.error(f"Error: {e}")

elif selected_category == "🔍 Deep Research":
    st.markdown("### 🔍 Agentic Deep Research")
    research_prompt = st.text_input("What should I research?")
    if st.button("Start Research", type="primary") and research_prompt:
        with st.spinner("Browsing live internet and generating report..."):
            try:
                query_gen = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "system", "content": "Generate 3 search queries based on this topic. Output ONLY the queries separated by newlines."}, {"role": "user", "content": research_prompt}])
                queries = query_gen.choices[0].message.content.strip().split('\n')
                all_results = []
                for q in queries:
                    if q.strip():
                        res = list(DDGS().text(q, max_results=3))
                        all_results.extend(res)
                context = "\n".join([f"Title: {r['title']}\nSnippet: {r['body']}" for r in all_results])
                final_report = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "system", "content": "Synthesize into a highly detailed report with headings."}, {"role": "user", "content": f"Topic: {research_prompt}\n\nResults:\n{context}"}], temperature=0.5, max_tokens=2000)
                st.markdown(final_report.choices[0].message.content)
            except Exception as e: st.error(f"Error: {e}")

elif selected_category == "🌍 Translator":
    st.markdown("### 🌍 Language Translator")
    col1, col2 = st.columns(2)
    with col1: src_lang = st.selectbox("From", ["Auto-Detect", "Bengali", "English", "Hindi", "Arabic"])
    with col2: tgt_lang = st.selectbox("To", ["English", "Bengali", "Hindi", "Arabic", "Spanish"])
    text_to_translate = st.text_area("Enter text to translate:")
    if st.button("Translate", type="primary") and text_to_translate:
        with st.spinner("Translating..."):
            prompt = f"Translate the following text from {src_lang} to {tgt_lang}. Only output the translation: \n\n{text_to_translate}"
            res = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "user", "content": prompt}])
            st.success(res.choices[0].message.content)

elif selected_category == "🔗 URL Reader":
    st.markdown("### 🔗 URL Reader")
    url_input = st.text_input("Paste a website link here:")
    url_query = st.text_input("What do you want to know about this page?")
    if st.button("Read URL", type="primary") and url_input:
        with st.spinner("Reading webpage..."):
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                page = requests.get(url_input, headers=headers, timeout=10)
                soup = BeautifulSoup(page.content, 'html.parser')
                text = soup.get_text(separator=' ', strip=True)[:5000]
                prompt = f"Based on the following website content, answer this: {url_query if url_query else 'Summarize this page'}\n\nContent:\n{text}"
                res = groq_client.chat.completions.create(model="openai/gpt-oss-120b", messages=[{"role": "user", "content": prompt}])
                st.markdown(res.choices[0].message.content)
            except Exception as e: st.error(f"Failed to read URL: {e}")

else:
    # চ্যাট ইন্টারফেস (সব টেক্সট ও কাস্টম মোডের জন্য)
    for m in current_messages:
        avatar_ai = "logo.png" if "logo.png" else "✨"
        avatar = avatar_ai if m["role"] == "assistant" else "👤"
        with st.chat_message(m["role"], avatar=avatar):
            st.markdown(m["content"])

    with st.expander("🎤 Record Voice / Upload Image"):
        audio_value = st.audio_input("Speak now")
        uploaded_image = st.file_uploader("Upload Image", type=["png", "jpg", "jpeg"])

    if prompt := st.chat_input("Ask ASIKERA anything..."):
        user_text = prompt
        if audio_value:
            with st.spinner("Transcribing..."):
                with open("temp.wav", "wb") as f: f.write(audio_value.getbuffer())
                with open("temp.wav", "rb") as f:
                    user_text = groq_client.audio.transcriptions.create(file=("temp.wav", f.read()), model="whisper-large-v3").text
        
        current_messages.append({"role":"user","content":user_text})
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_text)
            
        with st.chat_message("assistant", avatar="logo.png" if "logo.png" else "✨"):
            with st.spinner("Thinking..."):
                if uploaded_image:
                    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                    response = gemini_model.generate_content([user_text, {"mime_type": uploaded_image.type, "data": uploaded_image.getvalue()}])
                    reply = response.text
                    st.markdown(reply)
                else:
                    system_msg = {"role": "system", "content": persona_prompt}
                    stream = groq_client.chat.completions.create(
                        model="openai/gpt-oss-120b", 
                        messages=[system_msg] + current_messages[-10:], 
                        temperature=0.7, max_tokens=1500, stream=True
                    )
                    reply = st.write_stream(chunk.choices[0].delta.content for chunk in stream if chunk.choices[0].delta.content)
                
            current_messages.append({"role":"assistant","content":reply})
            save_chat(st.session_state.user_email, st.session_state.current_session, current_messages)
            
            audio_data = generate_audio_edge(reply, voice_gender)
            if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)
