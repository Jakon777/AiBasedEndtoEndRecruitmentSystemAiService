import json
import os
import re
import shutil
import uuid
import base64
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


class BatchShortlistEvaluateItem(BaseModel):
    """
    JSON item for /shortlist/evaluate/batch.

    Resume content must be base64-encoded PDF bytes. Any provided ids are echoed back.
    """

    model_config = ConfigDict(extra="ignore")

    candidateId: Optional[str] = None
    jobPostingId: Optional[str] = None
    jobApplicationId: Optional[str] = None
    resumeId: Optional[str] = None

    job: dict[str, Any] | str
    resumeBase64: str = Field(..., min_length=1, description="Base64-encoded PDF bytes")
    resumeFileName: Optional[str] = Field(default="resume.pdf", description="Optional filename hint")


class BatchShortlistEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    items: list[BatchShortlistEvaluateItem] = Field(default_factory=list)


UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def _save_upload_temp(resume: UploadFile) -> str:
    """Write upload to a temp file; caller must delete the path when done."""
    suffix = Path(resume.filename or "").suffix or ".pdf"
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    path = os.path.join(UPLOAD_FOLDER, safe_name)
    with open(path, "wb") as buffer:
        shutil.copyfileobj(resume.file, buffer)
    return path


def _save_bytes_temp(data: bytes, filename_hint: str = "resume.pdf") -> str:
    """Write bytes to a temp file; caller must delete the path when done."""
    suffix = Path(filename_hint or "").suffix or ".pdf"
    safe_name = f"{uuid.uuid4().hex}{suffix}"
    path = os.path.join(UPLOAD_FOLDER, safe_name)
    with open(path, "wb") as buffer:
        buffer.write(data)
    return path


def _remove_file_quiet(path: str) -> None:
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _evaluate_shortlist_safe(job_payload: dict[str, Any], path: str) -> dict[str, Any]:
    """Run shortlist evaluation; never raises — callers batching many resumes rely on this."""
    try:
        out = dict(evaluate_shortlist(job_payload, path))
        out["ok"] = True
        return out
    except Exception as e:
        required = [str(s) for s in (job_payload.get("skillsRequired") or [])]
        return {
            "ok": False,
            "error": str(e),
            "shortlisted": False,
            "score": 0.0,
            "similarity": 0.0,
            "skillsMatchRatio": 0.0,
            "matchedSkills": [],
            "missingSkills": required,
            "candidateName": "",
            "reason": f"Evaluation failed: {e}",
        }


def _ats_for_path(path: str) -> dict[str, Any]:
    """Parse resume and compute ATS score + feedback; never raises."""
    try:
        parsed = parse_resume(path, include_full_text=True)
        full_text = str(parsed.get("full_text") or "")
        ats_score_value = _compute_ats_score_from_resume_text(parsed, full_text)
        feedback = _build_ats_feedback(parsed, full_text, ats_score_value)
        return {
            "ok": True,
            "atsScore": int(ats_score_value),
            "feedback": feedback,
        }
    except Exception as e:
        return {
            "ok": False,
            "atsScore": 0,
            "feedback": {
                "level": "needs_improvement",
                "strengths": [],
                "improvementAreas": ["Could not read this resume file reliably."],
                "error": str(e),
            },
        }


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
    if not isinstance(skills, list):
        skills = []
    emails = parsed.get("email") or []
    if not isinstance(emails, list):
        emails = []
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
    Always returns 200; check `ok` for per-file success (parsing errors do not raise).
    """
    path = _save_upload_temp(resume)
    try:
        return _ats_for_path(path)
    finally:
        _remove_file_quiet(path)


@router.post("/ats-score-batch")
async def ats_score_batch(
    resumes: list[UploadFile] = File(
        ...,
        description="One or more resume PDFs; each is scored independently.",
    ),
):
    """
    Score many resumes in one request. Failures on one file do not stop the rest.
    """
    if not resumes:
        raise HTTPException(status_code=400, detail="Provide at least one resume file.")

    results: list[dict[str, Any]] = []
    succeeded = 0
    failed = 0

    for i, resume in enumerate(resumes):
        path = ""
        try:
            path = _save_upload_temp(resume)
            item = _ats_for_path(path)
            if item.get("ok"):
                succeeded += 1
            else:
                failed += 1
            results.append(
                {
                    "index": i,
                    "fileName": resume.filename or "",
                    **item,
                }
            )
        except Exception as e:
            failed += 1
            results.append(
                {
                    "index": i,
                    "fileName": resume.filename or "",
                    "ok": False,
                    "atsScore": 0,
                    "feedback": {
                        "level": "needs_improvement",
                        "strengths": [],
                        "improvementAreas": [],
                        "error": str(e),
                    },
                }
            )
        finally:
            _remove_file_quiet(path)

    return {
        "total": len(resumes),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }


@router.post("/evaluate/batch")
async def shortlist_evaluate_batch_json(payload: BatchShortlistEvaluateRequest):
    """
    JSON batch endpoint for clients that POST application/json to:
      /shortlist/evaluate/batch

    Response is a flat list in the same order as `payload.items`.
    """
    if payload is None or not payload.items:
        return []

    out: list[dict[str, Any]] = []
    for item in payload.items:
        path = ""
        try:
            raw_job: dict[str, Any]
            if isinstance(item.job, str):
                try:
                    decoded = json.loads(item.job)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid job JSON string: {e}") from e
                if not isinstance(decoded, dict):
                    raise ValueError("job JSON string must decode to an object")
                raw_job = decoded
            elif isinstance(item.job, dict):
                raw_job = item.job
            else:
                raise ValueError("job must be a JSON object or JSON string")

            job_model = JobPostingPayload.model_validate(raw_job)
            job_payload = job_model.model_dump()

            b64 = (item.resumeBase64 or "").strip()
            try:
                pdf_bytes = base64.b64decode(b64, validate=True)
            except Exception as e:
                raise ValueError(f"Invalid resumeBase64: {e}") from e

            if not pdf_bytes:
                raise ValueError("resumeBase64 decoded to empty bytes")

            path = _save_bytes_temp(pdf_bytes, item.resumeFileName or "resume.pdf")
            result = _evaluate_shortlist_safe(job_payload, path)

            out.append(
                {
                    "candidateId": item.candidateId,
                    "jobPostingId": item.jobPostingId,
                    "jobApplicationId": item.jobApplicationId,
                    "resumeId": item.resumeId,
                    **result,
                }
            )
        except Exception as e:
            required: list[str] = []
            if isinstance(item.job, dict):
                required = [str(s) for s in (item.job.get("skillsRequired") or [])]
            elif isinstance(item.job, str):
                try:
                    parsed = json.loads(item.job)
                    if isinstance(parsed, dict):
                        required = [str(s) for s in (parsed.get("skillsRequired") or [])]
                except Exception:
                    pass

            out.append(
                {
                    "candidateId": item.candidateId,
                    "jobPostingId": item.jobPostingId,
                    "jobApplicationId": item.jobApplicationId,
                    "resumeId": item.resumeId,
                    "ok": False,
                    "error": str(e),
                    "shortlisted": False,
                    "score": 0.0,
                    "similarity": 0.0,
                    "skillsMatchRatio": 0.0,
                    "matchedSkills": [],
                    "missingSkills": required,
                    "candidateName": "",
                    "reason": f"Evaluation failed: {e}",
                }
            )
        finally:
            _remove_file_quiet(path)

    return out


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
    Check `ok`; if False, `error` explains the failure without aborting client batch flows.
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

    path = _save_upload_temp(resume)
    try:
        return _evaluate_shortlist_safe(job_payload, path)
    finally:
        _remove_file_quiet(path)


@router.post("/evaluate-batch")
async def shortlist_batch(
    job: str = Form(
        ...,
        description='Job posting JSON, e.g. {"title":"...","description":"...","skillsRequired":["Java"]}',
    ),
    resumes: list[UploadFile] = File(
        ...,
        description="One or more resume PDFs; each is evaluated independently against the same job.",
    ),
):
    """
    Evaluate many applications for one job in one request.
    A corrupt or unreadable resume does not stop scoring for the others.
    """
    if not resumes:
        raise HTTPException(status_code=400, detail="Provide at least one resume file.")

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

    results: list[dict[str, Any]] = []
    succeeded = 0
    failed = 0

    for i, resume in enumerate(resumes):
        path = ""
        try:
            path = _save_upload_temp(resume)
            data = _evaluate_shortlist_safe(job_payload, path)
            if data.get("ok"):
                succeeded += 1
            else:
                failed += 1
            results.append(
                {
                    "index": i,
                    "fileName": resume.filename or "",
                    "result": data,
                }
            )
        except Exception as e:
            failed += 1
            required = [str(s) for s in (job_payload.get("skillsRequired") or [])]
            results.append(
                {
                    "index": i,
                    "fileName": resume.filename or "",
                    "result": {
                        "ok": False,
                        "error": str(e),
                        "shortlisted": False,
                        "score": 0.0,
                        "similarity": 0.0,
                        "skillsMatchRatio": 0.0,
                        "matchedSkills": [],
                        "missingSkills": required,
                        "candidateName": "",
                        "reason": f"Evaluation failed: {e}",
                    },
                }
            )
        finally:
            _remove_file_quiet(path)

    return {
        "total": len(resumes),
        "succeeded": succeeded,
        "failed": failed,
        "results": results,
    }
