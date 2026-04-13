import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from core.cron_jobs import start_cron_scheduler, stop_cron_scheduler
from middleware.request_logging import RequestLoggingMiddleware
from routes.resume_routes import router as resume_router
from routes.embedding_routes import router as embedding_router
from routes.test_routes import router as test_router
from routes.evaluation_routes import router as evaluation_router
from routes.scoring_routes import router as scoring_router
from routes.shortlist_routes import router as shortlist_router
# ✅ NEW: Interview routes
from routes.interview_routes import router as interview_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ai_hr.main")

_cron_stop: Optional[asyncio.Event] = None
_cron_task: Optional[asyncio.Task] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _cron_stop, _cron_task
    _cron_stop, _cron_task = start_cron_scheduler()
    log.info("application startup")
    yield
    log.info("application shutdown")
    if _cron_stop is not None and _cron_task is not None:
        await stop_cron_scheduler(_cron_stop, _cron_task)


app = FastAPI(
    title="AI Hiring Service",
    description="Microservice for Resume Parsing, Embedding, Evaluation and Scoring",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLoggingMiddleware)

app.include_router(resume_router)
app.include_router(embedding_router)
app.include_router(test_router)
app.include_router(evaluation_router)
app.include_router(scoring_router)
app.include_router(shortlist_router)
# ✅ NEW: Interview Route
app.include_router(interview_router)


@app.get("/")
def root():
    return {
        "message": "AI Hiring Service Running",
        "docs": "/docs",
    }
