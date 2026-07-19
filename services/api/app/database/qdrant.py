"""Offline-safe Qdrant connection and collection lifecycle management."""

import logging
import os
import uuid
from collections.abc import Sequence
from typing import Any

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from qdrant_client.http.exceptions import ApiException, UnexpectedResponse

logger = logging.getLogger(__name__)

# Specific exception tuple covering all connection, HTTP, and API errors
QDRANT_ERRORS = (
    ValueError,
    TypeError,
    ConnectionError,
    OSError,
    RuntimeError,
    httpx.HTTPError,
    UnexpectedResponse,
    ApiException,
)


class QdrantClientWrapper:
    """Lazy, offline-safe access to the CloudGraph Qdrant instance."""

    def __init__(self, client_factory=QdrantClient):
        self._url_params = {
            "host": os.getenv("QDRANT_HOST", "localhost"),
            "port": int(os.getenv("QDRANT_PORT", "6333")),
            "api_key": os.getenv("QDRANT_API_KEY"),
            "timeout": float(os.getenv("QDRANT_TIMEOUT", "2.0")),
        }
        self.vector_size = int(os.getenv("QDRANT_VECTOR_SIZE", "384"))
        self.collection_names = tuple(
            name.strip()
            for name in os.getenv("QDRANT_COLLECTIONS", "evidence").split(",")
            if name.strip()
        )
        self._client_factory = client_factory
        self.client: QdrantClient | None = None

    def connect(self) -> bool:
        """Connect to Qdrant, returning False instead of raising offline errors."""
        if self.client is not None:
            return True

        try:
            client = self._client_factory(
                host=self._url_params["host"],
                port=self._url_params["port"],
                api_key=self._url_params["api_key"],
                timeout=self._url_params["timeout"],
                check_compatibility=False,
            )
            client.get_collections()
            self.client = client
            return True
        except QDRANT_ERRORS as exc:
            self.client = None
            logger.warning(
                "Qdrant is unavailable at %s:%s; vector retrieval is disabled: %s",
                self._url_params["host"],
                self._url_params["port"],
                exc,
            )
            return False

    def close(self) -> None:
        """Close the Qdrant connection cleanly."""
        if self.client is not None:
            try:
                self.client.close()
            except QDRANT_ERRORS as exc:
                logger.warning("Failed to close the Qdrant client cleanly: %s", exc)
            finally:
                self.client = None

    def ensure_collections(self) -> bool:
        """Create configured collections when absent; remain safe when offline."""
        if not self.connect():
            return False

        try:
            for collection_name in self.collection_names:
                if not self.client.collection_exists(collection_name):
                    self.client.create_collection(
                        collection_name=collection_name,
                        vectors_config=VectorParams(
                            size=self.vector_size,
                            distance=Distance.COSINE,
                        ),
                    )
                    logger.info("Created Qdrant collection %s", collection_name)
            return True
        except QDRANT_ERRORS as exc:
            logger.warning(
                "Could not initialize Qdrant collections; "
                "vector retrieval is disabled: %s",
                exc,
            )
            self.client = None
            return False

    def search(
        self,
        query_vector: Sequence[float],
        *,
        collection_name: str = "evidence",
        limit: int = 10,
        query_filter: Any = None,
    ) -> list[Any]:
        """Return nearest points, or an empty list whenever Qdrant is offline."""
        if not self.connect():
            return []

        try:
            response = self.client.query_points(
                collection_name=collection_name,
                query=list(query_vector),
                query_filter=query_filter,
                limit=limit,
            )
            return list(response.points)
        except QDRANT_ERRORS as exc:
            logger.warning("Qdrant search failed; returning no vector results: %s", exc)
            self.client = None
            return []

    def upsert(
        self,
        doc_id: str,
        vector: Sequence[float],
        payload: dict[str, Any],
        *,
        collection_name: str = "evidence",
    ) -> bool:
        """Store one evidence vector, returning False when Qdrant is offline."""
        if not self.connect():
            return False
        try:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"cloudgraph:{doc_id}"))
            self.client.upsert(
                collection_name=collection_name,
                points=[PointStruct(id=point_id, vector=list(vector), payload=payload)],
                wait=True,
            )
            return True
        except QDRANT_ERRORS as exc:
            logger.warning(
                "Qdrant upsert failed; evidence remains in file fallback: %s", exc
            )
            self.client = None
            return False


qdrant_client = QdrantClientWrapper()
