import uuid
import json
from typing import Any

from core.llm_client import generate_text

# In-memory sessions
sessions: dict[str, Any] = {}

_SINGLE_QUESTION_RULES = """
Rules:
- Ask exactly ONE question per message. No numbered lists of multiple questions.
- Do not bundle several unrelated questions; one clear question only.
- Be conversational and human-like; use follow-ups based on prior answers.
- Mix technical and behavioral questions as appropriate.
- Keep the interview structured and professional.
"""


def _format_job_posting(job: dict[str, Any]) -> str:
    """Turn a job posting document (e.g. Mongo JobPostings) into prompt text."""
    lines: list[str] = []
    order = [
        "id",
        "title",
        "description",
        "skillsRequired",
        "experienceRequired",
        "profile",
        "jobType",
        "locations",
        "salaryRange",
        "salaryRangeInLPA",
        "currency",
        "shortlistPercentage",
        "companyId",
        "isAssessmentRequired",
        "isInterviewRequired",
        "isActive",
    ]
    seen: set[str] = set()
    for key in order:
        if key not in job:
            continue
        val = job[key]
        if val is None or val == "":
            continue
        seen.add(key)
        if isinstance(val, (list, dict)):
            lines.append(f"- {key}: {json.dumps(val, default=str)}")
        else:
            lines.append(f"- {key}: {val}")
    for key, val in sorted(job.items()):
        if key in seen or str(key).startswith("$"):
            continue
        if val is None or val == "":
            continue
        if isinstance(val, (list, dict)):
            lines.append(f"- {key}: {json.dumps(val, default=str)}")
        else:
            lines.append(f"- {key}: {val}")
    return "\n".join(lines) if lines else "(no job fields provided)"


def _format_resume_context(parsed: dict[str, Any]) -> str:
    name = (parsed.get("name") or "").strip()
    phone = (parsed.get("phone") or "").strip()
    emails = parsed.get("email") or []
    if not isinstance(emails, list):
        emails = []
    skills = parsed.get("skills") or []
    if not isinstance(skills, list):
        skills = []
    full_text = str(parsed.get("full_text") or parsed.get("text_for_similarity") or "").strip()
    max_resume_chars = 9000
    if len(full_text) > max_resume_chars:
        full_text = full_text[:max_resume_chars] + "\n[... resume truncated ...]"
    parts = [
        f"Detected name: {name or 'unknown'}",
        f"Contact: emails={emails}, phone={phone or 'n/a'}",
        f"Skills from resume (keyword match): {', '.join(skills) if skills else 'none detected'}",
        "Resume text (for interview context):",
        full_text or "(no text extracted from PDF)",
    ]
    return "\n".join(parts)


# -----------------------------
# SYSTEM PROMPT (IMPORTANT)
# -----------------------------
def build_system_prompt(job: dict[str, Any], resume_context: str) -> str:
    job_block = _format_job_posting(job)
    return f"""
You are a professional AI interviewer.

Job posting (complete context):
{job_block}

Candidate resume (parsed from uploaded PDF):
{resume_context}

{_SINGLE_QUESTION_RULES}
"""


# -----------------------------
# START INTERVIEW
# -----------------------------
def start_interview(
    candidate_id: str,
    job: dict[str, Any],
    resume_parsed: dict[str, Any],
    *,
    job_posting_id: str | None = None,
    job_application_id: str | None = None,
    resume_id: str | None = None,
) -> tuple[str, str]:
    session_id = str(uuid.uuid4())

    resume_context = _format_resume_context(resume_parsed)
    system_prompt = build_system_prompt(job, resume_context)

    opener = (
        "Start the interview with the first question only. "
        "Remember: exactly one question, no lists of multiple questions."
    )
    first_question = generate_text(system_prompt + "\n" + opener)

    sessions[session_id] = {
        "candidate_id": candidate_id,
        "job": job,
        "job_posting_id": job_posting_id,
        "job_application_id": job_application_id,
        "resume_id": resume_id,
        "resume_context": resume_context,
        "history": [
            {"role": "system", "content": system_prompt},
            {"role": "assistant", "content": first_question},
        ],
        "scores": [],
    }

    return session_id, first_question.strip()


# -----------------------------
# EVALUATE ANSWER (LLM-based)
# -----------------------------
def evaluate_answer_llm(question: str, answer: str):
    prompt = f"""
Evaluate the candidate answer.

Question: {question}
Answer: {answer}

Return STRICT JSON only:

{{
  "score": number (0-10),
  "technical_accuracy": number (0-10),
  "communication": number (0-10),
  "relevance": number (0-10),
  "feedback": "short feedback"
}}
"""

    raw = generate_text(prompt)

    try:
        start = raw.find("{")
        end = raw.rfind("}")
        data = json.loads(raw[start:end+1])
        return data
    except:
        return {
            "score": 5,
            "technical_accuracy": 5,
            "communication": 5,
            "relevance": 5,
            "feedback": "Evaluation failed, default score applied",
        }


# -----------------------------
# NEXT QUESTION (CONVERSATIONAL)
# -----------------------------
def generate_next_question(history):
    conversation = "\n".join(
        [f"{h['role']}: {h['content']}" for h in history]
    )

    prompt = f"""
Continue this interview naturally.

Conversation so far:
{conversation}

Ask the next relevant question only. Exactly ONE question — no multi-part lists or several questions at once.
"""

    return generate_text(prompt)


# -----------------------------
# PROCESS ANSWER
# -----------------------------
def process_answer(session_id: str, answer: str):
    session = sessions.get(session_id)

    if not session:
        return {"error": "Invalid session"}

    history = session["history"]

    # Last question asked
    last_question = history[-1]["content"]

    # Evaluate answer
    evaluation = evaluate_answer_llm(last_question, answer)
    session["scores"].append(evaluation["score"])

    # Update conversation
    history.append({"role": "user", "content": answer})

    # Stop condition (after ~5–7 questions)
    if len(session["scores"]) >= 6:
        avg_score = sum(session["scores"]) / len(session["scores"])
        result = "Selected" if avg_score >= 6 else "Rejected"

        return {
            "message": "Interview completed",
            "average_score": round(avg_score, 2),
            "result": result,
            "detailed_evaluations": session["scores"],
        }

    # Generate next question
    next_q = generate_next_question(history)

    history.append({"role": "assistant", "content": next_q})

    return {
        "score": evaluation["score"],
        "feedback": evaluation["feedback"],
        "next_question": next_q.strip(),
    }