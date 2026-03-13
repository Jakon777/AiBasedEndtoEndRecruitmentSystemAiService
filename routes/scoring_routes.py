from fastapi import APIRouter
from pydantic import BaseModel
from core.scoring_engine import compute_composite

router=APIRouter(prefix="/scoring")

class ScoreRequest(BaseModel):
    similarity:float
    required:list
    candidate:list
    mcq:float
    coding:float

@router.post("/final")
def final_score(req:ScoreRequest):
    return compute_composite(
        req.similarity,
        req.required,
        req.candidate,
        req.mcq,
        req.coding
    )
