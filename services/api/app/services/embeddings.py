"""Local embedding providers used by CloudGraph retrieval."""

import hashlib
import logging
import os
from sentence_transformers import SentenceTransformer


logger = logging.getLogger(__name__)


class EmbeddingUnavailable(RuntimeError):
    """Raised when the configured local embedding model cannot be loaded."""


class SentenceTransformerEmbedder:
    """Lazy local all-MiniLM-L6-v2 encoder with no hosted API dependency."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or os.getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )
        self.dimension = 384
        self._model = None
        self._load_failed = False

    def get_dimension(self) -> int:
        """Return the vector dimension of generated embeddings."""
        return self.dimension

    def _load(self):
        if self._load_failed:
            raise EmbeddingUnavailable(
                f"Embedding model {self.model_name} is unavailable"
            )
        if self._model is not None:
            return self._model
        try:
            self._model = SentenceTransformer(self.model_name)
            dimension = self._model.get_embedding_dimension()
            if dimension:
                self.dimension = int(dimension)
            return self._model
        except Exception as exc:
            self._load_failed = True
            logger.warning(
                "Local embedding model %s is unavailable; using the file fallback: %s",
                self.model_name,
                exc,
            )
            raise EmbeddingUnavailable(str(exc)) from exc

    def embed(self, text: str) -> list[float]:
        """Encode the given text string into normalized float embeddings."""
        try:
            vector = self._load().encode(
                text,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except EmbeddingUnavailable:
            raise
        except Exception as exc:
            self._load_failed = True
            logger.warning(
                "Local embedding model %s is unavailable; using the file fallback: %s",
                self.model_name,
                exc,
            )
            raise EmbeddingUnavailable(str(exc)) from exc
        return vector.tolist()


class HashedFallbackEmbedder:
    """Deterministic offline fallback; not used for Qdrant indexing."""

    dimension = 384

    def get_dimension(self) -> int:
        """Return the vector dimension of generated embeddings."""
        return self.dimension

    def embed(self, text: str) -> list[float]:
        """Generate a deterministic normalized vector based on term hashes."""
        tokens = [token for token in text.lower().replace("-", " ").split() if token]
        vector = [0.0] * self.dimension
        for token in tokens:
            index = int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16)
            vector[index % self.dimension] += 1.0
        norm = sum(value * value for value in vector) ** 0.5
        return [value / norm for value in vector] if norm else vector
