import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Project root — folder containing pyproject.toml
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    
    # ── Folder Paths ──────────────────────────────────────
    UPLOAD_FOLDER: str = str(ROOT_DIR / "uploads")
    OUTPUT_FOLDER: str = str(ROOT_DIR / "output")
    TRANSCRIPT_FOLDER: str = str(ROOT_DIR / "data" / "transcripts")
    LOG_FOLDER: str = str(ROOT_DIR / "logs")
    STATIC_FOLDER: str = str(ROOT_DIR / "static")

    # ── Audio Settings ────────────────────────────────────
    CHUNK_DURATION_MS: int = 5000       # how often browser sends audio chunk
    SAMPLE_RATE: int = 16000            # whisper expects 16khz
    AUDIO_FORMAT: str = "wav"           # format after conversion
    MAX_AUDIO_SIZE_MB: int = 25         # max upload size

    # ── Whisper / Transcription ───────────────────────────
    WHISPER_MODEL: str = "whisper-large-v3"         # base/small/medium
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"  # most efficient on cpu
    WHISPER_LANGUAGE: str = "en"

    # ── LLM / Summary ────────────────────────────────────
    LLM_PROVIDER: str = "groq"          # groq or ollama
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # ── App Settings ──────────────────────────────────────
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"


# Single instance used across entire app
settings = Settings()

# Ensure all folders exist on startup
for folder in [
    settings.UPLOAD_FOLDER,
    settings.OUTPUT_FOLDER,
    settings.TRANSCRIPT_FOLDER,
    settings.LOG_FOLDER,
]:
    os.makedirs(folder, exist_ok=True)