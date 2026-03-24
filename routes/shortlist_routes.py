import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from core.resume_parser import parse_resume
from core.shortlist_engine import evaluate_shortlist
from pydantic import BaseModel, ConfigDict, Field, model_validator

router = APIRouter(prefix="/shortlist", tags=["Shortlist"])


class JobPostingPayload(BaseModel):
    """Subset of Mongo job document; extra fields are ignored."""

    model_config = ConfigDict(extra="ignore")

    title: Optional[str] = None
    description: str = ""
    skillsRequired: list[str] = Field(default_factory=list)
    experienceRequired: Optional[float] = None
    profile: Optional[str] = None
    jobType: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def coerce_mongo_dates(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Drop Mongo-style wrappers so validation does not fail on unknown shapes
            return {k: v for k, v in data.items() if not k.startswith("$")}
        return data


UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _compute_ats_score_from_resume_text(parsed: dict[str, Any], full_text: str) -> int:
    """
    Compute a basic ATS-style integer score (0-100) from resume quality signals.
    """
    text = (full_text or "").strip()
    if not text:
        return 0

    score = 0

    # Contact completeness: email + phone
    emails = parsed.get("email") or []
    phone = (parsed.get("phone") or "").strip()
    if emails:
        score += 10
    if phone:
        score += 10

    # Candidate name detected
    name = (parsed.get("name") or "").strip()
    if name:
        score += 10

    # Skills richness from extracted skill list
    skills = parsed.get("skills") or []
    score += min(35, len(skills) * 5)

    # Resume text length quality (caps at 25 points around 2000 chars)
    length_score = min(25, int((len(text) / 2000) * 25))
    score += length_score

    # Section coverage: experience, education, projects, summary, certifications
    section_terms = [
        "experience",
        "education",
        "project",
        "summary",
        "certification",
    ]
    matched_sections = sum(
        1 for term in section_terms if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE)
    )
    score += min(10, matched_sections * 2)

    return max(0, min(100, int(score)))


def _build_ats_feedback(parsed: dict[str, Any], full_text: str, ats_score: int) -> dict[str, Any]:
    """
    Generate actionable feedback describing where the candidate should improve.
    """
    text = (full_text or "").strip()
    skills = parsed.get("skills") or []
    emails = parsed.get("email") or []
    phone = (parsed.get("phone") or "").strip()
    name = (parsed.get("name") or "").strip()

    improvement_areas: list[str] = []
    strengths: list[str] = []

    if not name:
        improvement_areas.append("Add a clear full name at the top of the resume.")
    else:
        strengths.append("Candidate name is clearly detectable.")

    if not emails:
        improvement_areas.append("Add a professional email address.")
    else:
        strengths.append("Email contact is present.")

    if not phone:
        improvement_areas.append("Add a valid phone number for recruiter outreach.")
    else:
        strengths.append("Phone number is present.")

    if len(skills) < 5:
        improvement_areas.append(
            "Add a stronger technical skills section with relevant tools and technologies."
        )
    else:
        strengths.append("Skills section contains multiple relevant keywords.")

    section_checks = {
        "experience": "Add or improve the work experience section with measurable impact.",
        "education": "Add education details (degree, institute, graduation year).",
        "project": "Add project details with responsibilities and outcomes.",
        "summary": "Add a short professional summary aligned with target roles.",
        "certification": "Add certifications if available to strengthen profile credibility.",
    }

    for section_key, suggestion in section_checks.items():
        if not re.search(rf"\b{re.escape(section_key)}\b", text, re.IGNORECASE):
            improvement_areas.append(suggestion)

    if len(text) < 700:
        improvement_areas.append("Resume content is too short; add more role-relevant detail.")
    elif len(text) >= 1400:
        strengths.append("Resume includes substantial descriptive content.")

    if ats_score >= 80:
        level = "strong"
    elif ats_score >= 60:
        level = "moderate"
    else:
        level = "needs_improvement"

    return {
        "level": level,
        "strengths": strengths,
        "improvementAreas": improvement_areas,
    }


@router.post("/ats-score")
async def ats_score(resume: UploadFile = File(..., description="Candidate resume PDF")):
    """
    Upload a resume and return an ATS-like integer score.
    """
    suffix = Path(resume.filename or "").suffix or ".pdf"
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    path = os.path.join(UPLOAD_FOLDER, safe_name)

    try:
        with open(path, "wb") as buffer:
            shutil.copyfileobj(resume.file, buffer)

        parsed = parse_resume(path, include_full_text=True)
        full_text = str(parsed.get("full_text") or "")
        ats_score_value = _compute_ats_score_from_resume_text(parsed, full_text)
        feedback = _build_ats_feedback(parsed, full_text, ats_score_value)
        return {
            "atsScore": int(ats_score_value),
            "feedback": feedback,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse resume: {e}") from e
    finally:
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass


@router.post("/evaluate")
async def shortlist_candidate(
    job: str = Form(
        ...,
        description='Job posting JSON, e.g. {"title":"...","description":"...","skillsRequired":["Java"]}',
    ),
    resume: UploadFile = File(..., description="Candidate resume PDF"),
):
    """
    Upload a resume PDF plus job posting metadata; returns whether the candidate
    is shortlisted (boolean) and supporting scores.
    """
    try:
        raw = json.loads(job)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid job JSON: {e}") from e

    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="job must be a JSON object")

    try:
        job_model = JobPostingPayload.model_validate(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid job payload: {e}") from e

    job_payload = job_model.model_dump()

    suffix = Path(resume.filename or "").suffix or ".pdf"
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    path = os.path.join(UPLOAD_FOLDER, safe_name)

    try:
        with open(path, "wb") as buffer:
            shutil.copyfileobj(resume.file, buffer)

        result = evaluate_shortlist(job_payload, path)
        return result
    finally:
        if os.path.isfile(path):
            try:
                os.remove(path)
            except OSError:
                pass
