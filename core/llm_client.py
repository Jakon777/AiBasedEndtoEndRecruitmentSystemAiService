import os
from dotenv import load_dotenv
# import google.generativeai as genai
# from google import genai
import google.generativeai as genai

load_dotenv()

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your environment or a .env file "
            "in AI_HR-Services (see python-dotenv)."
        )
    _client = genai.Client(api_key=api_key)
    return _client


def generate_text(prompt: str) -> str:
    """
    Sends prompt to Gemini and returns generated text.
    Used by test generator service.
    """

    try:
        client = _get_client()
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