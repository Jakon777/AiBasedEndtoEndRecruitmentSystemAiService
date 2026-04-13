import json
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from core.interview_engine import process_answer, start_interview
from core.resume_parser import parse_resume
from routes.shortlist_routes import _remove_file_quiet, _save_upload_temp

router = APIRouter(prefix="/interview", tags=["Interview"])


class AnswerRequest(BaseModel):
    """JSON body for `POST /interview/answer` (unchanged)."""

    session_id: str
    answer: str


@router.post("/start")
async def start(
    job: str = Form(
        ...,
        description="JSON string of the job posting (same shape as Java `JobPostings` / Mongo document).",
    ),
    resume: UploadFile = File(..., description="Resume PDF bytes (e.g. from GridFS)."),
    candidate_id: str = Form(..., description="Candidate identifier."),
    job_posting_id: Optional[str] = Form(None, description="Optional echo of job posting id."),
    job_application_id: Optional[str] = Form(None, description="Optional job application id."),
    resume_id: Optional[str] = Form(None, description="Optional resume / GridFS file id."),
):
    """
    Start an AI interview using the **full job posting** and **resume file** (multipart), same idea as
    reading `resumeBytes` + filename from GridFS on the Java side.

    Returns one first `question` and a `session_id` for `POST /interview/answer`.
    """
    try:
        raw = json.loads(job)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid job JSON: {e}") from e

    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail="job must be a JSON object")

    job_payload = {k: v for k, v in raw.items() if not str(k).startswith("$")}

    path = _save_upload_temp(resume)
    try:
        parsed = parse_resume(path, include_full_text=True)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Could not read resume PDF: {e}",
        ) from e
    finally:
        _remove_file_quiet(path)

    text = str(parsed.get("full_text") or parsed.get("text_for_similarity") or "").strip()
    if not text:
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted from the resume PDF.",
        )

    session_id, first_question = start_interview(
        candidate_id,
        job_payload,
        parsed,
        job_posting_id=job_posting_id,
        job_application_id=job_application_id,
        resume_id=resume_id,
    )

    return {
        "session_id": session_id,
        "question": first_question,
        "candidate_id": candidate_id,
        "job_posting_id": job_posting_id,
        "job_application_id": job_application_id,
        "resume_id": resume_id,
    }


@router.post("/answer")
def answer(req: AnswerRequest):
    return process_answer(req.session_id, req.answer)
