import re
from typing import Any, Dict, List, Tuple

from core.embedding_engine import compute_similarity

# Weight semantic fit vs explicit skill overlap (0–1 each, then scaled to score 0–100)
_SIMILARITY_WEIGHT = 0.5
_SKILL_WEIGHT = 0.5
# Combined score (0–100) at or above this => shortlisted
_SHORTLIST_THRESHOLD = 58.0


def _norm_skill(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _skill_satisfied(required: str, candidate_skills: List[str]) -> bool:
    r = _norm_skill(required)
    if not r:
        return True
    for c in candidate_skills:
        cn = _norm_skill(c)
        if not cn:
            continue
        if r == cn or r in cn or cn in r:
            return True
    return False


def _skills_overlap(
    required: List[str], candidate_skills: List[str]
) -> Tuple[float, List[str], List[str]]:
    if not required:
        return 1.0, [], []
    matched = [s for s in required if _skill_satisfied(s, candidate_skills)]
    matched_set = set(matched)
    missing = [s for s in required if s not in matched_set]
    ratio = len(matched) / len(required)
    return ratio, matched, missing


def build_job_text(job: Dict[str, Any]) -> str:
    parts: List[str] = []
    title = job.get("title")
    if title:
        parts.append(str(title))
    profile = job.get("profile")
    if profile:
        parts.append(str(profile))
    desc = job.get("description")
    if desc:
        parts.append(str(desc))
    skills = job.get("skillsRequired") or []
    if skills:
        parts.append("Required skills: " + ", ".join(str(s) for s in skills))
    exp = job.get("experienceRequired")
    if exp is not None:
        parts.append(f"Minimum experience (years): {exp}")
    jt = job.get("jobType")
    if jt:
        parts.append(f"Job type: {jt}")
    return "\n".join(parts) if parts else ""


def evaluate_shortlist(job: Dict[str, Any], resume_path: str) -> Dict[str, Any]:
    """
    Parse resume PDF, compare to job posting via embeddings + required skills.
    """
    from core.resume_parser import parse_resume

    # Don't keep the full (potentially huge) resume text in memory.
    # We only need a bounded slice for embeddings.
    parsed = parse_resume(resume_path, include_full_text=False)
    resume_text = (parsed.get("text_for_similarity") or parsed.get("text_preview") or "").strip()
    candidate_skills: List[str] = list(parsed.get("skills") or [])

    job_text = build_job_text(job).strip()
    # Cap job text too; embedding tokenization can otherwise spike memory for
    # very large descriptions.
    job_text = job_text[:4000] if job_text else job_text
    required = [str(s) for s in (job.get("skillsRequired") or [])]

    if not resume_text:
        return {
            "shortlisted": False,
            "score": 0.0,
            "similarity": 0.0,
            "skillsMatchRatio": 0.0,
            "matchedSkills": [],
            "missingSkills": required,
            "candidateName": parsed.get("name") or "",
            "reason": "No text could be extracted from the resume PDF.",
        }

    sim_raw = compute_similarity(job_text, resume_text) if job_text else 0.0
    similarity = max(0.0, min(1.0, float(sim_raw)))

    skill_ratio, matched_skills, missing_skills = _skills_overlap(
        required, candidate_skills
    )

    if not required:
        combined_100 = similarity * 100.0
    else:
        combined_100 = (
            _SIMILARITY_WEIGHT * similarity + _SKILL_WEIGHT * skill_ratio
        ) * 100.0

    shortlisted = combined_100 >= _SHORTLIST_THRESHOLD

    return {
        "shortlisted": shortlisted,
        "score": round(combined_100, 2),
        "similarity": round(similarity, 4),
        "skillsMatchRatio": round(skill_ratio, 4),
        "matchedSkills": matched_skills,
        "missingSkills": missing_skills,
        "candidateName": parsed.get("name") or "",
    }
