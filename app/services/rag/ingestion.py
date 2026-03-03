import queue
import threading
import re
from langchain_core.documents import Document
from app.services.rag.store import MeetingVectorStore
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TranscriptIngestionPipeline:
    """
    Background ingestion pipeline.
    Audio handler drops chunks here — worker processes them.
    Same concept as your batch loop but continuous and non-blocking.
    """

    def __init__(self, store: MeetingVectorStore):
        self._store = store
        self._queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(
            target=self._run,
            name=f"ingestion_{store.session_id}",
            daemon=True
        )

    def start(self):
        self._worker.start()
        logger.info(f"Pipeline started for {self._store.session_id}")

    def stop(self):
        """Wait for queue to drain then stop worker."""
        logger.info("Draining queue...")
        self._queue.join()
        self._stop_event.set()
        self._worker.join(timeout=5)
        logger.info(f"Pipeline stopped. {self._store.count} sentences indexed")

    def ingest(self, text: str, chunk_id: int):
        """Non-blocking — drops chunk in queue and returns immediately."""
        if text and text.strip():
            self._queue.put((text.strip(), chunk_id))

    def _run(self):
        while not self._stop_event.is_set():
            try:
                text, chunk_id = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                sentences = _split_sentences(text)
                if sentences:
                    added = self._store.add_texts(sentences, chunk_id)
                    logger.debug(f"Chunk {chunk_id} {added} sentences indexed")
            except Exception as e:
                logger.error(f"Ingestion error chunk {chunk_id}: {e}")
            finally:
                self._queue.task_done()


def _split_sentences(text: str) -> list[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 15]