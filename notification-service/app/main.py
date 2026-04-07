from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes.notify import router
from app.config import SERVICE_PORT
from app.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MSRIT Notification Service...")
    init_db()
    logger.info("alert_logs table ready.")
    yield
    logger.info("Shutting down Notification Service.")


app = FastAPI(
    title="MSRIT Notification Service",
    description=(
        "Phase 3 — Standalone email notification microservice. "
        "Receives manual alert requests from the backend, sends HTML emails "
        "to teachers, and logs all activity to PostgreSQL."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=SERVICE_PORT, reload=True)
