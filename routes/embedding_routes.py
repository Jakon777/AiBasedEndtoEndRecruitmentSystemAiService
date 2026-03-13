from fastapi import APIRouter
from pydantic import BaseModel
from core.embedding_engine import compute_similarity

router=APIRouter(prefix="/embedding")

class SimilarityRequest(BaseModel):
    text1:str
    text2:str

@router.post("/similarity")
def similarity(req:SimilarityRequest):
    return {"score":compute_similarity(req.text1,req.text2)}
