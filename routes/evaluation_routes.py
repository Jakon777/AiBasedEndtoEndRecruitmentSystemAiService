from fastapi import APIRouter
from pydantic import BaseModel
from core.code_evaluator import evaluate_code

router=APIRouter(prefix="/evaluation")

class EvalRequest(BaseModel):
    code:str
    test_cases:list

@router.post("/evaluate")
def evaluate(req:EvalRequest):
    return evaluate_code(req.code,req.test_cases)
