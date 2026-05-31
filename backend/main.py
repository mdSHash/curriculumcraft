"""MathCraft API — FastAPI application entry point."""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from database import create_tables
import models  # noqa: F401 — registers all ORM models with Base before create_tables()
from routers.books import router as books_router
from routers.exams import router as exams_router
from routers.moe_library import router as moe_library_router
from routers.workbooks import router as workbooks_router
from utils.file_utils import ensure_directories

# ─── Logging Configuration ─────────────────────────────────────────────────────
# Configure root logger to output all app logs to console (stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
# Reduce noise from third-party libraries
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown events."""
    # Startup
    logger.info("MathCraft API starting up...")
    ensure_directories()
    create_tables()
    logger.info("MathCraft API ready.")
    yield
    # Shutdown (nothing to clean up currently)
    logger.info("MathCraft API shutting down.")


settings = get_settings()

app = FastAPI(
    title="MathCraft API",
    version="1.0.0",
    description="Backend API for MathCraft — AI-powered math workbook generator",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(books_router, prefix="/api")
app.include_router(exams_router, prefix="/api")
app.include_router(moe_library_router, prefix="/api")
app.include_router(workbooks_router, prefix="/api")


@app.get("/api/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}
