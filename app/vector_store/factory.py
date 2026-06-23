from app.core.config import Settings
from app.core.exceptions import DependencyError
from app.vector_store.base import VectorStore
from app.vector_store.pgvector import PgVectorStore


def get_vector_store(settings: Settings) -> VectorStore:
    backend = settings.vector_store_backend
    if backend == "pgvector":
        return PgVectorStore()
    if backend == "pinecone":
        raise DependencyError("Pinecone backend not yet implemented.")
    raise DependencyError(f"Unknown vector store backend: {backend}")
