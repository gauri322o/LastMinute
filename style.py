from pathlib import Path
import streamlit as st

CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap');

.stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3,
.stApp button, .stApp textarea { font-family: 'DM Sans', sans-serif; }
[data-testid="stHeader"] { background: transparent; }

/* Expanded full-screen width with sage background */
.block-container { 
  max-width: 100% !important; 
  padding: 2.5rem 4rem 4rem 4rem !important; 
  background-color: #d8e2dc;
}

.stApp {
  background-color: #d8e2dc;
}

h2, h3 { color: #2c4a43; font-weight: 700; letter-spacing: -0.5px; }
hr { border-color: #2c4a43; }

/* buttons */
button[kind="primary"], button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"] {
  background: #d4645c; color: #fff; border: none; border-radius: 999px;
  font-weight: 700; padding: .5rem 1.4rem; }
button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="stBaseButton-primaryFormSubmit"]:hover { background: #c0524b; color: #fff; }

button[kind="secondary"], button[data-testid="stBaseButton-secondary"],
button[data-testid="stBaseButton-secondaryFormSubmit"] {
  background: #f4f1ea; color: #2c4a43; border: 2px solid #2c4a43;
  border-radius: 999px; font-weight: 700; }

/* inputs and cards */
textarea { background: #f4f1ea !important; border: 2px solid #2c4a43 !important;
  border-radius: 12px !important; color: #2c4a43 !important; }
[data-testid="stForm"] { background: #f4f1ea; border: 2px solid #2c4a43;
  border-radius: 14px; box-shadow: 6px 6px 0 #2c4a43; padding: 1.8rem; }
[data-testid="stAlert"] { border: 2px solid #2c4a43; border-radius: 12px; }

/* custom hero */
.lm-nav { display: flex; justify-content: space-between; align-items: center;
  font-weight: 700; margin-bottom: 2rem; color: #2c4a43; font-size: 1.1rem; }
.lm-last { color: #d4645c; }
.lm-min { color: #13222f; }
.lm-pill { background: #d4645c; color: #fff; padding: .35rem 1.2rem;
  border-radius: 999px; font-size: .85rem; }
.lm-hero { text-align: center; color: #2c4a43; margin-bottom: 2rem; }
.lm-title { font-size: 3.8rem; font-weight: 700; line-height: 1.1; letter-spacing: -1px; }
.lm-sub { font-size: 1.05rem; color: #4f6b63; max-width: 600px; margin: 1rem auto 0; }

.lm-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem;
  text-align: center; margin: 2rem 0; color: #2c4a43; }
.lm-card { background: #f4f1ea; padding: 1.5rem; border: 2px solid #2c4a43; border-radius: 14px; box-shadow: 5px 5px 0 #2c4a43; }
.lm-card b { display: block; font-size: 1rem; margin: .4rem 0; color: #2c4a43; }
.lm-card span { font-size: .9rem; color: #4f6b63; }

@media (max-width: 768px) {
  .lm-grid { grid-template-columns: 1fr; }
  .lm-title { font-size: 2.6rem; }
}
"""


def bg_css():
    return """
.stApp {
  background-color: #d8e2dc;
}
[data-testid="stToolbar"] { visibility: hidden; }
"""


def inject_css():
    st.markdown("<style>" + CSS + bg_css() + "</style>", unsafe_allow_html=True)


def hero_html():
    return (
        '<div class="lm-nav"><span>🌲 <span class="lm-last">Last</span><span class="lm-min">Minute</span></span>'
        '<span class="lm-pill">Start Your Journey →</span></div>'
        '<div class="lm-hero">'
        '<div class="lm-title">Where Panic<br>Meets Progress.</div>'
        '<div class="lm-sub">Exam tomorrow? Paste your notes and turn them into a quiz, '
        'then get a calm explanation for everything you got wrong.</div></div>'
        '<div class="lm-grid">'
        '<div class="lm-card">📝<b>Notes to Quiz</b><span>Paste notes, get multiple-choice questions.</span></div>'
        '<div class="lm-card">✅<b>Honest Marking</b><span>Scored by plain code, so it is always accurate.</span></div>'
        '<div class="lm-card">🌿<b>Gentle Tutor</b><span>Explains your mistakes using your own notes.</span></div>'
        '</div>'
    )


def _pine(cx, ground, tiers, px, light, dark):
    out = []
    rows = tiers * 3
    top = ground - 2 * px - rows * px
    for t in range(tiers):
        for k in range(3):
            w = (1 + 2 * (t + k)) * px
            y = top + (t * 3 + k) * px
            color = light if k < 2 else dark
            out.append(f'<rect x="{cx - w / 2}" y="{y}" width="{w}" height="{px}" fill="{color}"/>')
    out.append(f'<rect x="{cx - px}" y="{ground - 2 * px}" width="{2 * px}" height="{2 * px}" fill="#5b4638"/>')
    return "".join(out)


def scene_html():
    px, ground = 6, 168
    trees = [(45, 3), (105, 4), (190, 5), (290, 3), (395, 4), (480, 5), (560, 3), (615, 4)]
    parts = ['<rect width="640" height="200" fill="#c4d5cc"/>']
    for x, y, w, h in [(230, 44, 96, 16), (250, 30, 54, 14), (214, 58, 132, 14),
                       (470, 52, 70, 14), (486, 40, 36, 12)]:
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#eaf2ec"/>')
    for cx, tiers in trees:
        parts.append(_pine(cx, ground, tiers, px, "#8fae9b", "#547864"))
    parts.append('<rect y="166" width="640" height="8" fill="#436352"/>')
    parts.append('<rect y="174" width="640" height="26" fill="#7fa494"/>')
    for x, y, w in [(60, 184, 40), (220, 190, 56), (420, 184, 48), (540, 192, 36)]:
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="3" fill="#a3c1b3"/>')
    return ('<svg viewBox="0 0 640 200" width="100%" shape-rendering="crispEdges" '
            'style="display:block;border:2px solid #2c4a43;border-radius:14px;'
            'box-shadow:6px 6px 0 #2c4a43;margin-bottom:2rem">'
            + "".join(parts) + '</svg>')