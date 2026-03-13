from fastapi import FastAPI
from routes import resume_routes, embedding_routes, test_routes, evaluation_routes, scoring_routes

app=FastAPI()

app.include_router(resume_routes.router)
app.include_router(embedding_routes.router)
app.include_router(test_routes.router)
app.include_router(evaluation_routes.router)
app.include_router(scoring_routes.router)
