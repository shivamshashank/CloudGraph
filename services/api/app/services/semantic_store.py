"""Semantic evidence storage backed by Qdrant with an offline file fallback."""

import hashlib
import json
import logging
import os
from typing import Any

from app.database.qdrant import QDRANT_ERRORS, qdrant_client
from app.services.embeddings import (
    EmbeddingUnavailable,
    HashedFallbackEmbedder,
    SentenceTransformerEmbedder,
)
from app.services.evidence_chunking import chunk_evidence


logger = logging.getLogger(__name__)


class SemanticVectorStore:
    """Semantic vector store implementing fallback capabilities."""

    def __init__(
        self,
        storage_path: str | None = None,
        embedder=None,
        vector_client=None,
    ):
        self.storage_path = storage_path or os.getenv(
            "SEMANTIC_STORE_PATH", "/tmp/cloudgraph-semantic-store.json"
        )
        self.embedder = embedder or SentenceTransformerEmbedder()
        self.fallback_embedder = HashedFallbackEmbedder()
        self.vector_client = vector_client or qdrant_client
        self.documents: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                self.documents = json.load(handle).get("documents", [])
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Could not load semantic fallback store: %s", exc)
            self.documents = []

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path) or ".", exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as handle:
            json.dump({"documents": self.documents}, handle)

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = sum(a * a for a in left) ** 0.5
        right_norm = sum(b * b for b in right) ** 0.5
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    def _embed(self, text: str) -> tuple[list[float], str]:
        try:
            return self.embedder.embed(text), "sentence-transformer"
        except EmbeddingUnavailable:
            return self.fallback_embedder.embed(text), "hashed-file-fallback"

    def index_document(
        self, doc_id: str, text: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Index a document into the local fallback store and Qdrant if possible."""
        metadata = dict(metadata or {})
        evidence_type = str(
            metadata.get("type") or metadata.get("label") or "evidence"
        ).lower()
        chunks = chunk_evidence(text, evidence_type, metadata)
        indexed: list[dict[str, Any]] = []

        for index, chunk in enumerate(chunks):
            chunk_id = doc_id if len(chunks) == 1 else f"{doc_id}:{index}"
            embedding, backend = self._embed(chunk)
            chunk_metadata = {
                **metadata,
                "type": evidence_type,
                "source_id": doc_id,
                "chunk_index": index,
                "embedding_backend": backend,
            }
            document = {
                "id": chunk_id,
                "text": chunk,
                "embedding": embedding,
                "metadata": chunk_metadata,
                "hash": hashlib.sha256(chunk.encode("utf-8")).hexdigest(),
            }
            self.documents = [item for item in self.documents if item["id"] != chunk_id]
            self.documents.append(document)
            indexed.append(document)

            # Never contaminate the real vector collection with fallback vectors.
            if backend == "sentence-transformer":
                try:
                    self.vector_client.upsert(
                        chunk_id,
                        embedding,
                        {"id": chunk_id, "text": chunk, **chunk_metadata},
                    )
                except QDRANT_ERRORS as exc:
                    logger.warning("Could not upsert semantic vector: %s", exc)

        self._save()
        return indexed[0] if indexed else {}

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Search documents using the vector client or the fallback store."""
        query_embedding, backend = self._embed(query)
        if backend == "sentence-transformer":
            try:
                points = self.vector_client.search(query_embedding, limit=limit)
            except QDRANT_ERRORS as exc:
                logger.warning("Could not search semantic vector store: %s", exc)
                points = []
            if points:
                return [
                    {
                        "id": point.payload.get("id", str(point.id)),
                        "text": point.payload.get("text", ""),
                        "metadata": {
                            key: value
                            for key, value in point.payload.items()
                            if key not in {"id", "text"}
                        },
                        "score": float(point.score),
                    }
                    for point in points
                ]

        # Qdrant or the model is unavailable: search persisted local evidence.
        scored = [
            (self._cosine_similarity(query_embedding, doc["embedding"]), doc)
            for doc in self.documents
            if doc.get("metadata", {}).get("embedding_backend") == backend
            or "embedding_backend" not in doc.get("metadata", {})
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                "id": document["id"],
                "text": document["text"],
                "metadata": document["metadata"],
                "score": score,
            }
            for score, document in scored[:limit]
            if score > 0.0
        ]
