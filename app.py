import streamlit as st
from tavily import TavilyClient
import google.generativeai as genai
import sqlite3
from streamlit_drawable_canvas import st_canvas
from PIL import Image
from pypdf import PdfReader
from datetime import datetime

# --- 1. DATABASE INIT (Just for history now) ---
conn = sqlite3.connect('nexus_studio.db', check_same_thread=False)
db = conn.cursor()
db.execute('CREATE TABLE IF NOT EXISTS history (username TEXT, query TEXT, timestamp TEXT)')
conn.commit()

# --- 2. UI/UX STYLING & WEBSITE NAME ---
st.set_page_config(page_title="Ajay's AI Portfolio", layout="wide") 
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;800&display=swap');
    
    .stApp { 
        background-color: #1e1e2e; 
        color: #cdd6f4; 
        font-family: 'Nunito', sans-serif; 
    }
    
    /* 👇 ADD THESE 3 LINES TO HIDE STREAMLIT BRANDING 👇 */
    [data-testid="stHeader"] { visibility: hidden; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }
    /* 👆 ------------------------------------------- 👆 */

    h1, h2, h3 { color: #89b4fa !important; font-weight: 800; }
    
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

# --- 3. THE FRIENDLY MENTOR WORKSPACE ---
# --- API CONFIG ---
tavily = TavilyClient(api_key=st.secrets["TAVILY_KEY"])
genai.configure(api_key=st.secrets["GEMINI_KEY"]) 
model = genai.GenerativeModel('gemini-2.5-flash')

default_user = "Guest" # All visitors will share this history profile

with st.sidebar:
    st.title("Welcome! 🌟")
    st.divider()
    st.subheader("📚 Recent Topics")
    db.execute('SELECT query FROM history WHERE username = ? ORDER BY timestamp DESC LIMIT 5', (default_user,))
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
    db.execute('INSERT INTO history VALUES (?, ?, ?)', (default_user, query, datetime.now()))
    conn.commit()
    
    with chat_container:
        with st.chat_message("user"): st.write(query)
        with st.chat_message("assistant"):
            with st.spinner("Thinking of the best way to help... 💭"):
                # 1. Search the web
                web_data = tavily.search(query)
                web_txt = "\n".join([f"{r['title']}: {r['content']}" for r in web_data['results']])
                
                # 2. Build the message
                payload = [f"Hi Nexus! My name is {default_user}. Here is my question: {query}\n\nHere is some web info to help you answer: {web_txt}"]
                
                if up_pdf: 
                    pdf_reader = PdfReader(up_pdf)
                    payload.append(f"Here is a document I uploaded: {''.join([p.extract_text() for p in pdf_reader.pages])[:3000]}")
                if up_img: payload.append(Image.open(up_img))
                if canvas_result.image_data is not None:
                    payload.append(Image.fromarray(canvas_result.image_data.astype('uint8'), 'RGBA'))

                # 3. Prompt
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
                
                try:
                    full_text = response.text
                except ValueError:
                    full_text = "Whoops! 🛑 Google's safety filters blocked my response, or I got a little confused. Could you try asking that in a slightly different way?\n--- HELPFUL TIPS ---\nMake sure your prompt or uploaded file doesn't trigger any safety guidelines!\n--- NEXT STEPS ---\nTry asking another coding question!"

                # 4. Display
                if "--- HELPFUL TIPS ---" in full_text and "--- NEXT STEPS ---" in full_text:
                    parts = full_text.split("--- HELPFUL TIPS ---")
                    answer_part = parts[0]
                    tips_steps = parts[1].split("--- NEXT STEPS ---")
                    tips_part = tips_steps[0]
                    steps_part = tips_steps[1]
                    
                    st.write(answer_part.strip())
                    st.success(f"**💡 Friendly Tips:**\n\n{tips_part.strip()}")
                    st.info(f"**🚀 Next Steps:**\n\n{steps_part.strip()}")
                else: 
                    st.write(full_text)
