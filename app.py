import streamlit as st
from tavily import TavilyClient
import google.generativeai as genai
import sqlite3
import hashlib
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from pypdf import PdfReader
from datetime import datetime

# --- 1. DATABASE & SESSION INIT ---
if 'auth' not in st.session_state:
    st.session_state.auth = False
if 'user' not in st.session_state:
    st.session_state.user = None

conn = sqlite3.connect('nexus_studio.db', check_same_thread=False)
db = conn.cursor()
db.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)')
db.execute('CREATE TABLE IF NOT EXISTS history (username TEXT, query TEXT, timestamp TEXT)')
conn.commit()

# --- 2. AUTH FUNCTIONS ---
def make_hash(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def signup_user(user, pw):
    try:
        db.execute('INSERT INTO users(username, password) VALUES (?,?)', (user, make_hash(pw)))
        conn.commit()
        return True
    except: return False

def login_user(user, pw):
    db.execute('SELECT * FROM users WHERE username = ? AND password = ?', (user, make_hash(pw)))
    return db.fetchone()

# --- 3. UI/UX STYLING (FRIENDLY THEME) ---
st.set_page_config(page_title="Nexus Mentor", layout="wide")
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;800&display=swap');
    
    .stApp { 
        background-color: #1e1e2e; /* Soft, friendly dark blue/gray */
        color: #cdd6f4; 
        font-family: 'Nunito', sans-serif; 
    }
    
    h1, h2, h3 { color: #89b4fa !important; font-weight: 800; }
    
    /* Soft Login Box */
    .auth-card { 
        padding: 40px; background: rgba(255, 255, 255, 0.03); 
        border: 2px solid #89b4fa; border-radius: 24px; 
        max-width: 450px; margin: auto;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
    }
    
    /* Friendly Sidebar */
    [data-testid="stSidebar"] { background-color: #181825 !important; border-right: none; }
    
    /* Hide File Uploader Text */
    div[data-testid="stFileUploader"] label { display: none; }
    
    /* Cute Popover Button */
    div[data-testid="stPopover"] > button { 
        border-radius: 50% !important; border: 2px solid #89b4fa !important; 
        color: #89b4fa !important; height: 48px; width: 48px; font-size: 20px;
        transition: all 0.2s ease;
    }
    div[data-testid="stPopover"] > button:hover { background-color: #89b4fa !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 4. FRIENDLY AUTHENTICATION SCREEN ---
if not st.session_state.auth:
    st.markdown("<br><br>", unsafe_allow_html=True)
    cols = st.columns([1, 1.5, 1])
    with cols[1]:
        st.markdown("<h1 style='text-align: center; font-size: 3em;'>👋 Hello there!</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #a6adc8;'>Welcome to Nexus, your personal AI coding buddy.</p>", unsafe_allow_html=True)
        
        tab1, tab2 = st.tabs(["Log In", "Sign Up"])
        
        with tab1:
            u = st.text_input("What's your username?", key="login_user")
            p = st.text_input("Password", type="password", key="login_pass")
            if st.button("Let's Go! 🚀", use_container_width=True):
                if login_user(u, p):
                    st.session_state.auth = True
                    st.session_state.user = u
                    st.rerun()
                else: st.error("Oops! Those details don't look quite right.")
        
        with tab2:
            nu = st.text_input("Choose a cool username", key="reg_user")
            np = st.text_input("Create a password", type="password", key="reg_pass")
            if st.button("Create My Account ✨", use_container_width=True):
                if signup_user(nu, np): st.success("Yay! Account created. You can now log in.")
                else: st.error("Hmm, that username is already taken. Try another one!")

# --- 5. THE FRIENDLY MENTOR WORKSPACE ---
else:
    # --- API CONFIG ---
    tavily = TavilyClient(api_key=st.secrets["TAVILY_KEY"])
    genai.configure(api_key=st.secrets["GEMINI_KEY"]) # <-- PASTE KEY HERE
    model = genai.GenerativeModel('gemini-1.5-flash')

    with st.sidebar:
        st.title(f"Hi, {st.session_state.user}! 🌟")
        if st.button("Sign Out 👋"):
            st.session_state.auth = False
            st.rerun()
        st.divider()
        st.subheader("📚 Your Recent Topics")
        db.execute('SELECT query FROM history WHERE username = ? ORDER BY timestamp DESC LIMIT 5', (st.session_state.user,))
        for s in db.fetchall():
            st.markdown(f"🔹 *{s[0]}*")

    st.title("Nexus Mentor 🌱")
    st.caption("I'm here to help you learn, code, and build awesome things!")
    
    chat_container = st.container()
    st.divider()
    
    input_col, tool_col = st.columns([0.88, 0.12])

    with tool_col:
        with st.popover("📎"):
            t1, t2 = st.tabs(["Files 📁", "Sketch 🎨"])
            with t1:
                st.caption("Upload PDFs or Images")
                up_pdf = st.file_uploader("PDF", type="pdf")
                up_img = st.file_uploader("IMG", type=["png", "jpg"])
            with t2:
                st.caption("Draw your idea here!")
                if st.button("Clear Canvas 🗑️"): st.rerun()
                canvas_result = st_canvas(
                    fill_color="rgba(137, 180, 250, 0.3)", stroke_width=4,
                    stroke_color="#89b4fa", background_color="#181825",
                    height=200, width=220, drawing_mode="freedraw", key="friendly_canvas"
                )

    with input_col:
        query = st.chat_input("Ask me anything about your project...")

    if query:
        db.execute('INSERT INTO history VALUES (?, ?, ?)', (st.session_state.user, query, datetime.now()))
        conn.commit()
        
        with chat_container:
            with st.chat_message("user"): st.write(query)
            with st.chat_message("assistant"):
                with st.spinner("Thinking of the best way to help... 💭"):
                    # 1. Search the web
                    web_data = tavily.search(query)
                    web_txt = "\n".join([f"{r['title']}: {r['content']}" for r in web_data['results']])
                    
                    # 2. Build the message for Gemini
                    payload = [f"Hi Nexus! My name is {st.session_state.user}. Here is my question: {query}\n\nHere is some web info to help you answer: {web_txt}"]
                    
                    if up_pdf: 
                        pdf_reader = PdfReader(up_pdf)
                        payload.append(f"Here is a document I uploaded: {''.join([p.extract_text() for p in pdf_reader.pages])[:3000]}")
                    if up_img: payload.append(Image.open(up_img))
                    if canvas_result.image_data is not None:
                        payload.append(Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA'))

                    # 3. THE NEW FRIENDLY PERSONALITY PROMPT
                    payload.insert(0, """You are Nexus, a super friendly, encouraging, and highly skilled coding mentor.
                    Explain things clearly, use emojis, and be very supportive.
                    
                    Format your reply EXACTLY like this:
                    [Your friendly and easy-to-understand answer]
                    --- HELPFUL TIPS ---
                    [Provide 1 or 2 gentle tips, best practices, or point out any small mistakes in a kind way]
                    --- NEXT STEPS ---
                    [Cheer them on and suggest what they can try doing next!]
                    """)
                    
                    response = model.generate_content(payload)
                    full_text = response.text

                    # 4. Display the friendly formatted answer
                    if "--- HELPFUL TIPS ---" in full_text and "--- NEXT STEPS ---" in full_text:
                        parts = full_text.split("--- HELPFUL TIPS ---")
                        answer_part = parts[0]
                        tips_steps = parts[1].split("--- NEXT STEPS ---")
                        tips_part = tips_steps[0]
                        steps_part = tips_steps[1]
                        
                        st.write(answer_part.strip())
                        
                        # Streamlit's built-in colored boxes look super friendly!
                        st.success(f"**💡 Friendly Tips:**\n\n{tips_part.strip()}")
                        st.info(f"**🚀 Next Steps:**\n\n{steps_part.strip()}")
                    else: 
                        st.write(full_text)