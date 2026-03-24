import json
from core.llm_client import generate_text

def generate_test(skills, job_desc, difficulty="Intermediate"):
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
  ],
  
  "coding_questions": [
    {{
      "title": "string",
      "description": "string",
      "sample_input": "string",
      "sample_output": "string"
    }}
  ]
}}

Requirements:
- Generate exactly 5 MCQs
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

    raw = generate_text(prompt)

    start = raw.find("{")
    end = raw.rfind("}")
    return json.loads(raw[start:end+1])
