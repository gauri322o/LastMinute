Last Minute Study Assistant

Built at Hacktoberfest x MOSS Hack Day Udupi, 25 October 2026.

Last Minute Study Assistant helps students who are short on time. Paste notes, upload PDFs or take photos of textbook pages and handwritten notes, and the app writes a multiple-choice quiz from them using Gemma 4. It also has a study timer and analytics dashboard (hours and chapters per day and per subject) so you can see your progress.

Challenges entered: Best Open-Source AI Project and Best Use of Gemma 4.

Team members
Gauri Agrawal
Sarthak Patel

What the project does and how it works
Sources tab: the user adds notes, text files, PDFs and images. PDFs are converted to text locally with pypdf. Images are sent to the model as-is, because Gemma 4 understands images.
Quiz tab: the app builds a prompt from the material and asks Gemma 4 for a JSON list of questions (4 options, the correct answer and a short explanation each). The app parses the reply, shows an interactive quiz and scores it.
Study Timer and Analytics tabs: a stopwatch logs study sessions (subject, hours, chapters) to a local JSON file, and the dashboard charts them.
Open-weight model used
Gemma 4, Google's open-weight model family, used through the Gemini API.
Models selectable in the app: gemma-4-26b-a4b-it (default) and gemma-4-31b-it.
Gemma 4 license: https://ai.google.dev/gemma/apache_2
Gemma terms of use: https://ai.google.dev/gemma/terms
Gemma 4 model card: https://ai.google.dev/gemma/docs/core/model_card_4
How the project calls Gemma 4 through the Gemini API

All model calls go through the call_gemma() function in app.py, which uses the google-genai SDK:

python
client = genai.Client(api_key=api_key)
response = client.models.generate_content(
    model="gemma-4-26b-a4b-it",   # or gemma-4-31b-it
    contents=[prompt, image_parts...],
    config=types.GenerateContentConfig(...),
)

The app only offers Gemma 4 models, and the sidebar shows which model wrote the current quiz.

Libraries, frameworks, APIs and datasets
Streamlit (web UI)
google-genai (Gemini API SDK)
pandas (analytics)
pypdf (PDF text extraction)
Gemini API (hosted access to Gemma 4)
No datasets are used.
AI coding tools used
Claude (Anthropic), used as a chat-based coding assistant. It wrote the first version(quiz generation, study timer, analytics), helped debug API errors, and drafted this README, requirements.txt and .gitignore.

how to run it
# 1. Install dependencies (Python 3.10+ recommended)
pip install -r requirements.txt

# 2. Set your Gemini API key (get one at https://aistudio.google.com/apikey)
#    Mac/Linux:
export GEMINI_API_KEY="your-key"
#    Windows PowerShell:
$env:GEMINI_API_KEY="your-key"

# 3. Start the app
streamlit run main.py

Then open http://localhost:8501. You can also paste your key into the sidebar. Never commit your API key.

License
MIT. See LICENSE.