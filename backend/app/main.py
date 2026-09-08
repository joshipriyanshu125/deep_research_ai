import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config.settings import settings
from app.database.mongodb import connect_to_mongo, close_mongo_connection
from app.workers.research_worker import research_worker
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

# API Routers
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.research import router as research_router
from app.api.reports import router as reports_router
from app.api.sources import router as sources_router
from app.api.history import router as history_router
from app.api.admin import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    worker_task = asyncio.create_task(research_worker.start_worker())
    yield
    # Shutdown
    research_worker.is_running = False
    worker_task.cancel()
    await close_mongo_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Autonomous Deep Research AI Backend Platform",
    lifespan=lifespan
)

# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=300, window_seconds=60)

# Include Routers with API Prefix
api_prefix = settings.API_V1_STR
app.include_router(auth_router, prefix=api_prefix)
app.include_router(users_router, prefix=api_prefix)
app.include_router(research_router, prefix=api_prefix)
app.include_router(reports_router, prefix=api_prefix)
app.include_router(sources_router, prefix=api_prefix)
app.include_router(history_router, prefix=api_prefix)
app.include_router(admin_router, prefix=api_prefix)


@app.get("/health")
@app.get(f"{api_prefix}/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT
    }


# Mount Static Frontend Files
frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend"))
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG)
