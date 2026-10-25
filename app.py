"""
LastMinute
Hacktoberfest x MOSS Hack Day Udupi, 25 October 2026

Turns your notes, PDFs and photos of textbook pages into a quiz using
Gemma 4 (open-weight) through the Gemini API, and tracks your study time.
"""

import io
import json
import os
import re
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st
from google import genai
from google.genai import types
from pypdf import PdfReader

# Import your custom styling and layout functions
from style import inject_css, hero_html, scene_html

st.set_page_config(page_title="Last Minute Study Assistant", page_icon="📚", layout="wide")

# Apply custom sage-green aesthetic and full-screen layout
inject_css()

DATA_FILE = Path("study_sessions.json")

# Gemma 4 models served by the Gemini API (only these are offered in the UI)
GEMMA_MODELS = ["gemma-4-26b-a4b-it", "gemma-4-31b-it"]
MAX_CONTEXT_CHARS = 80000  # keeps requests fast and inside limits

IMAGE_MIME = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}

ss = st.session_state


# ----------------------------------------------------------------------------
# Persistence for study sessions (survives restarts)
# ----------------------------------------------------------------------------
def load_sessions():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def save_sessions():
    DATA_FILE.write_text(json.dumps(ss.sessions, indent=2), encoding="utf-8")


# ----------------------------------------------------------------------------
# Session state defaults
# ----------------------------------------------------------------------------
ss.setdefault("sessions", load_sessions())
ss.setdefault("quiz", None)
ss.setdefault("quiz_model", "")
ss.setdefault("quiz_submitted", False)
ss.setdefault("timer_running", False)
ss.setdefault("timer_started_at", 0.0)
ss.setdefault("timer_accumulated", 0.0)
ss.setdefault("flash", None)


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
st.sidebar.title("⚙️ Settings")
api_key = st.sidebar.text_input(
    "Gemini API key",
    value=os.environ.get("GEMINI_API_KEY", ""),
    type="password",
    help="Reads GEMINI_API_KEY from your environment by default. Never commit your key.",
)
model_name = st.sidebar.selectbox(
    "Gemma 4 model",
    GEMMA_MODELS,
    help="26b-a4b is faster. 31b is larger and usually a bit more accurate.",
)
deep_thinking = st.sidebar.checkbox(
    "Deep thinking (slower)",
    value=False,
    help="Off is much faster and is fine for quizzes.",
)
st.sidebar.divider()
st.sidebar.caption("🤖 Powered by Gemma 4 (open-weight) through the Gemini API.")


# ----------------------------------------------------------------------------
# Gemma 4 integration (Gemini API)
# ----------------------------------------------------------------------------
def make_client(key: str):
    return genai.Client(
        api_key=key,
        http_options=types.HttpOptions(timeout=120000),  # 2 minutes
    )


def call_gemma(client, model: str, contents: list, deep: bool):
    """Single place where the app calls Gemma 4 through the Gemini API."""
    level = "high" if deep else "minimal"
    try:
        config = types.GenerateContentConfig(
            temperature=0.7,
            thinking_config=types.ThinkingConfig(thinking_level=level),
        )
    except Exception:
        # Older google-genai versions don't know thinking_level
        config = types.GenerateContentConfig(temperature=0.7)

    try:
        return client.models.generate_content(model=model, contents=contents, config=config)
    except Exception as e:
        if "thinking" in str(e).lower():
            plain = types.GenerateContentConfig(temperature=0.7)
            return client.models.generate_content(model=model, contents=contents, config=plain)
        raise


# ----------------------------------------------------------------------------
# Source reading
# ----------------------------------------------------------------------------
def pdf_to_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages).strip()


# ----------------------------------------------------------------------------
# Quiz helpers
# ----------------------------------------------------------------------------
def parse_quiz_json(raw_text: str):
    raw_text = (raw_text or "").strip()
    candidates = [raw_text]
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw_text, re.S)
    if fence:
        candidates.append(fence.group(1).strip())
    start, end = raw_text.find("["), raw_text.rfind("]")
    if start != -1 and end > start:
        candidates.append(raw_text[start : end + 1])
    for c in candidates:
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    raise ValueError("Could not read the quiz JSON from the model's reply.")


def clean_questions(items):
    good = []
    if not isinstance(items, list):
        return good
    for q in items:
        if not isinstance(q, dict):
            continue
        opts = q.get("options")
        if not (q.get("question") and isinstance(opts, list) and len(opts) >= 2 and q.get("answer")):
            continue
        good.append(
            {
                "question": str(q["question"]),
                "options": [str(o) for o in opts],
                "answer": str(q["answer"]),
                "explanation": str(q.get("explanation", "")),
            }
        )
    return good


def generate_quiz(client, model, text, images, num_questions, topic, deep):
    prompt = f"""
You are an expert study assistant.
Using the study materials below (text, plus any attached images of notes, diagrams or textbook pages),
write exactly {num_questions} multiple-choice quiz questions focusing on:
{topic or 'General core concepts'}.

Study Materials:
{text or '(see the attached images)'}

Output ONLY a valid JSON array. No markdown, no code fences, no commentary before or after.
Each item must have these exact keys:
- "question": string
- "options": list of exactly 4 strings
- "answer": string (must match one of the options exactly)
- "explanation": string (one or two sentences on why the answer is correct)
"""
    contents = [prompt]
    for data, mime in images:
        contents.append(types.Part.from_bytes(data=data, mime_type=mime))

    last_error = None
    for _ in range(2):  # one retry if the model's JSON is malformed
        response = call_gemma(client, model, contents, deep)
        try:
            questions = clean_questions(parse_quiz_json(response.text))
            if questions:
                return questions
            last_error = ValueError("The model did not return any valid questions.")
        except ValueError as e:
            last_error = e
    raise last_error


# ----------------------------------------------------------------------------
# Timer helpers
# ----------------------------------------------------------------------------
def elapsed_seconds() -> float:
    total = ss.timer_accumulated
    if ss.timer_running:
        total += time.time() - ss.timer_started_at
    return total


def timer_start():
    if not ss.timer_running:
        ss.timer_started_at = time.time()
        ss.timer_running = True


def timer_pause():
    if ss.timer_running:
        ss.timer_accumulated += time.time() - ss.timer_started_at
        ss.timer_running = False


def timer_reset():
    ss.timer_running = False
    ss.timer_accumulated = 0.0
    ss.timer_started_at = 0.0


def timer_stop_and_save():
    secs = elapsed_seconds()
    if secs < 1:
        ss.flash = ("warning", "Start the timer before saving a session.")
        return
    subject = (ss.get("timer_subject") or "").strip() or "General"
    chapters = int(ss.get("timer_chapters", 0))
    ss.sessions.append(
        {
            "date": date.today().isoformat(),
            "hours": round(secs / 3600, 4),
            "chapters_completed": chapters,
            "subject": subject,
        }
    )
    save_sessions()
    timer_reset()
    ss.flash = ("success", f"Saved {secs / 60:.1f} min of {subject}.")


def render_timer():
    secs = int(elapsed_seconds())
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    st.markdown(
        f"<div style='text-align:center;font-size:5rem;font-weight:700;"
        f"font-variant-numeric:tabular-nums;'>{h:02d}:{m:02d}:{s:02d}</div>",
        unsafe_allow_html=True,
    )
    if ss.timer_running:
        label = "⏱️ Running…"
    elif secs > 0:
        label = "⏸️ Paused"
    else:
        label = "Ready"
    st.markdown(f"<div style='text-align:center'>{label}</div>", unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Render Custom Aesthetic Hero & Scene
# ----------------------------------------------------------------------------
st.markdown(hero_html(), unsafe_allow_html=True)
st.markdown(scene_html(), unsafe_allow_html=True)

# ----------------------------------------------------------------------------
# Main Tabs Workflow
# ----------------------------------------------------------------------------
tab_sources, tab_quiz, tab_timer, tab_stats = st.tabs(
    ["1️⃣ Sources", "2️⃣ Quiz", "⏱️ Study Timer", "📊 Analytics"]
)

# ---------------------------- Sources ---------------------------------------
with tab_sources:
    st.subheader("Add your study material")
    st.caption("Everything you add here is used when you generate a quiz. No separate upload step.")

    notes = st.text_area("Paste notes", height=180, key="notes")
    youtube_url = st.text_input(
        "YouTube link (optional)",
        key="youtube_url",
        help="Only the link is passed to the model as text. It can't watch the video.",
    )
    uploaded_docs = st.file_uploader(
        "Upload PDFs or text files",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
        key="uploaded_docs",
    )
    uploaded_images = st.file_uploader(
        "Upload photos of notes, diagrams or textbook pages (Gemma 4 reads images)",
        type=list(IMAGE_MIME.keys()),
        accept_multiple_files=True,
        key="uploaded_images",
    )
    st.info(
        f"Ready: {len(notes or '')} characters of notes, "
        f"{len(uploaded_docs)} document(s), {len(uploaded_images)} image(s)."
    )

# ---------------------------- Quiz ------------------------------------------
with tab_quiz:
    st.subheader("Generate a quiz")
    c1, c2 = st.columns([1, 2])
    num_questions = c1.slider("Number of questions", 3, 20, 5)
    topic_focus = c2.text_input("Topic focus (optional)", placeholder="e.g. Chapter 3: Thermodynamics")

    if st.button("✨ Generate quiz", type="primary"):
        text_parts = []
        images = []
        warnings = []

        if notes and notes.strip():
            text_parts.append(f"--- Notes ---\n{notes}")
        if youtube_url and youtube_url.strip():
            text_parts.append(f"--- YouTube Reference ---\nURL: {youtube_url}")

        for f in uploaded_docs:
            data = f.getvalue()
            if not data:
                continue
            if f.name.lower().endswith(".pdf"):
                try:
                    pdf_text = pdf_to_text(data)
                except Exception as e:
                    pdf_text = ""
                    warnings.append(f"Couldn't read {f.name}: {e}")
                if pdf_text:
                    text_parts.append(f"--- PDF: {f.name} ---\n{pdf_text}")
                else:
                    warnings.append(
                        f"No text found in {f.name} (maybe a scan). Upload photos of its pages as images instead."
                    )
            else:
                text_parts.append(f"--- File: {f.name} ---\n{data.decode('utf-8', errors='ignore')}")

        for f in uploaded_images:
            ext = f.name.rsplit(".", 1)[-1].lower()
            images.append((f.getvalue(), IMAGE_MIME.get(ext, "image/jpeg")))

        context_text = "\n\n".join(text_parts)
        if len(context_text) > MAX_CONTEXT_CHARS:
            context_text = context_text[:MAX_CONTEXT_CHARS]
            warnings.append(f"Your material was long, so only the first {MAX_CONTEXT_CHARS:,} characters were used.")

        for w in warnings:
            st.warning(w)

        if not api_key:
            st.error("Add your Gemini API key in the sidebar first.")
        elif not context_text.strip() and not images:
            st.error("Add some notes, files or images in the Sources tab first.")
        else:
            try:
                client = make_client(api_key)
                with st.spinner(f"Asking {model_name}… this can take a little while."):
                    ss.quiz = generate_quiz(
                        client, model_name, context_text, images, num_questions, topic_focus, deep_thinking
                    )
                ss.quiz_model = model_name
                ss.quiz_submitted = False
                for k in [k for k in ss.keys() if k.startswith("quiz_ans_")]:
                    del ss[k]
                st.rerun()
            except Exception as e:
                st.error(f"Quiz generation failed: {e}")

    if ss.quiz:
        st.divider()
        st.caption(f"Questions written by {ss.quiz_model} through the Gemini API.")
        with st.form("quiz_form"):
            for i, q in enumerate(ss.quiz):
                st.markdown(f"**Q{i + 1}. {q['question']}**")
                st.radio(
                    "Choose one",
                    q["options"],
                    index=None,
                    key=f"quiz_ans_{i}",
                    label_visibility="collapsed",
                )
                st.write("")
            submitted = st.form_submit_button("Submit answers", type="primary")
        if submitted:
            ss.quiz_submitted = True

        if ss.quiz_submitted:
            score = 0
            for i, q in enumerate(ss.quiz):
                picked = ss.get(f"quiz_ans_{i}")
                correct = picked is not None and picked.strip() == q["answer"].strip()
                score += int(correct)
                with st.expander(f"{'✅' if correct else '❌'} Q{i + 1}: {q['question']}"):
                    st.write(f"Your answer: {picked if picked else '(not answered)'}")
                    st.write(f"Correct answer: **{q['answer']}**")
                    if q["explanation"]:
                        st.caption(q["explanation"])
            st.success(f"Score: {score} / {len(ss.quiz)}")

# ---------------------------- Timer -----------------------------------------
with tab_timer:
    st.subheader("Study timer")

    if ss.flash:
        kind, msg = ss.flash
        getattr(st, kind)(msg)
        ss.flash = None

    c1, c2 = st.columns(2)
    c1.text_input("Subject", value="General", key="timer_subject")
    c2.number_input("Chapters completed this session", min_value=0, value=0, step=1, key="timer_chapters")

    timer_fragment = st.fragment(run_every=1 if ss.timer_running else None)(render_timer)
    timer_fragment()

    b1, b2, b3, b4 = st.columns(4)
    b1.button("▶️ Start / Resume", on_click=timer_start, use_container_width=True, disabled=ss.timer_running)
    b2.button("⏸️ Pause", on_click=timer_pause, use_container_width=True, disabled=not ss.timer_running)
    b3.button("🔄 Reset", on_click=timer_reset, use_container_width=True)
    b4.button("💾 Stop & Save", on_click=timer_stop_and_save, type="primary", use_container_width=True)

    with st.expander("Or log a session manually"):
        with st.form("manual_log"):
            m1, m2, m3 = st.columns(3)
            m_subject = m1.text_input("Subject", value="General", key="manual_subject")
            m_hours = m2.number_input("Hours", min_value=0.0, value=1.0, step=0.25)
            m_chapters = m3.number_input("Chapters", min_value=0, value=0, step=1)
            m_date = st.date_input("Date", value=date.today())
            if st.form_submit_button("Log session"):
                ss.sessions.append(
                    {
                        "date": m_date.isoformat(),
                        "hours": float(m_hours),
                        "chapters_completed": int(m_chapters),
                        "subject": m_subject.strip() or "General",
                    }
                )
                save_sessions()
                st.success("Session logged.")

# ---------------------------- Analytics -------------------------------------
with tab_stats:
    st.subheader("Your progress")
    period = st.selectbox("Period", ["Last 7 days", "Last 30 days", "All time"])

    if not ss.sessions:
        st.info("No sessions yet. Use the timer or log one manually.")
    else:
        df = pd.DataFrame(ss.sessions)
        df["date"] = pd.to_datetime(df["date"])
        if period == "Last 7 days":
            df = df[df["date"] >= pd.Timestamp(date.today() - timedelta(days=6))]
        elif period == "Last 30 days":
            df = df[df["date"] >= pd.Timestamp(date.today() - timedelta(days=29))]

        if df.empty:
            st.info("No sessions in this period.")
        else:
            m1, m2, m3 = st.columns(3)
            m1.metric("Total hours", f"{df['hours'].sum():.2f}")
            m2.metric("Chapters completed", int(df["chapters_completed"].sum()))
            m3.metric("Sessions", len(df))

            st.markdown("**Hours per day**")
            st.bar_chart(df.groupby(df["date"].dt.date)["hours"].sum())

            st.markdown("**Hours per subject**")
            st.bar_chart(df.groupby("subject")["hours"].sum())

            st.markdown("**History**")
            show = df.copy()
            show["date"] = show["date"].dt.date
            st.dataframe(show.sort_values("date", ascending=False), use_container_width=True, hide_index=True)

        if st.button("🗑️ Clear all history"):
            ss.sessions = []
            save_sessions()
            st.rerun()