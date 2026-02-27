import sys
import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from werkzeug.utils import secure_filename
from app.services.transcription import transcribe_audio
from app.services.summary import generate_summary
from app.core.config import settings
from app.core.exceptions import (
    TranscriptionException,
    SummaryGenerationException,
    FileProcessingException
)
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# in-memory session store
# replace with database later
session_store = {}

ALLOWED_AUDIO = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg"}
ALLOWED_VIDEO = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
ALLOWED_PDF   = {".pdf"}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Handles file upload — audio, video, or PDF.
    Returns session ID and processing status.
    """
    session_id = str(uuid.uuid4())
    save_path = None

    logger.info(f"Upload received — file: {file.filename}, session: {session_id}")

    try:
        # validate file
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1].lower()

        if ext not in ALLOWED_AUDIO | ALLOWED_VIDEO | ALLOWED_PDF:
            raise FileProcessingException(
                f"Unsupported file type: {ext}", sys
            )

        # save file
        unique_filename = f"{session_id}_{filename}"
        save_path = os.path.join(settings.UPLOAD_FOLDER, unique_filename)

        with open(save_path, "wb") as f:
            content = await file.read()
            f.write(content)

        logger.info(f"File saved: {save_path}")

        # transcribe
        if ext in ALLOWED_PDF:
            # PDF handling — plug in your existing pdf_extractor here
            raise FileProcessingException(
                "PDF support coming soon", sys
            )
        else:
            result = transcribe_audio(save_path)
            transcript = result["text"]

        logger.info(f"Transcription complete — words: {len(transcript.split())}")

        # generate summary
        summary_result = generate_summary(transcript)

        # store session
        session_store[session_id] = {
            "file": save_path,
            "transcript": transcript,
            "summary": summary_result["summary"],
            "session_id": session_id
        }

        logger.info(f"Upload processed successfully — session: {session_id}")

        return {
            "status": "completed",
            "session_id": session_id,
            "summary": summary_result["summary"],
            "words_transcribed": len(transcript.split()),
            "model_used": summary_result["model"],
            "strategy": summary_result.get("strategy", "direct")
        }

    except FileProcessingException as e:
        logger.error(f"File processing failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except TranscriptionException as e:
        logger.error(f"Transcription failed: {e}")
        raise HTTPException(status_code=500, detail="Transcription failed")

    except SummaryGenerationException as e:
        logger.error(f"Summary generation failed: {e}")
        raise HTTPException(status_code=500, detail="Summary generation failed")

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    finally:
        # clean up uploaded file after processing
        if save_path and os.path.exists(save_path):
            try:
                os.remove(save_path)
                logger.debug(f"Cleaned up: {save_path}")
            except Exception:
                pass


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Returns stored session data."""
    if session_id not in session_store:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_store[session_id]


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Deletes session data — privacy compliance."""
    if session_id not in session_store:
        raise HTTPException(status_code=404, detail="Session not found")
    del session_store[session_id]
    logger.info(f"Session {session_id} deleted")
    return {"status": "deleted", "session_id": session_id}