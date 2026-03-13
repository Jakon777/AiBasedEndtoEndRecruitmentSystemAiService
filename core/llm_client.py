import os
from dotenv import load_dotenv
# import google.generativeai as genai
from google import genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

# genai.configure(api_key=API_KEY)
client = genai.Client(api_key=API_KEY)

# model = genai.GenerativeModel("gemini-2.5-flash")


def generate_text(prompt: str) -> str:
    """
    Sends prompt to Gemini and returns generated text.
    Used by test generator service.
    """

    try:
        # response = model.generate_content(prompt)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        if response.text:
            return response.text
        else:
            return "Model returned empty response."

    except Exception as e:
        raise RuntimeError(f"Gemini API error: {str(e)}")