import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found")

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel("gemini-1.5-flash")


def evaluate_resume(resume_text: str, job_description: str):

    prompt = f"""
You are an AI HR evaluator.

Evaluate the candidate resume against the job description.

Return JSON only.

Resume:
{resume_text}

Job Description:
{job_description}

Return in JSON format:

{{
"score": number from 0-100,
"matching_skills": [],
"missing_skills": [],
"experience_match": "",
"final_recommendation": "Hire / Maybe / Reject"
}}
"""

    response = model.generate_content(prompt)

    return response.text


# from sentence_transformers import SentenceTransformer
# from sklearn.metrics.pairwise import cosine_similarity

# model = SentenceTransformer("all-MiniLM-L6-v2")

# def generate_embedding(text):
#     return model.encode(text).tolist()

# def compute_similarity(text1, text2):
#     emb1 = model.encode([text1])
#     emb2 = model.encode([text2])
#     return float(cosine_similarity(emb1, emb2)[0][0])
