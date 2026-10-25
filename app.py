"""
LastMinute
Hacktoberfest x MOSS Hack Day Udupi, 25 October 2026

Turns your notes, PDFs, YouTube transcripts and photos of textbook pages into a quiz
and a tutor using Gemma 4 (open-weight) through the Gemini API, and tracks your study time.
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

try:
    from dotenv import load_dotenv

    load_dotenv()  # reads GEMINI_API_KEY from a local .env file if there is one
except ImportError:
    pass

try:
    from style import inject_css, title_html
except ImportError:
    # style.py is missing or an older version: fall back to a plain look
    def inject_css():
        pass

    def title_html():
        return "<h1 style='text-align:center'>📚 LastMinute</h1>"

st.set_page_config(page_title="LastMinute", page_icon="📚", layout="wide")
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
ss.setdefault("tutor_answer", "")
ss.setdefault("yt_cache", {})
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
    help="Reads GEMINI_API_KEY from your environment or .env file by default. Never commit your key.",
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
    """Single place where the app calls Gemma 4 through the Gemini API.
    Retries on temporary server errors, then falls back to plain settings."""
    level = "high" if deep else "minimal"
    try:
        full_config = types.GenerateContentConfig(
            temperature=0.7,
            thinking_config=types.ThinkingConfig(thinking_level=level),
        )
    except Exception:
        # Older google-genai versions don't know thinking_level
        full_config = types.GenerateContentConfig(temperature=0.7)
    plain_config = types.GenerateContentConfig(temperature=0.7)

    temporary = ("500", "503", "429", "internal", "unavailable", "overloaded", "deadline")
    last_error = None
    for attempt in range(3):
        config = full_config if attempt == 0 else plain_config  # drop thinking after the first try
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except Exception as e:
            last_error = e
            msg = str(e).lower()
            if "thinking" in msg:
                continue
            if any(word in msg for word in temporary):
                time.sleep(2 * (attempt + 1))  # wait 2s, then 4s
                continue
            raise
    raise last_error


# ----------------------------------------------------------------------------
# Source reading (shared by the Quiz and the Tutor)
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


def youtube_video_id(url: str):
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/|/live/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else None


def get_youtube_transcript(url: str):
    """Returns (transcript_text, error_message). The video needs captions."""
    video_id = youtube_video_id(url)
    if not video_id:
        return "", "that doesn't look like a YouTube video link"

    if video_id in ss.yt_cache:
        return ss.yt_cache[video_id], ""

    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return "", "youtube-transcript-api is not installed (run: python -m pip install youtube-transcript-api)"

    langs = ["en", "en-IN", "hi", "kn"]
    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):  # older versions
            try:
                items = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
            except Exception:
                items = next(iter(YouTubeTranscriptApi.list_transcripts(video_id))).fetch()
            parts = [i["text"] for i in items]
        else:  # newer versions
            api = YouTubeTranscriptApi()
            try:
                fetched = api.fetch(video_id, languages=langs)
            except Exception:
                fetched = next(iter(api.list(video_id))).fetch()
            parts = [s.text for s in fetched]
    except Exception as e:
        first_line = (str(e).strip().splitlines() or [""])[0]
        return "", f"{type(e).__name__}: {first_line[:120]}"

    text = " ".join(parts).strip()
    if not text:
        return "", "the transcript was empty"
    ss.yt_cache[video_id] = text  # only successes are remembered
    return text, ""


def collect_materials(notes, youtube_url, uploaded_docs, uploaded_images):
    """Gather everything from the Sources tab. Returns (text, images, warnings)."""
    text_parts, images, warnings = [], [], []

    if notes and notes.strip():
        text_parts.append(f"--- Notes ---\n{notes}")

    if youtube_url and youtube_url.strip():
        link = youtube_url.strip()
        transcript, err = get_youtube_transcript(link)
        if transcript:
            text_parts.append(f"--- YouTube transcript ({link}) ---\n{transcript}")
        else:
            warnings.append(
                f"Couldn't get a transcript for that YouTube link ({err}). "
                "Open the video's transcript on YouTube and paste it into the notes box instead."
            )

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

    text = "\n\n".join(text_parts)
    if len(text) > MAX_CONTEXT_CHARS:
        text = text[:MAX_CONTEXT_CHARS]
        warnings.append(f"Your material was long, so only the first {MAX_CONTEXT_CHARS:,} characters were used.")
    return text, images, warnings


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
Base every question on the materials, not on outside knowledge.

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
# Tutor helper
# ----------------------------------------------------------------------------
def ask_tutor(client, model, text, images, question, deep):
    materials = text or ("(see the attached images)" if images else "(no study materials were added)")
    prompt = f"""
You are a gentle, expert study tutor.
Using the study materials provided below, answer the student's question clearly and helpfully.
If the answer is not explicitly in the study materials, use your general knowledge to explain it
clearly, keeping it relevant to the context.

Study Materials:
{materials}

Student Question:
{question}
"""
    contents = [prompt]
    for data, mime in images:
        contents.append(types.Part.from_bytes(data=data, mime_type=mime))

    response = call_gemma(client, model, contents, deep)
    return response.text or "(The tutor returned an empty answer. Please try again.)"


# ----------------------------------------------------------------------------
# Timer helpers (state changes happen in callbacks so the display is reliable)
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
# Page
# ----------------------------------------------------------------------------
st.markdown(title_html(), unsafe_allow_html=True)

tab_sources, tab_quiz, tab_tutor, tab_timer, tab_stats = st.tabs(
    ["1️⃣ Sources", "2️⃣ Quiz", "💬 Tutor", "⏱️ Study Timer", "📊 Analytics"]
)

# ---------------------------- Sources ---------------------------------------
with tab_sources:
    st.subheader("Add your study material")
    st.caption("Everything you add here is used by the Quiz and the Tutor. No separate upload step.")

    notes = st.text_area("Paste notes", height=180, key="notes")
    youtube_url = st.text_input(
        "YouTube link (optional)",
        key="youtube_url",
        help="The app reads the video's captions (transcript). Videos without captions won't work.",
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
        f"{len(uploaded_docs)} document(s), {len(uploaded_images)} image(s)"
        f"{', 1 YouTube link' if (youtube_url or '').strip() else ''}."
    )

# ---------------------------- Quiz ------------------------------------------
with tab_quiz:
    st.subheader("Generate a quiz")
    c1, c2 = st.columns([1, 2])
    num_questions = c1.slider("Number of questions", 3, 20, 5)
    topic_focus = c2.text_input("Topic focus (optional)", placeholder="e.g. Chapter 3: Thermodynamics")

    if st.button("✨ Generate quiz", type="primary"):
        context_text, images, warnings = collect_materials(
            notes, youtube_url, uploaded_docs, uploaded_images
        )
        for w in warnings:
            st.warning(w)

        if not api_key:
            st.error("Add your Gemini API key in the sidebar first.")
        elif not context_text.strip() and not images:
            st.error(
                "Nothing to build a quiz from. Add notes, files, images or a YouTube link "
                "(with captions) in the Sources tab first."
            )
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

# ---------------------------- Tutor -----------------------------------------
with tab_tutor:
    st.subheader("Ask your AI tutor")
    st.caption("Ask about your notes, PDFs, videos or photos from the Sources tab and get a clear explanation.")

    tutor_query = st.text_input(
        "What would you like explained?",
        placeholder="e.g. Can you explain the main idea of Chapter 2?",
        key="tutor_query",
    )

    if st.button("Ask tutor", type="primary"):
        context_text, images, warnings = collect_materials(
            notes, youtube_url, uploaded_docs, uploaded_images
        )
        for w in warnings:
            st.warning(w)

        if not api_key:
            st.error("Add your Gemini API key in the sidebar first.")
        elif not tutor_query.strip():
            st.warning("Please type a question for the tutor.")
        else:
            try:
                client = make_client(api_key)
                with st.spinner(f"Tutor ({model_name}) is thinking…"):
                    ss.tutor_answer = ask_tutor(
                        client, model_name, context_text, images, tutor_query, deep_thinking
                    )
            except Exception as e:
                ss.tutor_answer = ""
                st.error(f"Tutor response failed: {e}")

    if ss.tutor_answer:
        st.divider()
        st.markdown("### Answer")
        st.markdown(ss.tutor_answer)

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

    # The display refreshes itself every second while the timer is running.
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