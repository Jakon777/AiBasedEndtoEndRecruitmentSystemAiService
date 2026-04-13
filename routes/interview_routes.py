from fastapi import APIRouter
from pydantic import BaseModel

from core.interview_engine import start_interview, process_answer

router = APIRouter(prefix="/interview", tags=["Interview"])


class StartInterviewRequest(BaseModel):
    candidate_id: str
    job_description: str


class AnswerRequest(BaseModel):
    session_id: str
    answer: str


@router.post("/start")
def start(req: StartInterviewRequest):
    session_id, first_question = start_interview(
        req.candidate_id, req.job_description
    )

    return {
        "session_id": session_id,
        "question": first_question,
    }


@router.post("/answer")
def answer(req: AnswerRequest):
    return process_answer(req.session_id, req.answer)