# import os
# import google.generativeai as genai
# from dotenv import load_dotenv

# load_dotenv()

# API_KEY = os.getenv("GEMINI_API_KEY")

# if not API_KEY:
#     raise ValueError("GEMINI_API_KEY not found")

# genai.configure(api_key=API_KEY)

# model = genai.GenerativeModel("gemini-2.5-flash")


# def evaluate_resume(resume_text: str, job_description: str):

#     prompt = f"""
# You are an AI HR evaluator.

# Evaluate the candidate resume against the job description.

# Return JSON only.

# Resume:
# {resume_text}

# Job Description:
# {job_description}

# Return in JSON format:

# {{
# "score": number from 0-100,
# "matching_skills": [],
# "missing_skills": [],
# "experience_match": "",
# "final_recommendation": "Hire / Maybe / Reject"
# }}
# """

#     response = model.generate_content(prompt)

#     return response.text


# # from sentence_transformers import SentenceTransformer
# # from sklearn.metrics.pairwise import cosine_similarity

# # model = SentenceTransformer("all-MiniLM-L6-v2")

# # def generate_embedding(text):
# #     return model.encode(text).tolist()

# # def compute_similarity(text1, text2):
# #     emb1 = model.encode([text1])
# #     emb2 = model.encode([text2])
# #     return float(cosine_similarity(emb1, emb2)[0][0])



from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # Force CPU to keep memory predictable on small hosts.
        _model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
        # SentenceTransformer defaults are typically fine, but capping helps
        # keep tokenization / attention work bounded.
        if hasattr(_model, "max_seq_length") and _model.max_seq_length:
            _model.max_seq_length = min(int(_model.max_seq_length), 256)
    return _model


def generate_embedding(text: str):
    """
    Generate embedding vector for a given text.
    """
    # Use a small batch size + no progress bar to reduce per-request RAM.
    return _get_model().encode(
        text,
        batch_size=1,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=False,
    )


def compute_similarity(text1: str, text2: str):
    """
    Compute cosine similarity between two texts.
    """
    emb1 = generate_embedding(text1)
    emb2 = generate_embedding(text2)

    score = cosine_similarity([emb1], [emb2])[0][0]

    return float(score)