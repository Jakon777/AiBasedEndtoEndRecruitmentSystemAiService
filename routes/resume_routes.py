from fastapi import APIRouter, UploadFile, File
import shutil, os
from core.resume_parser import parse_resume
from core.embedding_engine import generate_embedding

router=APIRouter(prefix="/resume")

UPLOAD_FOLDER="uploads"
os.makedirs(UPLOAD_FOLDER,exist_ok=True)

@router.post("/parse")
async def parse(file:UploadFile=File(...)):
    path=os.path.join(UPLOAD_FOLDER,file.filename)
    with open(path,"wb") as buffer:
        shutil.copyfileobj(file.file,buffer)
    data=parse_resume(path)
    data["embedding"]=generate_embedding(data["raw_text"])
    return data
