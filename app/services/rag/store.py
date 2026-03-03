import threading
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import FastEmbedEmbeddings
from app.utils.logger import get_logger

logger = get_logger(__name__)

# FastEmbedEmbeddings uses ONNX runtime internally
# same all-MiniLM-L6-v2 model, no sentence-transformers needed
# loaded once at module level — shared across all sessions
embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
logger.info("Embeddings loaded")


class MeetingVectorStore:
    """
    Per-session in-memory Chroma vectorstore.
    LangChain style — same as your medical app but in-memory.
    Thread-safe for concurrent reads and writes.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id

        # in-memory Chroma — no persist_directory
        self._vectorstore = Chroma(
            collection_name=f"session_{session_id}",
            embedding_function=embeddings,
            collection_metadata={"hnsw:space": "cosine"}
        )

        self._lock = threading.Lock()
        self._seen: set[str] = set()
        self._count = 0

        logger.info(f"VectorStore ready for session {session_id}")

    def add_texts(self, texts: list[str], chunk_id: int) -> int:
        """
        Add sentences to vectorstore.
        Same as vectorstore.add_texts() in your medical app.
        Thread-safe.
        """
        new_texts = [t for t in texts if t not in self._seen]
        if not new_texts:
            return 0

        metadatas = [{"chunk_id": chunk_id} for _ in new_texts]

        with self._lock:
            try:
                self._vectorstore.add_texts(
                    texts=new_texts,
                    metadatas=metadatas
                )
                self._seen.update(new_texts)
                self._count += len(new_texts)
                logger.debug(f"Added {len(new_texts)} texts from chunk {chunk_id}")
                return len(new_texts)
            except Exception as e:
                logger.error(f"Failed to add texts: {e}")
                return 0

    def as_retriever(self, k: int = 5):
        """
        Returns LangChain retriever object.
        Same as vectorstore.as_retriever() in your medical app.
        """
        return self._vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": k}
        )

    def similarity_search(self, query: str, k: int = 5) -> list:
        """
        Direct similarity search.
        Returns LangChain Document objects.
        """
        with self._lock:
            if self._count == 0:
                return []
            k = min(k, self._count)
            return self._vectorstore.similarity_search(query, k=k)

    @property
    def count(self) -> int:
        return self._count