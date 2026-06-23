from __future__ import annotations

from threading import Lock
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

from app.core.exceptions import DependencyError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.db.repositories.candidates import CandidateRepository
from app.db.repositories.jobs import JobRepository
from app.schemas.common import EntityKind
from app.vector_store import VectorStore

log = get_logger(__name__)


class EmbeddingService:
    """
    Wraps the sentence-transformers model + writes to the configured VectorStore.

    The model is heavy (~400MB) and slow to load. We load once at startup via
    `warm_up()` and reuse the singleton for every request.
    """

    def __init__(self, model_name: str, vector_store: VectorStore):
        self.model_name = model_name
        self.vector_store = vector_store
        self._model = None
        self._dim: int | None = None
        self._lock = Lock()

    # ---------- lifecycle ----------

    def warm_up(self) -> None:
        """Load the model into memory. Safe to call multiple times."""
        with self._lock:
            if self._model is not None:
                return
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover
                raise DependencyError("sentence-transformers is not installed") from exc

            log.info("loading_embedding_model", model=self.model_name)
            self._model = SentenceTransformer(self.model_name)
            self._dim = int(self._model.get_sentence_embedding_dimension())
            log.info("embedding_model_loaded", model=self.model_name, dim=self._dim)

    @property
    def dim(self) -> int:
        if self._dim is None:
            self.warm_up()
        assert self._dim is not None
        return self._dim

    # ---------- core ops ----------

    def embed(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise ValidationError("Cannot embed empty text.")
        if self._model is None:
            self.warm_up()
        assert self._model is not None
        vec = self._model.encode(text, normalize_embeddings=False)
        return np.asarray(vec, dtype=np.float32).tolist()

    def store(
        self,
        session: Session,
        kind: EntityKind,
        entity_id: UUID,
        vector: list[float],
    ) -> None:
        if kind == "resume":
            if not CandidateRepository(session).exists(entity_id):
                raise NotFoundError(f"Candidate {entity_id} not found.")
            self.vector_store.upsert_resume(session, entity_id, vector, self.model_name)
        elif kind == "job":
            if not JobRepository(session).exists(entity_id):
                raise NotFoundError(f"Job {entity_id} not found.")
            self.vector_store.upsert_job(session, entity_id, vector, self.model_name)
        else:  # pragma: no cover
            raise ValidationError(f"Unknown kind: {kind}")
