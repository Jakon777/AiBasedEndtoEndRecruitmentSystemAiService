# from fastapi import FastAPI
# from routes import resume_routes, embedding_routes, test_routes, evaluation_routes, scoring_routes

# app=FastAPI()

# app.include_router(resume_routes.router)
# app.include_router(embedding_routes.router)
# app.include_router(test_routes.router)
# app.include_router(evaluation_routes.router)
# app.include_router(scoring_routes.router)



from fastapi import FastAPI

# Import routers explicitly
from routes.resume_routes import router as resume_router
from routes.embedding_routes import router as embedding_router
from routes.test_routes import router as test_router
from routes.evaluation_routes import router as evaluation_router
from routes.scoring_routes import router as scoring_router
from routes.shortlist_routes import router as shortlist_router

app = FastAPI(
    title="AI Hiring Service",
    description="Microservice for Resume Parsing, Embedding, Evaluation and Scoring",
    version="1.0.0"
)

# Register routers
app.include_router(resume_router)
app.include_router(embedding_router)
app.include_router(test_router)
app.include_router(evaluation_router)
app.include_router(scoring_router)
app.include_router(shortlist_router)


@app.get("/")
def root():
    return {
        "message": "AI Hiring Service Running",
        "docs": "/docs"
    }