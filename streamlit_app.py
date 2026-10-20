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

# ================= ১. পেজ কনফিগারেশন =================
st.set_page_config(page_title="ASIKERA AI", page_icon="logo.png", layout="wide", initial_sidebar_state="expanded")

# ================= ২. আল্ট্রা-প্রিমিয়াম ডার্ক থিম CSS (মেইন অ্যাপ) =================
custom_css_chat = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
.stApp { background: #1E1E1E; font-family: 'Inter', sans-serif; color: #E0E0E0; }
[data-testid="stSidebar"] { background: #191919; border-right: 1px solid #333; width: 260px !important; }
[data-testid="stHeader"] { display: none !important; }
#MainMenu {visibility: hidden;} footer {visibility: hidden;} 

.block-container { padding-top: 1rem !important; padding-bottom: 6rem !important; max-width: 850px !important; margin: 0 auto !important; }
.stButton>button[kind="primary"] { background: #4D6BFE; border-radius: 8px; height: 35px; font-weight: 500; border: 0; color: white; font-size: 13px; }
.stButton>button[kind="secondary"] { background: #252525; border: 1px solid #333; border-radius: 8px; color: #AAA; padding: 5px; font-size: 12px; }
.stButton>button[kind="secondary"]:hover { background: #333; color: white; }

div[data-testid="stChatMessage"] { background-color: transparent; padding: 10px 0; border: none; }
div[data-testid="stChatMessage"] h1, div[data-testid="stChatMessage"] h2, div[data-testid="stChatMessage"] h3, 
div[data-testid="stChatMessage"] h4, div[data-testid="stChatMessage"] h5, div[data-testid="stChatMessage"] h6,
div[data-testid="stChatMessage"] strong { color: #FFFFFF !important; margin-top: 15px !important; margin-bottom: 10px !important; }
div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li { color: #E0E0E0 !important; font-size: 14px !important; line-height: 1.6; }
div[data-testid="stChatMessage"] table { display: block !important; overflow-x: auto !important; border-collapse: collapse !important; margin: 15px 0 !important; width: 100% !important; }
div[data-testid="stChatMessage"] table th, div[data-testid="stChatMessage"] table td { color: #FFFFFF !important; border: 1px solid #555 !important; padding: 10px !important; font-size: 13px !important; background-color: #252525 !important; }
div[data-testid="stChatMessage"] pre { background-color: #111111 !important; border: 1px solid #333 !important; border-radius: 8px !important; padding: 12px !important; }
div[data-testid="stChatMessage"] code { color: #A8FF60 !important; background-color: transparent !important; font-family: 'Courier New', monospace !important; font-size: 13px !important; }
div[data-testid="stChatMessage"] p code { background-color: #333333 !important; color: #FFD700 !important; padding: 2px 6px !important; border-radius: 4px !important; }

div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse; text-align: right; margin-left: auto; margin-right: 0; width: fit-content; max-width: 90%; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) .stMarkdown { background: #2A2A2A; padding: 10px 15px; border-radius: 15px 15px 2px 15px; display: inline-block; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) { margin-right: auto; margin-left: 0; width: 100%; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) .stMarkdown { background: transparent; padding: 10px 0; display: inline-block; }

div[data-testid="stTextInput"] input { background-color: #252525 !important; color: #FFFFFF !important; border: 1px solid #444 !important; border-radius: 8px !important; }
div[data-testid="stTextInput"] input::placeholder { color: #888 !important; }
div[data-testid="stChatInput"] { background-color: #252525 !important; border-radius: 8px !important; border: 1px solid #444 !important; }
div[data-testid="stChatInput"] > div { background-color: #252525 !important; }
div[data-testid="stChatInput"] textarea { color: #FFFFFF !important; background-color: #252525 !important; font-size: 14px !important; }
div[data-testid="stChatInput"] button { background: #4D6BFE !important; border-radius: 5px !important; }
div[data-testid="stChatInput"] button svg { fill: white !important; }
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { background-color: #252525 !important; color: #FFF !important; border: 1px solid #444 !important; }

.sidebar-header { padding: 15px 10px 10px 10px; }
.sidebar-title { font-size: 18px; font-weight: 600; color: #FFF; margin: 0; letter-spacing: 0.5px; }
.sidebar-subtitle { font-size: 9px; color: #777; letter-spacing: 1px; margin-top: 5px; font-weight: 500; }
.divider { border-top: 1px solid #333; margin: 15px 0; }
.label-text { font-size: 11px; color: #777; margin-bottom: 8px; font-weight: 500; }
.user-card { display: flex; align-items: center; background: #252525; padding: 8px; border-radius: 8px; border: 1px solid #333; margin-bottom: 10px; }
.user-avatar { background: #4D6BFE; color: white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; font-size: 12px; margin-right: 10px; }
.user-email { font-size: 11px; color: #E0E0E0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
"""

# ================= ৩. আল্ট্রা-প্রিমিয়াম লগইন CSS (আপনার ১ নম্বর ছবির হুবহু ডিজাইন) =================
custom_css_login = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

/* ১. ব্যাকগ্রাউন্ড গ্লো */
.stApp { 
    background: radial-gradient(circle at 10% 20%, rgba(139, 92, 246, 0.25), transparent 40%), 
                radial-gradient(circle at 90% 80%, rgba(59, 130, 246, 0.25), transparent 40%), 
                #09090B !important; 
    font-family: 'Inter', sans-serif; 
}

/* ২. গ্লাসমরফিজম কার্ড */
div[data-testid="stForm"] {
    background: rgba(20, 20, 25, 0.6) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
    border: 1px solid rgba(255, 255, 255, 0.08) !important;
    border-radius: 16px !important;
    padding: 35px !important;
    box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5) !important;
}

/* ৩. ইনপুট বক্স ফিক্স */
div[data-testid="stTextInput"] input {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid rgba(255, 255, 255, 0.1) !important;
    border-radius: 8px !important;
    color: #FFFFFF !important;
    padding-left: 10px !important;
    transition: border-color 0.3s;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #8B5CF6 !important;
    box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.2) !important;
}

/* ৪. লগইন বাটন (জোর করে কালার পরিবর্তন করা হলো) */
div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #8B5CF6, #3B82F6) !important;
    border: none !important;
    border-radius: 8px !important;
    color: white !important;
    font-weight: 600 !important;
    padding: 12px 0 !important;
    box-shadow: 0 4px 20px rgba(139, 92, 246, 0.4) !important;
    transition: all 0.3s ease !important;
}
div[data-testid="stFormSubmitButton"] > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 25px rgba(139, 92, 246, 0.6) !important;
}

/* গুগল বাটন */
.stButton > button {
    background: transparent !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    border-radius: 8px !important;
    color: white !important;
}
.stButton > button:hover { border-color: rgba(255, 255, 255, 0.5) !important; }

/* ট্যাব ডিজাইন (লগইন / সাইন আপ) */
button[data-baseweb="tab"] {
    color: #888 !important; font-weight: 500 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    color: #FFF !important; border-bottom-color: #8B5CF6 !important;
}

h1, h2, h3, p, label { color: #FFFFFF !important; }
#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;} 
</style>
"""

# ================= ৪. API Clients & Supabase =================
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# ================= ৫. ডেটাবেস ফাংশন =================
def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def create_user(email, password):
    try: supabase.table("users").insert({"email": email, "password": make_hashes(password)}).execute(); return True
    except: return False
def login_user(email, password):
    response = supabase.table("users").select("password").eq("email", email).execute()
    return bool(response.data and response.data[0]["password"] == make_hashes(password))
def save_chat(email, session_name, messages):
    try:
        supabase.table("chats").delete().eq("user_email", email).eq("session_name", session_name).execute()
        supabase.table("chats").insert({"user_email": email, "session_name": session_name, "messages": messages}).execute()
    except: pass
def load_chats(email):
    response = supabase.table("chats").select("session_name, messages").eq("user_email", email).execute()
    sessions = {row["session_name"]: row["messages"] for row in response.data}
    return sessions if sessions else {"New Chat": []}

# ================= ৬. অডিও জেনারেটর =================
def generate_audio_edge(text, speed="+0%"):
    try:
        lang = detect(text)
        voice = 'bn-BD-NabanitaNeural' if lang == 'bn' else 'en-US-AriaNeural'
    except: voice = 'en-US-AriaNeural'
    async def _generate():
        communicate = edge_tts.Communicate(text, voice, rate=speed)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio": audio_data += chunk["data"]
        return audio_data
    try:
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)
        return io.BytesIO(loop.run_until_complete(_generate()))
    except: return None

# ================= ৭. অটো-লগইন =================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if not st.session_state.logged_in and "email" in st.query_params:
    st.session_state.logged_in = True
    st.session_state.user_email = st.query_params["email"]
    st.rerun()

# ================= ৮. লগইন ও সাইনআপ পেজ =================
if not st.session_state.logged_in:
    st.markdown(custom_css_login, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div style='text-align: center; margin-bottom: 25px;'>
            <div style='display: flex; align-items: center; justify-content: center; gap: 10px;'>
                <span style='font-size: 40px;'>⚡</span>
                <h1 style='margin: 0; font-size: 32px; font-weight: 700; letter-spacing: 1px;'>ASIKERA</h1>
            </div>
            <p style='color: #888; font-size: 11px; letter-spacing: 2px; margin-top: 5px; text-transform: uppercase;'>Asikul's Knowledge Era</p>
        </div>
        """, unsafe_allow_html=True)
        
        # ট্যাব ফিরিয়ে আনা হলো (Login / Sign Up)
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        
        with tab1:
            with st.form("login_form"):
                st.markdown("<h2 style='margin-top:0; font-size: 24px;'>Welcome back</h2>", unsafe_allow_html=True)
                st.markdown("<p style='font-size: 13px; color: #AAA; margin-bottom: 20px;'>Sign in to your workspace to continue</p>", unsafe_allow_html=True)
                
                l_email = st.text_input("Email", placeholder="✉️  you@company.com")
                l_pass = st.text_input("Password", type="password", placeholder="🔒  ••••••••")
                st.checkbox("Remember me")
                
                submit_login = st.form_submit_button("Login", use_container_width=True)
                if submit_login:
                    if login_user(l_email, l_pass):
                        st.session_state.logged_in = True
                        st.session_state.user_email = l_email
                        st.query_params["email"] = l_email
                        st.rerun()
                    else: 
                        st.error("Invalid email or password. (If new, please Sign Up)")
        
        with tab2:
            with st.form("signup_form"):
                st.markdown("<h2 style='margin-top:0; font-size: 24px;'>Create Account</h2>", unsafe_allow_html=True)
                st.markdown("<p style='font-size: 13px; color: #AAA; margin-bottom: 20px;'>Join ASIKERA to start creating</p>", unsafe_allow_html=True)
                
                s_email = st.text_input("Email", placeholder="✉️  you@company.com", key="s_email")
                s_pass = st.text_input("Password", type="password", placeholder="🔒  •••••••• (Min 6 chars)", key="s_pass")
                
                submit_signup = st.form_submit_button("Sign Up", use_container_width=True)
                if submit_signup:
                    if len(s_pass) < 6:
                        st.warning("Password must be at least 6 characters long.")
                    else:
                        if create_user(s_email, s_pass):
                            st.success("Account created! Please switch to Login tab.")
                        else:
                            st.error("This email is already registered. Please login.")
                            
        # গুগল বাটন ও ট্রাস্ট ব্যাজ
        st.markdown("<p style='text-align: center; color: #666; font-size: 12px; margin: 15px 0;'>Or continue with</p>", unsafe_allow_html=True)
        st.button("G  Continue with Google", use_container_width=True)
        
        st.markdown("""
        <div style='display: flex; justify-content: space-between; align-items: center; margin-top: 40px; font-size: 11px; color: #888;'>
            <span>🛡️ SOC 2 Compliant</span>
            <span>🔒 Enterprise-grade Security</span>
            <span>✅ 99.9% Uptime SLA</span>
        </div>
        <div style='text-align: center; margin-top: 20px; font-size: 11px; color: #666;'>
            © 2024 ASIKERA AI • Privacy • Terms • Contact
        </div>
        """, unsafe_allow_html=True)
        
    st.stop()

# ================= ৯. মেইন অ্যাপ (লগইন করার পর) =================
st.markdown(custom_css_chat, unsafe_allow_html=True)

if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_chats(st.session_state.user_email)
if "current_session" not in st.session_state:
    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]

CATEGORIES = [
    "💬 General Chat", "👨‍💻 Coding Assistant", "📚 Learning & Study", "✍️ Writing & Editing", 
    "🔍 Deep Research (Agentic)", "🎨 Image Generation", "📄 File Analysis", "🌐 Web Search",
    "📊 Data Analysis", "🎓 English Board (Sir English)"
]

with st.sidebar:
    col_logo, col_text = st.columns([1, 3])
    with col_logo:
        try: st.image("logo.png", use_container_width=True)
        except: st.markdown("⚡")
    with col_text:
        st.markdown("""<div style='padding-top: 5px;'><div class="sidebar-title">ASIKERA</div><div class="sidebar-subtitle">KNOWLEDGE ERA</div></div>""", unsafe_allow_html=True)
        
    st.write("") 
    
    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        new_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
        st.session_state.chat_sessions[new_id] = []
        st.session_state.current_session = new_id
        st.rerun()
        
    search_query = st.text_input("Search", placeholder="Search chats...", label_visibility="collapsed")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="label-text">✨ 10 AI Modes</div>', unsafe_allow_html=True)
    
    selected_category = st.selectbox("Select Mode", CATEGORIES, label_visibility="collapsed")
    
    if selected_category == "👨‍💻 Coding Assistant":
        persona_prompt = "You are an expert programmer. Write clean, optimized code. Explain bugs clearly."
    elif selected_category == "📚 Learning & Study":
        persona_prompt = "You are a patient and brilliant tutor. Explain concepts simply, step-by-step."
    elif selected_category == "✍️ Writing & Editing":
        persona_prompt = "You are a professional editor and writer. Fix grammar, improve tone, and write compelling content."
    elif selected_category == "🎓 English Board (Sir English)":
        persona_prompt = """
        You are 'Sir English', an elite, highly professional, and strict IELTS Examiner and English Professor (GPT-4 level). 
        Your goal is to help the user master English with absolute precision.
        1. If the user makes ANY grammatical, vocabulary, or structural mistake, point it out immediately in a strict but professional tone.
        2. Provide a 'Correction' section. 3. Provide a 'Detailed Explanation' section in Bengali. 4. Provide an 'Advanced Vocabulary/Phrasing' section.
        5. Format beautifully using Markdown. 6. Grade paragraphs using IELTS band descriptors.
        """
    elif selected_category == "🔍 Deep Research (Agentic)":
        persona_prompt = "You are a deep research agent. You will analyze the user's prompt, generate search queries, and synthesize a detailed report."
    else:
        persona_prompt = "You are a smart and helpful AI assistant."

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

# ================= ১০. মেইন অ্যাপ লজিক =================
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

if selected_category == "🎨 Image Generation":
    st.markdown("### 🎨 AI Image Generator")
    img_prompt = st.text_input("Describe your image:")
    if st.button("Generate Image", type="primary"):
        if img_prompt:
            with st.spinner("Painting..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, use_container_width=True)

elif selected_category == "📄 File Analysis":
    st.markdown("### 📄 File Analyzer")
    uploaded_file = st.file_uploader("Upload PDF or Image", type=["pdf", "png", "jpg", "jpeg"])
    file_query = st.text_input("What do you want to know about this file?")
    if st.button("Analyze File", type="primary") and uploaded_file and file_query:
        with st.spinner("Analyzing..."):
            try:
                gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                response = gemini_model.generate_content([file_query, {"mime_type": uploaded_file.type, "data": uploaded_file.getvalue()}])
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Error: {str(e)}")

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
                except Exception as e:
                    st.error(f"Error: {str(e)}")

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
            except Exception as e:
                st.error(f"Error: {str(e)}")

elif selected_category == "🔍 Deep Research (Agentic)":
    st.markdown("### 🔍 Agentic Deep Research")
    st.write("Ask a complex question. The AI will search the web, read multiple sources, and generate a comprehensive report.")
    
    research_prompt = st.text_input("What should I research?")
    if st.button("Start Research", type="primary") and research_prompt:
        with st.spinner("Step 1: Generating search queries..."):
            try:
                query_gen = groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b", 
                    messages=[{"role": "system", "content": "Generate 3 specific search engine queries based on this topic. Output ONLY the queries separated by newlines."}, {"role": "user", "content": research_prompt}]
                )
                queries = query_gen.choices[0].message.content.strip().split('\n')
                
                with st.spinner("Step 2: Browsing live internet..."):
                    all_results = []
                    for q in queries:
                        if q.strip():
                            res = list(DDGS().text(q, max_results=3))
                            all_results.extend(res)
                    context = "\n".join([f"Title: {r['title']}\nSnippet: {r['body']}" for r in all_results])
                
                with st.spinner("Step 3: Synthesizing comprehensive report..."):
                    final_report = groq_client.chat.completions.create(
                        model="openai/gpt-oss-120b",
                        messages=[
                            {"role": "system", "content": "You are a Deep Research Agent. Synthesize the following web search results into a highly detailed, structured report with headings and bullet points. Cite the sources."},
                            {"role": "user", "content": f"Topic: {research_prompt}\n\nSearch Results:\n{context}"}
                        ],
                        temperature=0.5, max_tokens=2000
                    )
                    st.markdown(final_report.choices[0].message.content)
            except Exception as e:
                st.error(f"Research Error: {str(e)}")

else:
    for m in current_messages:
        avatar_ai = "logo.png" if "logo.png" else "✨"
        avatar = avatar_ai if m["role"] == "assistant" else "👤"
        with st.chat_message(m["role"], avatar=avatar):
            st.markdown(m["content"])

    if prompt := st.chat_input("Ask ASIKERA anything..."):
        current_messages.append({"role":"user","content":prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
            
        with st.chat_message("assistant", avatar="logo.png" if "logo.png" else "✨"):
            with st.spinner("Thinking..."):
                system_msg = {"role": "system", "content": persona_prompt}
                stream = groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b", 
                    messages=[system_msg] + current_messages[-10:], 
                    temperature=0.7, max_tokens=1500, stream=True
                )
                reply = st.write_stream(chunk.choices[0].delta.content for chunk in stream if chunk.choices[0].delta.content)
                
            current_messages.append({"role":"assistant","content":reply})
            save_chat(st.session_state.user_email, st.session_state.current_session, current_messages)
            
            audio_data = generate_audio_edge(reply)
            if audio_data: st.audio(audio_data, format="audio/mp3", autoplay=True)
