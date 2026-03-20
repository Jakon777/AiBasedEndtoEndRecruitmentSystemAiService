from fastapi import APIRouter
from pydantic import BaseModel
from core.test_generator import generate_test

router=APIRouter(prefix="/test")

class TestRequest(BaseModel):
    skills:list
    difficulty:str="Intermediate"
    job_desc:str

@router.post("/generate")
def generate(req:TestRequest):
    return generate_test(req.skills, req.job_desc, req.difficulty)
