import sys
import json
from app.services.rag import MeetingVectorStore, TranscriptIngestionPipeline, run_agent
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

PROGRESSIVE_SUMMARY_INTERVAL = 600


class MeetingSession:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.transcript_chunks = []
        self.chunk_count = 0
        self.started_at = datetime.now()
        self.last_summary_at = datetime.now()
        self.is_recording = True
        # ── RAG: one store + pipeline per session ──────────────────────────
        self.vector_store = MeetingVectorStore(session_id)
        self.pipeline = TranscriptIngestionPipeline(self.vector_store)

    @property
    def full_transcript(self) -> str:
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
    await websocket.accept()
    session = MeetingSession(session_id)

    # ── RAG: start ingestion worker when session begins ────────────────────
    session.pipeline.start()

    logger.info(f"Session {session_id} started")

    await _send(websocket, {
        "type": "status",
        "message": "Recording started",
        "session_id": session_id
    })

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                await _handle_audio_chunk(
                    websocket, session, message["bytes"]
                )

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
    session.chunk_count += 1
    chunk_id = f"{session.session_id}_{session.chunk_count}"

    logger.info(f"Chunk {chunk_id} received — {len(audio_bytes)} bytes")

    wav_path = None

    try:
        wav_path = convert_webm_to_wav(audio_bytes, chunk_id)
        text = transcribe_chunk(wav_path)

        if not text or len(text.strip()) == 0:
            logger.warning(f"Chunk {chunk_id} produced empty transcript — skipping")
            return

        session.transcript_chunks.append(text.strip())

        # ── RAG: ingest chunk into vector store (non-blocking) ─────────────
        session.pipeline.ingest(text.strip(), session.chunk_count)

        logger.info(f"Chunk {chunk_id} transcribed: '{text[:50]}...'")

        await _send(websocket, {
            "type": "transcript",
            "text": text.strip(),
            "chunk_id": session.chunk_count,
            "total_words": session.word_count
        })

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
        if wav_path:
            cleanup_chunk(wav_path)


async def _handle_text_message(
    websocket: WebSocket,
    session: MeetingSession,
    data: dict
):
    message_type = data.get("type")

    if message_type == "stop":
        session.is_recording = False
        logger.info(f"Session {session.session_id} stopped by user")

        # ── RAG: drain queue before summary ───────────────────────────────
        # pipeline.stop() is blocking (queue.join())
        # run in executor so we don't block the event loop
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, session.pipeline.stop)

        await _send(websocket, {
            "type": "status",
            "message": "Recording stopped",
            "total_words": session.word_count,
            "total_chunks": session.chunk_count
        })

        # auto generate final summary on stop
        await _send_final_summary(websocket, session)

    elif message_type == "generate_summary":
        await _send_final_summary(websocket, session)

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


async def _send_final_summary(
    websocket: WebSocket,
    session: MeetingSession
):
    logger.info(f"Generating final summary for session {session.session_id}")

    if session.word_count < 50:
        await _send(websocket, {
            "type": "error",
            "message": "Not enough transcript to generate summary",
            "stage": "final_summary"
        })
        return

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
    RAG + LangGraph agent answers questions.
    Works during ongoing recording and after stop.
    """
    logger.info(f"Question received: '{question}'")

    await _send(websocket, {
        "type": "status",
        "message": "Searching transcript..."
    })

    # ── RAG: agent searches transcript + web if needed ─────────────────────
    answer = await run_agent(question, session.vector_store)

    await _send(websocket, {
        "type": "qa_answer",
        "question": question,
        "text": answer
    })


async def _send(websocket: WebSocket, data: dict):
    try:
        await websocket.send_json(data)
    except Exception as e:
        logger.error(f"Failed to send message: {e}")