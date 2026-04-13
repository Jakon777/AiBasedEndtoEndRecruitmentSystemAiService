import uuid
import json
from typing import Dict, Any

from core.llm_client import generate_text

# In-memory sessions
sessions: Dict[str, Any] = {}


# -----------------------------
# SYSTEM PROMPT (IMPORTANT)
# -----------------------------
def build_system_prompt(job_desc: str):
    return f"""
You are a professional AI interviewer.

Job Description:
{job_desc}

Rules:
- Ask one question at a time
- Be conversational and human-like
- Ask follow-up questions based on candidate answers
- Mix technical + behavioral questions
- Do NOT ask all questions at once
- Keep interview structured and professional
"""


# -----------------------------
# START INTERVIEW
# -----------------------------
def start_interview(candidate_id: str, job_desc: str):
    session_id = str(uuid.uuid4())

    system_prompt = build_system_prompt(job_desc)

    # First question from LLM
    first_question = generate_text(
        system_prompt + "\nStart the interview with the first question."
    )

    sessions[session_id] = {
        "candidate_id": candidate_id,
        "job_desc": job_desc,
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

Ask the next relevant question only.
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