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
st.set_page_config(page_title="ASIKERA AI", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")

# ================= ২. আল্ট্রা-প্রিমিয়াম ডার্ক থিম CSS =================
custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

/* গ্লোবাল সেটিংস */
.stApp { background: #1E1E1E; font-family: 'Inter', sans-serif; color: #E0E0E0; }
[data-testid="stSidebar"] { background: #191919; border-right: 1px solid #333; width: 260px !important; }
[data-testid="stHeader"] { display: none !important; }
#MainMenu {visibility: hidden;} footer {visibility: hidden;} 

/* মেইন কন্টেইনার */
.block-container { padding-top: 1rem !important; padding-bottom: 6rem !important; max-width: 850px !important; margin: 0 auto !important; }

/* বাটন ডিজাইন */
.stButton>button[kind="primary"] { background: #4D6BFE; border-radius: 8px; height: 35px; font-weight: 500; border: 0; color: white; font-size: 13px; }
.stButton>button[kind="secondary"] { background: #252525; border: 1px solid #333; border-radius: 8px; color: #AAA; padding: 5px; font-size: 12px; }
.stButton>button[kind="secondary"]:hover { background: #333; color: white; }

/* ================= চ্যাট ডিজাইন ও টেক্সট ফিক্স ================= */
div[data-testid="stChatMessage"] { background-color: transparent; padding: 10px 0; border: none; }

/* ১. হেডলাইন ও বোল্ড টেক্সট (সাদা) */
div[data-testid="stChatMessage"] h1, div[data-testid="stChatMessage"] h2, div[data-testid="stChatMessage"] h3, 
div[data-testid="stChatMessage"] h4, div[data-testid="stChatMessage"] h5, div[data-testid="stChatMessage"] h6,
div[data-testid="stChatMessage"] strong { color: #FFFFFF !important; margin-top: 15px !important; margin-bottom: 10px !important; }

/* ২. সাধারণ প্যারাগ্রাফ ও লিস্ট */
div[data-testid="stChatMessage"] p, div[data-testid="stChatMessage"] li { color: #E0E0E0 !important; font-size: 14px !important; line-height: 1.6; }

/* ৩. টেবিল ফিক্স */
div[data-testid="stChatMessage"] table { display: block !important; overflow-x: auto !important; border-collapse: collapse !important; margin: 15px 0 !important; width: 100% !important; }
div[data-testid="stChatMessage"] table th, div[data-testid="stChatMessage"] table td { color: #FFFFFF !important; border: 1px solid #555 !important; padding: 10px !important; font-size: 13px !important; background-color: #252525 !important; }
div[data-testid="stChatMessage"] table th * { color: #FFFFFF !important; }

/* ৪. কোড ব্লক ফিক্স */
div[data-testid="stChatMessage"] pre { background-color: #111111 !important; border: 1px solid #333 !important; border-radius: 8px !important; padding: 12px !important; }
div[data-testid="stChatMessage"] code { color: #A8FF60 !important; background-color: transparent !important; font-family: 'Courier New', monospace !important; font-size: 13px !important; }
div[data-testid="stChatMessage"] p code { background-color: #333333 !important; color: #FFD700 !important; padding: 2px 6px !important; border-radius: 4px !important; }

/* ৫. ইউজার ও এআই মেসেজ বাবল */
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) { flex-direction: row-reverse; text-align: right; margin-left: auto; margin-right: 0; width: fit-content; max-width: 90%; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarUser"]) .stMarkdown { background: #2A2A2A; padding: 10px 15px; border-radius: 15px 15px 2px 15px; display: inline-block; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) { margin-right: auto; margin-left: 0; width: 100%; }
div[data-testid="stChatMessage"]:has(div[data-testid="stChatMessageAvatarAssistant"]) .stMarkdown { background: transparent; padding: 10px 0; display: inline-block; }

/* ================= ইনপুট বক্স ফিক্স ================= */
div[data-testid="stTextInput"] input { background-color: #252525 !important; color: #FFFFFF !important; border: 1px solid #444 !important; border-radius: 8px !important; }
div[data-testid="stTextInput"] input::placeholder { color: #888 !important; }
div[data-testid="stChatInput"] { background-color: #252525 !important; border-radius: 8px !important; border: 1px solid #444 !important; }
div[data-testid="stChatInput"] > div { background-color: #252525 !important; }
div[data-testid="stChatInput"] textarea { color: #FFFFFF !important; background-color: #252525 !important; font-size: 14px !important; }
div[data-testid="stChatInput"] button { background: #4D6BFE !important; border-radius: 5px !important; }
div[data-testid="stChatInput"] button svg { fill: white !important; }
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div { background-color: #252525 !important; color: #FFF !important; border: 1px solid #444 !important; }

/* সাইডবার টেক্সট */
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
st.markdown(custom_css, unsafe_allow_html=True)

# ================= ৩. API Clients & Supabase =================
groq_client = Groq(api_key=st.secrets["GROQ_API_KEY"])
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# ================= ৪. ডেটাবেস ফাংশন =================
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

# ================= ৫. অডিও জেনারেটর =================
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

# ================= ৬. অটো-লগইন =================
if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "user_email" not in st.session_state: st.session_state.user_email = ""
if not st.session_state.logged_in and "email" in st.query_params:
    st.session_state.logged_in = True
    st.session_state.user_email = st.query_params["email"]
    st.rerun()

# ================= ৭. লগইন পেজ =================
if not st.session_state.logged_in:
    st.markdown("<h2 style='text-align: center; margin-top: 80px; font-weight:600; color:white;'>⚡ ASIKERA</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color:#777; font-size:12px; letter-spacing:1px; margin-bottom:40px;'>ASIKUL'S KNOWLEDGE ERA</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,1.5,1])
    with col2:
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        with tab1:
            l_email = st.text_input("Email", key="l_email")
            l_pass = st.text_input("Password", type="password", key="l_pass")
            if st.button("Login", use_container_width=True, type="primary"):
                if login_user(l_email, l_pass):
                    st.session_state.logged_in = True
                    st.session_state.user_email = l_email
                    st.query_params["email"] = l_email
                    st.rerun()
                else: st.error("Invalid credentials")
        with tab2:
            s_email = st.text_input("Email", key="s_email")
            s_pass = st.text_input("Password", type="password", key="s_pass")
            if st.button("Sign Up", use_container_width=True, type="secondary"):
                if create_user(s_email, s_pass): st.success("Account created! Please login.")
                else: st.error("Email already exists.")
    st.stop()

# ================= ৮. সাইডবার (১০টি ক্যাটাগরি) =================
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = load_chats(st.session_state.user_email)
if "current_session" not in st.session_state:
    st.session_state.current_session = list(st.session_state.chat_sessions.keys())[0]

# ১০টি ক্যাটাগরি
CATEGORIES = [
    "💬 General Chat", "👨‍💻 Coding Assistant", "📚 Learning & Study", "✍️ Writing & Editing", 
    "🔍 Deep Research (Agentic)", "🎨 Image Generation", "📄 File Analysis", "🌐 Web Search",
    "📊 Data Analysis", "🎓 English Board (Sir English)"
]

with st.sidebar:
    st.markdown("""
    <div class="sidebar-header">
        <div class="sidebar-title">⚡ ASIKERA</div>
        <div class="sidebar-subtitle">KNOWLEDGE ERA</div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("＋ New Chat", use_container_width=True, type="primary"):
        new_id = f"Chat {len(st.session_state.chat_sessions) + 1}"
        st.session_state.chat_sessions[new_id] = []
        st.session_state.current_session = new_id
        st.rerun()
        
    search_query = st.text_input("Search", placeholder="Search chats...", label_visibility="collapsed")
    
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="label-text">✨ 10 AI Modes</div>', unsafe_allow_html=True)
    
    # ক্যাটাগরি সিলেকশন
    selected_category = st.selectbox("Select Mode", CATEGORIES, label_visibility="collapsed")
    
    # পার্সোনালিটি প্রম্পট
    if selected_category == "👨‍💻 Coding Assistant":
        persona_prompt = "You are an expert programmer. Write clean, optimized code. Explain bugs clearly."
    elif selected_category == "📚 Learning & Study":
        persona_prompt = "You are a patient and brilliant tutor. Explain concepts simply, step-by-step."
    elif selected_category == "✍️ Writing & Editing":
        persona_prompt = "You are a professional editor and writer. Fix grammar, improve tone, and write compelling content."
    elif selected_category == "🎓 English Board (Sir English)":
        persona_prompt = "You are 'Sir English'. A strict English teacher. Correct grammar, explain rules in Bengali, and give examples."
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
    st.markdown(f"""
    <div class="user-card">
        <div class="user-avatar">👤</div>
        <div class="user-email">{st.session_state.user_email}</div>
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("Logout", use_container_width=True, type="secondary"):
        st.session_state.logged_in = False
        st.query_params.clear()
        st.rerun()

# ================= ৯. মেইন অ্যাপ লজিক (টুলস) =================
current_messages = st.session_state.chat_sessions[st.session_state.current_session]

# --- ১. ইমেজ জেনারেটর ---
if selected_category == "🎨 Image Generation":
    st.markdown("### 🎨 AI Image Generator")
    img_prompt = st.text_input("Describe your image:")
    if st.button("Generate Image", type="primary"):
        if img_prompt:
            with st.spinner("Painting..."):
                safe_prompt = urllib.parse.quote(img_prompt)
                image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1024&height=1024&nologo=true"
                st.image(image_url, use_container_width=True)

# --- ২. ফাইল এনালাইজার ---
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

# --- ৩. ডেটা অ্যানালাইসিস ---
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

# --- ৪. ওয়েব সার্চ ---
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

# --- ৫. Deep Research (Agentic) ---
elif selected_category == "🔍 Deep Research (Agentic)":
    st.markdown("### 🔍 Agentic Deep Research")
    st.write("Ask a complex question. The AI will search the web, read multiple sources, and generate a comprehensive report.")
    
    research_prompt = st.text_input("What should I research?")
    if st.button("Start Research", type="primary") and research_prompt:
        with st.spinner("Step 1: Generating search queries..."):
            try:
                # Step 1: Generate queries
                query_gen = groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b", 
                    messages=[{"role": "system", "content": "Generate 3 specific search engine queries based on this topic. Output ONLY the queries separated by newlines."}, {"role": "user", "content": research_prompt}]
                )
                queries = query_gen.choices[0].message.content.strip().split('\n')
                
                # Step 2: Search Web
                with st.spinner("Step 2: Browsing live internet..."):
                    all_results = []
                    for q in queries:
                        if q.strip():
                            res = list(DDGS().text(q, max_results=3))
                            all_results.extend(res)
                    context = "\n".join([f"Title: {r['title']}\nSnippet: {r['body']}" for r in all_results])
                
                # Step 3: Synthesize Report
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

# --- ৬. সাধারণ চ্যাট (বাকি সব ক্যাটাগরি) ---
else:
    # চ্যাট হিস্ট্রি রেন্ডার
    for m in current_messages:
        avatar = "✨" if m["role"] == "assistant" else "👤"
        with st.chat_message(m["role"], avatar=avatar):
            st.markdown(m["content"])

    # ইনপুট
    if prompt := st.chat_input("Ask ASIKERA anything..."):
        current_messages.append({"role":"user","content":prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)
            
        with st.chat_message("assistant", avatar="✨"):
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
