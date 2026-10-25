from urllib.parse import quote

import streamlit as st

LEAF_LIGHT = "#a9c3a4"
LEAF_DARK = "#6f9477"
TRUNK = "#5b4638"
CLOUD = "#eef2dc"


# ----------------------------------------------------------------------------
# Pixel-art helpers (everything is drawn with plain rectangles)
# ----------------------------------------------------------------------------
def _r(x, y, w, h, fill):
    return f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" fill="{fill}"/>'


def _pine(cx, ground, tiers, px):
    out = []
    top = ground - 2 * px - tiers * 3 * px
    for t in range(tiers):
        for k in range(3):
            w = (1 + 2 * (t + k)) * px
            y = top + (t * 3 + k) * px
            out.append(_r(cx - w / 2, y, w, px, LEAF_LIGHT if k < 2 else LEAF_DARK))
    out.append(_r(cx - px, ground - 2 * px, 2 * px, 2 * px, TRUNK))
    return "".join(out)


def _cloud(x, y, px):
    rows = [(4, 3), (2, 7), (0, 11), (1, 9)]
    return "".join(_r(x + off * px, y + i * px, w * px, px, CLOUD)
                   for i, (off, w) in enumerate(rows))


def _bunny(ox, oy, c=5):
    white, ink, red, pink = "#f6f4ee", "#2a2f3a", "#d4645c", "#e8a3a0"
    cells = [
        (1, 0, 1, 3, white), (3, 0, 1, 3, white),                      # ears
        (0, 3, 5, 3, white), (3, 4, 1, 1, ink), (4, 5, 1, 1, pink),    # head, eye, nose
        (0, 6, 5, 4, red),                                             # sweater
        (-1, 8, 1, 2, white),                                          # tail
        (0, 10, 2, 1, white), (3, 10, 2, 1, white),                    # feet
        (5, 7, 2, 1, red),                                             # arm
    ]
    out = [_r(ox + x * c, oy + y * c, w * c, h * c, f) for x, y, w, h, f in cells]
    for x, y in [(7, 6), (8, 5), (9, 4), (10, 3), (11, 2), (12, 1)]:   # fishing rod
        out.append(_r(ox + x * c, oy + y * c, c, c, TRUNK))
    line_x, line_top = ox + 13 * c - 1, oy + c
    out.append(_r(line_x, line_top, 1.5, 188 - line_top, "#2c4a43"))   # line
    out.append(_r(line_x - 2, 184, 6, 6, red))                         # bobber
    return "".join(out)


def _svg(view_w, view_h, body, extra=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view_w} {view_h}" '
            f'shape-rendering="crispEdges" {extra}>{body}</svg>')


# ----------------------------------------------------------------------------
# Full-screen background: sky, clouds, pines on both sides, pond at the bottom
# ----------------------------------------------------------------------------
def _background_svg():
    px, ground = 12, 790
    p = ['<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
         '<stop offset="0" stop-color="#aecbc6"/><stop offset="1" stop-color="#dde9df"/>'
         '</linearGradient></defs>',
         '<rect width="1600" height="900" fill="url(#g)"/>']
    for x, y, s in [(220, 110, 16), (900, 60, 18), (1180, 230, 12), (40, 300, 12), (620, 250, 10)]:
        p.append(_cloud(x, y, s))
    for cx, tiers in [(60, 6), (170, 4), (280, 5), (1330, 5), (1440, 7), (1550, 4)]:
        p.append(_pine(cx, ground, tiers, px))
    p.append(_r(0, ground - 2, 1600, 14, "#4f7358"))
    p.append(_r(0, ground + 12, 1600, 900 - ground - 12, "#8fb0b0"))
    for x, y, w in [(100, 830, 90), (420, 860, 120), (760, 835, 100), (1100, 865, 130), (1400, 832, 90)]:
        p.append(_r(x, y, w, 5, "#b3cccb"))
    return _svg(1600, 900, "".join(p), 'preserveAspectRatio="xMidYMax slice"')


# ----------------------------------------------------------------------------
# Banner scene with the fishing bunny (shown under the title)
# ----------------------------------------------------------------------------
def scene_html():
    px, ground = 6, 168
    p = ['<rect width="640" height="200" fill="#b7d1cc"/>']
    for x, y, s in [(235, 30, 8), (500, 46, 7)]:
        p.append(_cloud(x, y, s))
    for cx, tiers in [(40, 3), (100, 4), (185, 5), (455, 4), (535, 5), (610, 3)]:
        p.append(_pine(cx, ground, tiers, px))
    p.append(_r(0, 166, 640, 8, "#4f7358"))
    p.append(_r(0, 174, 640, 26, "#8fb0b0"))
    for x, y, w in [(60, 184, 40), (220, 192, 56), (420, 184, 48), (540, 192, 36)]:
        p.append(_r(x, y, w, 3, "#b3cccb"))
    p.append(_r(285, 166, 100, 8, "#7a5c45"))        # little dock
    p.append(_bunny(300, 111))
    svg = _svg(640, 200, "".join(p),
               'width="100%" style="display:block;border:2px solid #2c4a43;'
               'border-radius:12px;box-shadow:5px 5px 0 #2c4a43;margin:1.2rem 0 .4rem"')
    return svg


# ----------------------------------------------------------------------------
# Page styling
# ----------------------------------------------------------------------------
CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

html, body, .stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3,
.stApp button, .stApp textarea, .stApp input, .stApp small {
  font-family: 'JetBrains Mono', monospace; }

/* keep Streamlit's icon font for arrows and upload icons */
[data-testid="stIconMaterial"], .material-symbols-rounded, [class*="material-symbols"] {
  font-family: 'Material Symbols Rounded' !important; }

/* full-screen pixel background */
.stApp {
  background-color: #cfe0d6;
  background-image: url("data:image/svg+xml,__BG__");
  background-size: cover;
  background-position: center bottom;
  background-attachment: fixed;
}
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { visibility: hidden; }

/* content panel */
.block-container {
  background: rgba(238, 244, 237, 0.88);
  border: 2px solid #2c4a43;
  border-radius: 16px;
  box-shadow: 6px 6px 0 #2c4a43;
  margin: 1.2rem auto 2rem;
  max-width: 960px;
  padding: 1.6rem 2.2rem 3rem;
}
[data-testid="stSidebar"] { background: #f3f1e3; border-right: 2px solid #2c4a43; }

h1, h2, h3 { color: #1d3b36; font-weight: 700; letter-spacing: -0.5px; }
hr { border-color: #2c4a43; }

/* tabs */
button[data-baseweb="tab"] { font-weight: 700; color: #1d3b36; }
button[data-baseweb="tab"][aria-selected="true"] { color: #d4645c; }
[data-baseweb="tab-highlight"] { background-color: #d4645c !important; }

/* buttons */
button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"] {
  background: #d4645c; color: #fff; border: none; border-radius: 999px; font-weight: 700; }
button[data-testid="stBaseButton-primary"]:hover,
button[data-testid="stBaseButton-primaryFormSubmit"]:hover { background: #c0524b; color: #fff; }
button[data-testid="stBaseButton-secondary"],
button[data-testid="stBaseButton-secondaryFormSubmit"] {
  background: #e9f0ea; color: #1d3b36; border: 2px solid #2c4a43;
  border-radius: 999px; font-weight: 700; }

/* inputs and boxes */
textarea { background: #f6f8f1 !important; color: #1d3b36 !important;
  border: 2px solid #2c4a43 !important; border-radius: 12px !important; }
[data-baseweb="input"], [data-baseweb="select"] > div {
  background: #f6f8f1 !important; border: 2px solid #2c4a43 !important;
  border-radius: 12px !important; }
[data-testid="stFileUploaderDropzone"] { background: #f6f4e6;
  border: 2px dashed #2c4a43; border-radius: 12px; }
[data-testid="stForm"] { background: #f6f4e6; border: 2px solid #2c4a43;
  border-radius: 14px; box-shadow: 5px 5px 0 #2c4a43; }
[data-testid="stAlert"] { border: 2px solid #2c4a43; border-radius: 12px; }
[data-testid="stExpander"] { border: 2px solid #2c4a43; border-radius: 12px; background: #f6f4e6; }

/* hero */
.lm-nav { display: flex; justify-content: space-between; align-items: center;
  font-weight: 700; color: #1d3b36; margin-bottom: 1rem; }
.lm-pill { background: #d4645c; color: #fff; padding: .35rem 1rem;
  border-radius: 999px; font-size: .75rem; }
.lm-title { text-align: center; font-size: 3.4rem; font-weight: 700;
  line-height: 1.1; letter-spacing: -2px; }
.lm-last { color: #e8837d; }
.lm-min { color: #556b2f; }
.lm-sub { text-align: center; font-size: .82rem; color: #4b6860;
  max-width: 540px; margin: .8rem auto 0; line-height: 1.6; }
.lm-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;
  text-align: center; margin: 1.4rem 0 0; color: #1d3b36; }
.lm-card b { display: block; font-size: .82rem; margin: .25rem 0; }
.lm-card span { font-size: .72rem; color: #4b6860; line-height: 1.5; }
@media (max-width: 700px) {
  .lm-grid { grid-template-columns: 1fr; }
  .lm-title { font-size: 2.3rem; }
  .block-container { padding: 1.2rem 1rem 2rem; }
}
"""


def inject_css():
    css = CSS.replace("__BG__", quote(_background_svg()))
    st.markdown("<style>" + css + "</style>", unsafe_allow_html=True)


def hero_html():
    return (
        '<div class="lm-nav"><span>🌲 LastMinute</span>'
        '<span class="lm-pill">Powered by Gemma 4</span></div>'
        '<div class="lm-title"><span class="lm-last">Last</span><span class="lm-min">Minute</span></div>'
        '<div class="lm-sub">Exam tomorrow? Paste your notes, PDFs or textbook photos and turn them '
        'into a quiz, then get a calm explanation for everything you got wrong.</div>'
        '<div class="lm-grid">'
        '<div class="lm-card">📝<b>Notes to Quiz</b><span>Paste notes, get multiple-choice questions.</span></div>'
        '<div class="lm-card">💬<b>Gentle Tutor</b><span>Ask anything and get a clear explanation.</span></div>'
        '<div class="lm-card">⏱️<b>Study Tracker</b><span>Time your sessions and see your progress.</span></div>'
        '</div>'
    )


def title_html():
    """Everything shown above the tabs: hero text plus the pixel banner."""
    return hero_html() + scene_html()