"""
Genomic Intelligence System — FastAPI Application Entry Point
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import init_db
from app.api.routes.ingest import router as ingest_router
from app.api.routes.accession import router as accession_router
from app.api.routes import auth
from app.api.routes import admin as admin_routes

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── App Lifespan ───────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Genomic Intelligence System...")
    await init_db()
    logger.info("Database tables initialized.")
    yield
    logger.info("Shutting down Genomic Intelligence System.")


# ── App Factory ────────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Backend API for the Genomic Intelligence System — "
        "DENR Region VIII Metagenomic Data Ingestion & Validation Engine"
    ),
    lifespan=lifespan,
)

# ── Rate Limiting ──────────────────────────────────────────────────────────────
app.state.limiter = auth.limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS — configured for secure local dev and production
backend_cors_origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://localhost:3000",
]
if settings.DEBUG:
    backend_cors_origins.extend(["*"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=backend_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(auth.router, prefix="/api/v1")
app.include_router(admin_routes.router, prefix="/api/v1")
app.include_router(ingest_router)
app.include_router(accession_router)


# ── Health Check ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "ok", "system": settings.APP_NAME, "version": settings.APP_VERSION}
