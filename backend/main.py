"""
FastAPI application entry point.

Start with:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import init_db
from backend.routes.backtests import router as backtests_router
from backend.routes.strategies import router as strategies_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialise the database and seed default strategies on first run."""
    logger.info("Initialising database …")
    init_db()
    logger.info("Database ready.")
    yield


app = FastAPI(
    title="Quant Research Dashboard API",
    lifespan=lifespan,
    description=(
        "REST API powering the Quantitative Research Dashboard. "
        "Provides endpoints for running Moving Average Crossover backtests, "
        "retrieving historical runs, and listing available strategies."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS — allow the Dash frontend running on port 8050
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8050"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(backtests_router, prefix="/api")
app.include_router(strategies_router, prefix="/api")

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Simple liveness probe."""
    return {"status": "ok"}
