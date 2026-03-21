import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

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
