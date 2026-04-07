# import os
# import warnings
# from pathlib import Path
# from typing import List, Optional

# from dotenv import load_dotenv
# from google.api_core import exceptions as google_exceptions
# from google import genai

# # Deprecation noise on import; SDK still works until you migrate to google.genai
# warnings.filterwarnings(
#     "ignore",
#     message=".*google.generativeai.*",
#     category=FutureWarning,
# )

# load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# _configured = False

# # Tried when the preferred model hits 429 / free-tier quota (2.0-flash often shows limit: 0).
# _DEFAULT_MODEL_FALLBACKS: tuple[str, ...] = (
#     "gemini-1.5-flash",
#     "gemini-2.5-flash-lite",
#     "gemini-2.5-flash",
#     "gemini-2.0-flash",
# )

# _last_ok_model: Optional[str] = None


# def _ensure_configured() -> None:
#     global _configured
#     if _configured:
#         return
#     api_key = os.getenv("GEMINI_API_KEY")
#     if not api_key:
#         raise RuntimeError(
#             "GEMINI_API_KEY is not set. Add it to your environment or a .env file "
#             "in AI_HR-Services (see python-dotenv)."
#         )
#     genai.configure(api_key=api_key)
#     _configured = True


# def _model_candidates() -> List[str]:
#     """Ordered, de-duplicated model ids to try."""
#     seen = set()
#     out: List[str] = []

#     def add(mid: Optional[str]) -> None:
#         if mid and mid not in seen:
#             seen.add(mid)
#             out.append(mid)

#     global _last_ok_model
#     add(_last_ok_model)
#     add(os.getenv("GEMINI_MODEL", "").strip() or None)
#     for m in _DEFAULT_MODEL_FALLBACKS:
#         add(m)
#     return out


# def generate_text(prompt: str) -> str:
#     """
#     Sends prompt to Gemini and returns generated text.
#     Tries multiple models if one hits free-tier quota (429 ResourceExhausted).
#     """
#     _ensure_configured()
#     global _last_ok_model

#     last_quota_error: Optional[BaseException] = None
#     candidates = _model_candidates()

#     for model_id in candidates:
#         try:
#             model = genai.GenerativeModel(model_id)
#             response = model.generate_content(prompt)
#             _last_ok_model = model_id

#             if response.text:
#                 return response.text
#             return "Model returned empty response."

#         except google_exceptions.ResourceExhausted as e:
#             last_quota_error = e
#             if model_id == _last_ok_model:
#                 _last_ok_model = None
#             continue

#         except google_exceptions.NotFound:
#             # Wrong model id for this API version / key — try next
#             continue

#     if last_quota_error is not None:
#         raise RuntimeError(
#             "Gemini API: free-tier quota exhausted for every model tried "
#             f"({', '.join(candidates)}). Wait and retry, use another API key, "
#             "enable billing, or set GEMINI_MODEL to a model your project supports. "
#             f"Details: {last_quota_error}"
#         ) from last_quota_error

#     raise RuntimeError(
#         "Gemini API: no model could handle the request. "
#         "Set GEMINI_MODEL to a valid model id for your API key."
#     )



import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai.errors import APIError

# Load .env file
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# =========================
# ✅ CONFIG
# =========================
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is not set. Add it to your .env file."
    )

# ✅ Create client (NEW SDK)
client = genai.Client(api_key=API_KEY)

# Model fallback list (safe + stable)
_DEFAULT_MODEL_FALLBACKS: tuple[str, ...] = (
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
)

_last_ok_model: Optional[str] = None


# =========================
# ✅ MODEL SELECTION
# =========================
def _model_candidates() -> List[str]:
    seen = set()
    out: List[str] = []

    def add(mid: Optional[str]):
        if mid and mid not in seen:
            seen.add(mid)
            out.append(mid)

    global _last_ok_model
    add(_last_ok_model)
    add(os.getenv("GEMINI_MODEL", "").strip() or None)

    for m in _DEFAULT_MODEL_FALLBACKS:
        add(m)

    return out


# =========================
# ✅ MAIN FUNCTION
# =========================
def generate_text(prompt: str) -> str:
    """
    Generate text using Gemini (new SDK)
    with fallback models for quota handling.
    """
    global _last_ok_model

    last_error: Optional[Exception] = None
    candidates = _model_candidates()

    for model_id in candidates:
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
            )

            _last_ok_model = model_id

            if response.text:
                return response.text

            return "Model returned empty response."

        except APIError as e:
            last_error = e
            continue

        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(
        f"Gemini API failed for all models: {candidates}. Error: {last_error}"
    )