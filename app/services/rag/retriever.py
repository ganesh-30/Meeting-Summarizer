from dataclasses import dataclass
from langchain_core.documents import Document
from app.services.rag.store import MeetingVectorStore
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RetrievalResult:
    found: bool
    context: str
    documents: list[Document]
    count: int


class MeetingRetriever:
    """
    LangChain-style retriever wrapper.
    Same pattern as your medical app retriever.
    """

    def __init__(self, store: MeetingVectorStore, k: int = 5):
        self._store = store
        self._k = k

    def retrieve(self, query: str) -> RetrievalResult:
        if self._store.count == 0:
            return RetrievalResult(
                found=False,
                context="",
                documents=[],
                count=0
            )

        docs = self._store.similarity_search(query, k=self._k)

        if not docs:
            return RetrievalResult(
                found=False,
                context="",
                documents=[],
                count=0
            )

        # format context with chunk numbers for chronological awareness
        lines = [
            f"[chunk {doc.metadata.get('chunk_id', 0)}] {doc.page_content}"
            for doc in docs
        ]

        return RetrievalResult(
            found=True,
            context="\n".join(lines),
            documents=docs,
            count=len(docs)
        )