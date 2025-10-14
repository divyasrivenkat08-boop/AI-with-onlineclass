import io
import streamlit as st
import pandas as pd
import google.generativeai as genai
import bcrypt
import os
from datetime import datetime
from docx import Document


# ---------- CONFIG ----------
st.set_page_config(page_title="🎓 Smart AI Classroom", layout="wide", initial_sidebar_state="collapsed")

# ---------- INITIALIZE SESSION STATE ----------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "attendance_marked" not in st.session_state:
    st.session_state.attendance_marked = False

if "broadcast" not in st.session_state:
    st.session_state.broadcast = ""

if "teacher" not in st.session_state:
    st.session_state.teacher = None


# ---- HIDE Streamlit deploy/share buttons & footer ----
hide_streamlit_style = """
    <style>
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        .stDeployButton {display: none !important;}
        .stAppDeployButton {display: none !important;}
    </style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

genai.configure(api_key=os.getenv("AIzaSyCfrfvfbxBStXWTYksHDmGlrAcE0VpBC1o"))
model = genai.GenerativeModel("gemini-1.5-flash")

USER_FILE = "users.csv"
HISTORY_DIR = "student_history"
if not os.path.exists(HISTORY_DIR):
    os.makedirs(HISTORY_DIR)

# ---------- SECURITY ----------
def hash_password(pwd): return bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()
def check_password(pwd, hashed): return bcrypt.checkpw(pwd.encode(), hashed.encode())

# ---------- GEMINI REPLY ----------
def get_gemini_reply(prompt):
    """
    Gemini always returns something meaningful in a conversational tone.
    Handles short or unclear inputs by rephrasing automatically.
    """
    try:
        if not prompt.strip():
            prompt = "Please clarify your question."
        system_prompt = (
            "You are a friendly, human-like AI tutor assisting students during live online classes. "
            "Answer accurately, clearly, and conversationally like ChatGPT. "
            "If a question is short or unclear, restate it before answering. "
            "You can explain *any topic* — from science and history to general knowledge."
        )
        response = model.generate_content(f"{system_prompt}\n\nStudent asked: {prompt}\n\nAnswer:")
        text = response.text.strip() if response and hasattr(response, "text") else ""
        if not text:
            text = "I'm having trouble fetching that right now, but generally speaking..."
        return text
    except Exception as e:
        return f"⚠️ Temporary issue: {e}. Please try again."

# ---------- SAVE / LOAD ----------

def save_chat(student, q, a):
    f = os.path.join(HISTORY_DIR, f"{student}_history.csv/docx")
    new = pd.DataFrame([[datetime.now(), q, a]], columns=["Time", "Question", "Answer"])
    df = pd.read_csv(f) if os.path.exists(f) else pd.DataFrame(columns=["Time","Question","Answer"])
    pd.concat([df, new], ignore_index=True).to_csv(f, index=False)

def load_chat(student):
    f = os.path.join(HISTORY_DIR, f"{student}_history.csv")
    return pd.read_csv(f) if os.path.exists(f) else pd.DataFrame(columns=["Time","Question","Answer"])

# ---------- INIT USERS ----------
if not os.path.exists(USER_FILE):
    pd.DataFrame(columns=["username","password","role"]).to_csv(USER_FILE, index=False)
users = pd.read_csv(USER_FILE)

# ---------- GLOBAL BROADCAST ----------
if "broadcast" not in st.session_state:
    st.session_state.broadcast = ""

# ---------- APP ----------
st.markdown("<style>#MainMenu{visibility:hidden;} footer{visibility:hidden;}</style>", unsafe_allow_html=True)
st.title("🎓 Smart AI Classroom")

menu = st.sidebar.selectbox("Choose Role", ["Student", "Teacher", "Register"])

# ---------- REGISTER ----------
if menu == "Register":
    st.subheader("📝 Register New Account")
    uname = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    role = st.selectbox("Role", ["Student","Teacher"])
    if st.button("Register"):
        if uname and pwd:
            if uname in users["username"].values:
                st.error("Username already exists.")
            else:
                hashed = hash_password(pwd)
                users = pd.concat([users, pd.DataFrame([[uname, hashed, role]], columns=["username","password","role"])], ignore_index=True)
                users.to_csv(USER_FILE, index=False)
                st.success("✅ Registration complete! Please log in.")
        else:
            st.warning("Fill all fields.")

# ---------- STUDENT ----------
elif menu == "Student":
    st.subheader("🎓 Student Login")
    uname = st.text_input("Username")
    pwd = st.text_input("Password", type="password")

    if st.button("Login"):
        if uname in users["username"].values:
            stored = users.loc[users["username"]==uname,"password"].values[0]
            if check_password(pwd, stored):
                st.session_state.student = uname
                st.session_state.attendance = True
                st.success(f"✅ Welcome {uname}! Attendance marked automatically.")
            else:
                st.error("Wrong password.")
        else:
            st.error("Username not found.")

    if "student" in st.session_state:
        if st.session_state.broadcast:
            st.info(f"📢 Announcement: {st.session_state.broadcast}")
        st.subheader("💬 Ask a Question (stay on Google Meet/Zoom)")
        prompt = st.text_input("Your Question:")
        if st.button("Ask Gemini"):
            if prompt.strip():
                reply = get_gemini_reply(prompt)
                save_chat(st.session_state.student, prompt, reply)
                st.markdown(f"**🤖 Gemini:** {reply}")
            else:
                st.warning("Type a question first.")
        st.write("---")
        st.subheader("📘 Previous Questions")
        st.dataframe(load_chat(st.session_state.student))
        if st.button("⬇️ Download My Chat (.docx)"):
            doc = Document()
            doc.add_heading(f"Chat History - {st.session_state.student}", 1)
            for _, row in load_chat(st.session_state.student).iterrows():
                doc.add_paragraph(f"Q: {row['Question']}")
                doc.add_paragraph(f"A: {row['Answer']}")
                doc.add_paragraph("---")
            filename = f"{st.session_state.student}_Chat.docx"
            doc.save(filename)
            st.success(f"Saved as {filename}")

            if len(st.session_state.messages) > 0:
               docx_file = generate_docx(st.session_state.student_name, st.session_state.messages) # type: ignore
               st.download_button(
               label="⬇️ Download My Chat (Word)",
               data=docx_file,
               file_name=f"{st.session_state.student_name}_chat.docx",
               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


elif menu == "Teacher":
    st.subheader("🧑‍🏫 Teacher Login")
    uname = st.text_input("Username")
    pwd = st.text_input("Password", type="password")

    # ---------- LOGIN ----------
    if st.button("Login"):
        if uname in users["username"].values:
            stored = users.loc[users["username"] == uname, "password"].values[0]
            role = users.loc[users["username"] == uname, "role"].values[0]
            if role == "Teacher" and check_password(pwd, stored):
                st.session_state.teacher = uname
                st.success(f"✅ Welcome, {uname} (Teacher Dashboard)")
            else:
                st.error("Not a teacher or wrong password.")
        else:
            st.error("Username not found.")

    # ---------- DASHBOARD ----------
    if "teacher" in st.session_state:
        st.subheader("📢 Broadcast to All Students")
        msg = st.text_input("Enter announcement")
        if st.button("Send Broadcast"):
            st.session_state.broadcast = msg
            st.success("✅ Broadcast sent!")

        # ---------- COLLECT STUDENT DATA ----------
        st.subheader("📋 All Student Questions")

        all_data = []  # ✅ Initialize once here

        # List all registered students
        student_list = users[users["role"] == "Student"]["username"].tolist()

        for student in student_list:
            try:
                fpath = os.path.join(HISTORY_DIR, f"{student}_history.csv")
                if os.path.exists(fpath):
                    df = pd.read_csv(fpath)

                    # Safe access to columns
                    for _, r in df.iterrows():
                        time_val = r.get("Time", "")
                        question_val = r.get("Question", "")
                        answer_val = r.get("Answer", "")
                        all_data.append([student, time_val, question_val, answer_val])
                else:
                    print(f"⚠️ No history for {student}")

            except Exception as e:
                print(f"⚠️ Error reading {student}: {e}")

        # ---------- DISPLAY TABLE ----------
        if all_data:
            df_all = pd.DataFrame(all_data, columns=["Student", "Time", "Question", "Answer"])
            st.dataframe(df_all, use_container_width=True)

            # Download buttons
            def generate_docx(student_name, messages):
                doc = Document()
                doc.add_heading(f"Chat History — {student_name}", 0)
                doc.add_paragraph("Attendance: ✅ Present")

                for msg in messages:
                      doc.add_paragraph(f"{msg['role'].capitalize()}: {msg['content']}")
  
              # Save to memory (no file path needed)
                buffer = io.BytesIO()
                doc.save(buffer)
                buffer.seek(0)
                return buffer

            # Save previous class chat as backup before clearing

            if st.button("▶️ Start New Class"):
                 if os.path.exists("all_chats.csv"):
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    os.rename("all_chats.csv", f"archived_class_{timestamp}.csv")

                 if os.path.exists("teacher_class_summary.docx"):
                     timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                     os.rename("teacher_class_summary.docx", f"archived_class_{timestamp}.docx")

    # Reset everything for new class
    st.session_state.class_active = True
    st.session_state.messages = []
    st.session_state.broadcasts = []
    st.session_state.attendance_marked = False
    st.session_state.student_name = ""
    st.success("🆕 New class started! Previous class data archived safely.")