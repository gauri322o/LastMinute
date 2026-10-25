from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client()

response = client.models.generate_content(
    model="gemma-4-26b-a4b-it",
    contents="Explain photosynthesis to a 10-year-old."
)
print(response.text)
