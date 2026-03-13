import json
from core.embedding_engine import generate_embedding, compute_similarity

# In-memory storage for job descriptions
jobs = {}

def create_job(job_id, title, description, required_skills):
    """
    Create a new job posting.
    """
    embedding = generate_embedding(description)
    jobs[job_id] = {
        "title": title,
        "description": description,
        "required_skills": required_skills,
        "embedding": embedding
    }

def get_job(job_id):
    return jobs.get(job_id)

def compute_resume_job_similarity(job_id, resume_text):
    """
    Compute similarity between resume and job description.
    """
    job = get_job(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")
    resume_emb = generate_embedding(resume_text)
    job_emb = job["embedding"]
    # Simple cosine similarity
    similarity = compute_similarity(resume_text, job["description"])
    return similarity * 100  # percentage

def get_required_skills(job_id):
    job = get_job(job_id)
    return job["required_skills"] if job else []