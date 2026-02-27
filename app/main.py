import sys
import os
from app.api.audio import audio_websocket
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from app.api.audio import router as audio_router
from app.api.upload import router as upload_router
from app.core.config import settings
from app.utils.logger import get_logger
from app.core.exceptions import ModelLoadException

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs on startup and shutdown.
    Startup: load models, verify folders exist
    Shutdown: cleanup resources
    """
    # ── Startup ──────────────────────────────────────
    logger.info("Starting Meeting Assistant...")
    logger.info(f"Whisper model: {settings.WHISPER_MODEL}")
    logger.info(f"LLM model: {settings.GROQ_MODEL}")
    logger.info(f"Debug mode: {settings.DEBUG}")

    # verify critical folders exist
    for folder in [
        settings.UPLOAD_FOLDER,
        settings.OUTPUT_FOLDER,
        settings.TRANSCRIPT_FOLDER,
        settings.LOG_FOLDER
    ]:
        os.makedirs(folder, exist_ok=True)
        logger.info(f"Folder verified: {folder}")

    # pre-load whisper model at startup
    # so first request isn't slow
    try:
        from app.services.transcription import client
        logger.info("Groq transcription client ready")
    except Exception as e:
        logger.critical(f"Failed to initialize transcription client: {e}")
        raise

    logger.info("Meeting Assistant started successfully")

    yield

    # ── Shutdown ─────────────────────────────────────
    logger.info("Shutting down Meeting Assistant...")


# create FastAPI app
app = FastAPI(
    title="Meeting Assistant",
    description="AI powered meeting assistant with real-time transcription and summarization",
    version="0.1.0",
    lifespan=lifespan
)

# mount static files
app.mount(
    "/static",
    StaticFiles(directory=settings.STATIC_FOLDER),
    name="static"
)

# register routers
app.include_router(audio_router, prefix="/api", tags=["audio"])
app.include_router(upload_router, prefix="/api", tags=["upload"])

app.add_api_websocket_route("/ws/audio", audio_websocket)

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main frontend page."""
    index_path = os.path.join(settings.STATIC_FOLDER, "index.html")
    with open(index_path, "r" , encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Useful for deployment monitoring.
    """
    return {
        "status": "healthy",
        "whisper_model": settings.WHISPER_MODEL,
        "llm_model": settings.GROQ_MODEL
    }