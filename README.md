# 📚 LastMinute

**Turn your notes, PDFs, YouTube transcripts and photos of textbook pages into a quiz and a personal tutor, and track how long you study.**

Built at **Hacktoberfest x MOSS Hack Day Udupi** (Manipal Open Source Society, MIT Manipal, 25 October 2026).

**Challenges entered:** Best Use of Gemma 4 · Best Open-Source AI Project

---

## What it does

Exam is tomorrow and your material is scattered across notes, slides, a lecture video and photos of a textbook? LastMinute puts it all in one place and uses **Gemma 4** to help you study it.

| Tab | What it does |
|---|---|
| **1️⃣ Sources** | Add material once: pasted notes, PDFs / `.txt` / `.md` files, a YouTube link (uses the video's captions), and photos of notes, diagrams or textbook pages. Everything is shared by the Quiz and the Tutor. |
| **2️⃣ Quiz** | Generates 3 to 20 multiple-choice questions grounded in your material, with an optional topic focus. Submit your answers to get a score and an explanation for every question. |
| **💬 Tutor** | Ask any question about your material and get a clear explanation. If the answer isn't in your sources, the tutor falls back on general knowledge, keeping it relevant. |
| **⏱️ Study Timer** | Start, pause, reset and save study sessions with a subject and number of chapters completed. You can also log a session manually. |
| **📊 Analytics** | Total hours, chapters completed and sessions, with charts of hours per day and per subject over the last 7 days, 30 days or all time. |

Study sessions are saved to `study_sessions.json`, so they survive restarts.

## How it works

1. **Reading sources.** PDFs are converted to text with `pypdf`. YouTube captions are fetched with `youtube-transcript-api` (English, Hindi and Kannada are tried first). Images are sent to the model directly. Text is capped at 80,000 characters to keep requests fast.
2. **Calling Gemma 4.** All model calls go through one function, `call_gemma()`, which uses the Gemini API (`google-genai` SDK). It retries on temporary server errors (500, 503, 429, timeouts) and falls back to plain settings if "thinking" options are not supported.
3. **Multimodal input.** Text and images are sent together in a single request, so Gemma 4 can read your handwritten notes, diagrams and textbook photos.
4. **Quiz generation.** The model is prompted to return a strict JSON array. The app parses it (including when it is wrapped in code fences), validates each question, and retries once if the JSON is malformed.
5. **Tutor.** The student's question and all sources are sent in one prompt, and the answer is shown as Markdown.

## Gemma 4 and the Gemini API

This project uses **Gemma 4** through the **Gemini API**, which is the required integration for the *Best Use of Gemma 4* challenge.

- **Models used** (selectable in the sidebar):
  - `gemma-4-26b-a4b-it`: faster
  - `gemma-4-31b-it`: larger, usually a bit more accurate
- **Where the integration lives:** `make_client()` and `call_gemma()` in `app.py` call `client.models.generate_content(...)`, and are used by `generate_quiz()` and `ask_tutor()`.
- **Multimodal use:** images are attached as `types.Part.from_bytes(...)` alongside the text prompt.
- **Optional "Deep thinking" toggle:** sets the thinking level to `high` (default is `minimal` for speed).
- **License / terms:** Gemma 4 is an open-weight model released by Google.  See the official page: <https://ai.google.dev/gemma>

## Getting started

### Requirements

- Python 3.10 or newer
- A free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

### Install

```bash
git clone <your-repo-url>
cd <your-repo-folder>

python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

### Add your API key

Create a `.env` file in the project folder:

```
GEMINI_API_KEY=your_key_here
```

You can also paste the key into the app's sidebar. **Never commit your key.** Make sure `.env` is in your `.gitignore`.

### Run

```bash
streamlit run app.py
```

Then open the URL Streamlit prints (usually <http://localhost:8501>).

### Quick tour

1. Go to **Sources** and add some notes, a PDF, a captioned YouTube link, or photos of a textbook page.
2. Open **Quiz**, choose how many questions you want, and click **Generate quiz**.
3. Ask follow-up questions in **Tutor**.
4. Start the **Study Timer**, then **Stop & Save** when you finish, and check **Analytics**.

## Troubleshooting

- **"Couldn't get a transcript" for a YouTube link:** the video must have captions. Open the transcript on YouTube and paste it into the notes box instead.
- **"No text found in your PDF":** it is probably a scan. Upload photos of its pages as images instead.
- **Slow responses:** switch to `gemma-4-26b-a4b-it` and turn off *Deep thinking*.
- **Missing look and feel:** `style.py` is optional. If it is absent, the app falls back to a plain theme.

## Project structure

```
.
├── app.py                 # Streamlit app (UI, Gemma 4 calls, quiz, tutor, timer, analytics)
├── style.py               # Optional custom CSS and title
├── requirements.txt
├── study_sessions.json    # Created automatically; your saved study sessions
├── LICENSE
└── README.md
```

## Built with

**Libraries and frameworks**

- [Streamlit](https://streamlit.io): UI
- [google-genai](https://pypi.org/project/google-genai/): Gemini API client
- [pypdf](https://pypi.org/project/pypdf/): PDF text extraction
- [pandas](https://pandas.pydata.org): analytics
- [python-dotenv](https://pypi.org/project/python-dotenv/): loading the `.env` file
- [youtube-transcript-api](https://pypi.org/project/youtube-transcript-api/): YouTube captions

**APIs:** Gemini API (serving Gemma 4)

**Datasets:** none

## AI tools used to build this project

| Tool | What it produced |
|---|---|
| _e.g. GitHub Copilot / ChatGPT / Claude_ | _e.g. boilerplate for the timer callbacks, README draft_ |

## Team


| Name |
|---|---|
| Gauri Agrawal |
| Sarthak Patel|

## Hackathon details

Built during build time (10:00 AM to 5:00 PM IST) on 25 October 2026 at Hacktoberfest x MOSS Hack Day Udupi, AB4, MIT Manipal. All project code was written during the event. Libraries, frameworks and APIs used are listed above.

## License

This project is released under the **MIT License** (see [`LICENSE`](LICENSE)). 
## Acknowledgements

- [Google Gemma 4](https://ai.google.dev/gemma) and the Gemini API
- [Manipal Open Source Society (MOSS)](https://github.com/) and [Major League Hacking](https://mlh.io) for organizing the event