import sys
import json
import asyncio
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.services.audio_processor import convert_webm_to_wav, cleanup_chunk
from app.services.transcription import transcribe_chunk
from app.services.summary import generate_summary, generate_progressive_summary
from app.utils.logger import get_logger
from app.core.exceptions import (
    AudioProcessingException,
    TranscriptionException,
    SummaryGenerationException
)

logger = get_logger(__name__)
router = APIRouter()

# progressive summary every 10 minutes
PROGRESSIVE_SUMMARY_INTERVAL = 600  # seconds


class MeetingSession:
    """
    Holds all state for one meeting session.
    Created when WebSocket connects, destroyed when it closes.
    """
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.transcript_chunks = []      # list of transcribed text chunks
        self.chunk_count = 0
        self.started_at = datetime.now()
        self.last_summary_at = datetime.now()
        self.is_recording = True

    @property
    def full_transcript(self) -> str:
        """Returns complete transcript as single string."""
        return " ".join(self.transcript_chunks)

    @property
    def word_count(self) -> int:
        return len(self.full_transcript.split())

    @property
    def minutes_since_last_summary(self) -> float:
        delta = datetime.now() - self.last_summary_at
        return delta.total_seconds() / 60


@router.websocket("/ws/audio")
async def audio_websocket(websocket: WebSocket, session_id: str):
    """
    Main WebSocket endpoint for live meeting audio.

    Handles:
    - Real-time audio chunk processing
    - Live transcript streaming
    - Progressive summaries every 10 minutes
    - Q&A questions from user
    - Stop signal and final summary trigger
    """
    await websocket.accept()
    session = MeetingSession(session_id)

    logger.info(f"Session {session_id} started")

    # send confirmation to frontend
    await _send(websocket, {
        "type": "status",
        "message": "Recording started",
        "session_id": session_id
    })

    try:
        while True:
            # receive either bytes (audio) or text (control messages)
            message = await websocket.receive()

            # ── Audio Chunk ──────────────────────────────────
            if "bytes" in message and message["bytes"]:
                await _handle_audio_chunk(
                    websocket, session, message["bytes"]
                )

            # ── Text Control Messages ────────────────────────
            elif "text" in message and message["text"]:
                data = json.loads(message["text"])
                await _handle_text_message(websocket, session, data)

    except WebSocketDisconnect:
        logger.info(f"Session {session_id} disconnected")

    except Exception as e:
        logger.error(f"Session {session_id} error: {str(e)}")
        await _send(websocket, {
            "type": "error",
            "message": "Unexpected error occurred",
            "stage": "session"
        })

    finally:
        logger.info(
            f"Session {session_id} ended — "
            f"chunks: {session.chunk_count}, "
            f"words: {session.word_count}"
        )


async def _handle_audio_chunk(
    websocket: WebSocket,
    session: MeetingSession,
    audio_bytes: bytes
):
    """
    Processes one audio chunk:
    1. Convert webm → wav
    2. Transcribe wav → text
    3. Clean up temp file
    4. Send transcript to frontend
    5. Check if progressive summary is due
    """
    session.chunk_count += 1
    chunk_id = f"{session.session_id}_{session.chunk_count}"

    logger.info(f"Chunk {chunk_id} received — {len(audio_bytes)} bytes")

    wav_path = None

    try:
        # step 1 — convert audio format
        wav_path = convert_webm_to_wav(audio_bytes, chunk_id)

        # step 2 — transcribe
        text = transcribe_chunk(wav_path)

        if not text or len(text.strip()) == 0:
            logger.warning(f"Chunk {chunk_id} produced empty transcript — skipping")
            return

        # step 3 — add to session transcript
        session.transcript_chunks.append(text.strip())

        logger.info(f"Chunk {chunk_id} transcribed: '{text[:50]}...'")

        # step 4 — send transcript to frontend
        await _send(websocket, {
            "type": "transcript",
            "text": text.strip(),
            "chunk_id": session.chunk_count,
            "total_words": session.word_count
        })

        # step 5 — check if progressive summary is due
        if (session.minutes_since_last_summary >= 10
                and session.word_count > 100):
            await _send_progressive_summary(websocket, session)

    except AudioProcessingException as e:
        logger.error(f"Audio processing failed for chunk {chunk_id}: {e}")
        await _send(websocket, {
            "type": "error",
            "message": "Failed to process audio chunk",
            "stage": "audio_processing",
            "chunk_id": session.chunk_count
        })

    except TranscriptionException as e:
        logger.error(f"Transcription failed for chunk {chunk_id}: {e}")
        await _send(websocket, {
            "type": "error",
            "message": "Failed to transcribe audio",
            "stage": "transcription",
            "chunk_id": session.chunk_count
        })

    finally:
        # always clean up temp wav file
        if wav_path:
            cleanup_chunk(wav_path)


async def _handle_text_message(
    websocket: WebSocket,
    session: MeetingSession,
    data: dict
):
    """
    Handles control messages from frontend:
    - stop: user clicked stop recording
    - generate_summary: user wants final summary
    - question: user asking Q&A question
    """
    message_type = data.get("type")

    # ── Stop Recording ───────────────────────────────
    if message_type == "stop":
        session.is_recording = False
        logger.info(f"Session {session.session_id} stopped by user")

        await _send(websocket, {
            "type": "status",
            "message": "Recording stopped",
            "total_words": session.word_count,
            "total_chunks": session.chunk_count
        })

    # ── Generate Final Summary ───────────────────────
    elif message_type == "generate_summary":
        await _send_final_summary(websocket, session)

    # ── Q&A Question ─────────────────────────────────
    elif message_type == "question":
        question = data.get("text", "").strip()
        if question:
            await _handle_question(websocket, session, question)
        else:
            await _send(websocket, {
                "type": "error",
                "message": "Empty question received"
            })

    else:
        logger.warning(f"Unknown message type: {message_type}")


async def _send_progressive_summary(
    websocket: WebSocket,
    session: MeetingSession
):
    """Generates and sends a progressive summary mid-meeting."""
    logger.info(f"Generating progressive summary for session {session.session_id}")

    try:
        result = generate_progressive_summary(session.full_transcript)
        session.last_summary_at = datetime.now()

        await _send(websocket, {
            "type": "progressive_summary",
            "text": result["summary"],
            "tokens_used": result.get("tokens_used", 0),
            "word_count": session.word_count
        })

    except SummaryGenerationException as e:
        logger.error(f"Progressive summary failed: {e}")
        # non critical — don't send error to user
        # meeting continues normally


async def _send_final_summary(
    websocket: WebSocket,
    session: MeetingSession
):
    """Generates and sends the final structured summary."""
    logger.info(f"Generating final summary for session {session.session_id}")

    if session.word_count < 50:
        await _send(websocket, {
            "type": "error",
            "message": "Not enough transcript to generate summary",
            "stage": "final_summary"
        })
        return

    # notify frontend that summary is being generated
    await _send(websocket, {
        "type": "status",
        "message": "Generating final summary..."
    })

    try:
        result = generate_summary(session.full_transcript)

        await _send(websocket, {
            "type": "final_summary",
            "text": result["summary"],
            "model": result["model"],
            "tokens_used": result.get("tokens_used", 0),
            "strategy": result.get("strategy", "direct"),
            "duration_minutes": (
                datetime.now() - session.started_at
            ).total_seconds() / 60
        })

        logger.info(f"Final summary sent for session {session.session_id}")

    except SummaryGenerationException as e:
        logger.error(f"Final summary failed: {e}")
        await _send(websocket, {
            "type": "error",
            "message": "Failed to generate summary",
            "stage": "final_summary"
        })


async def _handle_question(
    websocket: WebSocket,
    session: MeetingSession,
    question: str
):
    """
    Handles Q&A questions about the meeting transcript.
    RAG pipeline will be plugged in here in next step.
    For now returns a placeholder.
    """
    logger.info(f"Question received: '{question}'")

    # placeholder — RAG pipeline plugged in next step
    await _send(websocket, {
        "type": "qa_answer",
        "question": question,
        "text": "RAG pipeline coming soon",
    })


async def _send(websocket: WebSocket, data: dict):
    """
    Helper to send JSON messages to frontend.
    Single place to handle send errors.
    """
    try:
        await websocket.send_json(data)
    except Exception as e:
        logger.error(f"Failed to send message: {e}")