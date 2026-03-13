import json
from core.resume_parser import parse_resume
from core.job_manager import compute_resume_job_similarity, get_required_skills
from core.scoring_engine import compute_composite
from core.test_generator import generate_test
from core.llm_client import generate_text
from core.code_evaluator import evaluate_code

# In-memory storage for candidates
candidates = {}

def register_candidate(candidate_id, resume_path, job_id):
    """
    Register a candidate with resume and job application.
    """
    resume_data = parse_resume(resume_path)
    similarity = compute_resume_job_similarity(job_id, resume_data["raw_text"])
    required_skills = get_required_skills(job_id)
    candidate_skills = resume_data["skills"]

    # Initial shortlisting based on similarity and skills
    skill_match = len(set(required_skills) & set(candidate_skills)) / len(required_skills) * 100 if required_skills else 100
    shortlisted = similarity >= 50 and skill_match >= 50  # Thresholds

    candidates[candidate_id] = {
        "resume_data": resume_data,
        "job_id": job_id,
        "similarity": similarity,
        "skill_match": skill_match,
        "shortlisted": shortlisted,
        "mcq_test": None,
        "mcq_score": None,
        "coding_test": None,
        "coding_score": None,
        "interview_passed": None,
        "final_recommendation": None
    }

def get_candidate(candidate_id):
    return candidates.get(candidate_id)

def administer_mcq_test(candidate_id):
    """
    Generate and administer MCQ test.
    Returns questions for frontend to display.
    """
    candidate = get_candidate(candidate_id)
    if not candidate or not candidate["shortlisted"]:
        return None

    job = get_required_skills(candidate["job_id"])
    test_data = generate_test(job, "Intermediate")
    candidate["mcq_test"] = test_data["mcqs"]  # Store questions and correct answers
    return [{"question": q["question"], "options": q["options"]} for q in test_data["mcqs"]]

def evaluate_mcq_answers(candidate_id, user_answers):
    """
    Evaluate MCQ answers.
    user_answers: list of selected options, e.g., ["A", "B", ...]
    """
    candidate = get_candidate(candidate_id)
    if not candidate or not candidate["mcq_test"]:
        return None

    correct_answers = [q["correct_answer"] for q in candidate["mcq_test"]]
    score = sum(1 for user, correct in zip(user_answers, correct_answers) if user == correct) / len(correct_answers) * 100
    candidate["mcq_score"] = score
    candidate["shortlisted"] = score >= 60  # Threshold for next round
    return score >= 60

def administer_coding_test(candidate_id):
    """
    Generate coding test questions.
    """
    candidate = get_candidate(candidate_id)
    if not candidate or not candidate["shortlisted"]:
        return None

    job = get_required_skills(candidate["job_id"])
    test_data = generate_test(job, "Intermediate")
    candidate["coding_test"] = test_data["coding_questions"]
    return test_data["coding_questions"]

def evaluate_coding_submission(candidate_id, code, test_cases):
    """
    Evaluate coding submission.
    """
    candidate = get_candidate(candidate_id)
    if not candidate or not candidate["coding_test"]:
        return None

    result = evaluate_code(code, test_cases)
    score = result["score"]
    candidate["coding_score"] = score
    candidate["shortlisted"] = score >= 70  # Threshold
    return score >= 70

def conduct_ai_interview(candidate_id):
    """
    Conduct AI interview: generate questions and evaluate responses.
    Since it's automated, simulate by generating questions and using LLM to evaluate hypothetical responses.
    But for real automation, need user responses.
    For now, assume we get responses and evaluate.
    """
    candidate = get_candidate(candidate_id)
    if not candidate or not candidate["shortlisted"]:
        return None

    # Generate interview questions
    job = get_required_skills(candidate["job_id"])
    prompt = f"Generate 3 interview questions for skills: {job}"
    questions = generate_text(prompt).split('\n')[:3]

    # In real scenario, collect user responses here
    # For automation, assume responses are provided
    # Evaluate using LLM
    responses = ["Sample response 1", "Sample response 2", "Sample response 3"]  # Placeholder

    evaluation_prompt = f"Evaluate these interview responses for skills {job}: {responses}. Rate from 0-100."
    score_text = generate_text(evaluation_prompt)
    try:
        score = float(score_text.strip())
    except:
        score = 50  # Default

    candidate["interview_score"] = score
    candidate["interview_passed"] = score >= 70
    candidate["shortlisted"] = score >= 70

    return candidate["interview_passed"]

def finalize_candidate(candidate_id):
    """
    Compute final recommendation.
    """
    candidate = get_candidate(candidate_id)
    if not candidate:
        return None

    # Use scoring engine
    similarity = candidate["similarity"]
    required = get_required_skills(candidate["job_id"])
    candidate_skills = candidate["resume_data"]["skills"]
    mcq = candidate.get("mcq_score", 0)
    coding = candidate.get("coding_score", 0)

    result = compute_composite(similarity, required, candidate_skills, mcq, coding)
    candidate["final_recommendation"] = result["recommendation"]
    return result

def get_hr_dashboard():
    """
    Get all shortlisted candidates for HR.
    """
    return {cid: c for cid, c in candidates.items() if c.get("final_recommendation") in ["Strong Shortlist", "Shortlist"]}