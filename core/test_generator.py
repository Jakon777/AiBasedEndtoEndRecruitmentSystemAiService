import json
from core.llm_client import generate_text
from core.logging_config import get_logger

log = get_logger("ai_hr.core.TestGenerator")

def _local_mcq_fallback(skills, difficulty="Intermediate"):
    log.warning("Activating deterministic fallback MCQ generator for skills=%s, difficulty=%s", skills, difficulty)
    skill_list = [str(s).strip() for s in (skills or []) if str(s).strip()]
    if not skill_list:
        skill_list = ["General Programming"]

    mcqs = []
    for i in range(30):
        skill = skill_list[i % len(skill_list)]
        mcqs.append(
            {
                "question": f"[Fallback {difficulty}] Which statement is most accurate about {skill}?",
                "options": [
                    f"{skill} requires understanding core fundamentals.",
                    f"{skill} is only useful in one programming language.",
                    f"{skill} never changes over time.",
                    f"{skill} has no impact on production systems.",
                ],
                "correct_answer": f"{skill} requires understanding core fundamentals.",
            }
        )

    log.info("Generated %d fallback MCQs successfully", len(mcqs))
    return {"mcqs": mcqs}


def generate_test(skills, job_desc, difficulty="Intermediate"):
    log.info("Invoking Gemini LLM for MCQ test generation (target: 30 questions, difficulty='%s')", difficulty)
    prompt = f"""
You are an AI technical interview generator.

Generate questions based on:

Skills: {skills}
Job Description: {job_desc}
Difficulty: {difficulty}

Return ONLY valid JSON.

Rules:
- No explanations
- No markdown
- No text before or after JSON

JSON schema:

{{
  "mcqs": [
    {{
      "question": "string",
      "options": ["A","B","C","D"],
      "correct_answer": "A"
    }}
  ]
    }}

Requirements:
- Generate exactly 30 MCQs
"""
# - Generate exactly 2 coding questions

#     prompt = f"""
# Generate STRICT JSON only.

# Skills: {skills}
# Difficulty: {difficulty}

# Format:
# {{
#   "mcqs":[{{"question":"","options":["A","B","C","D"],"correct_answer":""}}],
#   "coding_questions":[{{"title":"","description":"","sample_input":"","sample_output":""}}]
# }}

# Generate 5 MCQs and 2 coding questions.
# """

    try:
        raw = generate_text(prompt)
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Model did not return JSON object content")
        data = json.loads(raw[start:end + 1])
        log.info("Gemini successfully generated %d test MCQs", len(data.get("mcqs", [])))
        return data
    except Exception as e:
        log.warn("Gemini generation failed: %s. Falling back to local test generator.", e)
        return _local_mcq_fallback(skills, difficulty)
