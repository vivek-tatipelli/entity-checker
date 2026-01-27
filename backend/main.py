import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.analyze import router as analyze_router

# --------------------------------------------------
# Logging
# --------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)

# --------------------------------------------------
# App
# --------------------------------------------------

app = FastAPI(
    title="EntityScope – Phase 1",
    description=(
        "Single-page entity and structured data analyzer. "
        "Supports JSON-LD, Microdata, RDFa, SEO signals, and schema suggestions."
    ),
    version="1.0.0"
)

# --------------------------------------------------
# CORS (safe defaults)
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten later if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# Routers
# --------------------------------------------------

app.include_router(
    analyze_router,
    prefix="/api",
    tags=["Analyze"]
)

# --------------------------------------------------
# Health check
# --------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "phase": "1",
        "service": "entityscope"
    }

# --------------------------------------------------
# Startup / Shutdown
# --------------------------------------------------

@app.on_event("startup")
def on_startup():
    logger.info("🚀 EntityScope Phase-1 API started")

@app.on_event("shutdown")
def on_shutdown():
    logger.info("🛑 EntityScope API shutting down")
