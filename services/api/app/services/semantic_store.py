import hashlib
import json
import os
from typing import Any, Dict, List


class SemanticVectorStore:
    def __init__(self, storage_path: str | None = None):
        self.storage_path = storage_path or os.getenv(
            "SEMANTIC_STORE_PATH", "/tmp/cloudgraph-semantic-store.json"
        )
        self.documents: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
                self.documents = data.get("documents", [])
        except Exception:
            self.documents = []

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.storage_path) or ".", exist_ok=True)
        with open(self.storage_path, "w", encoding="utf-8") as handle:
            json.dump({"documents": self.documents}, handle)

    def _simple_embedding(self, text: str) -> List[float]:
        tokens = [token for token in text.lower().replace("-", " ").split() if token]
        dimension = 32
        vector = [0.0] * dimension
        if not tokens:
            return vector
        for token in tokens:
            index = (
                int(hashlib.sha256(token.encode("utf-8")).hexdigest(), 16) % dimension
            )
            vector[index] += 1.0
        return vector

    def _cosine_similarity(self, left: List[float], right: List[float]) -> float:
        if not left or not right:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = sum(a * a for a in left) ** 0.5
        right_norm = sum(b * b for b in right) ** 0.5
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    def index_document(
        self, doc_id: str, text: str, metadata: Dict[str, Any] | None = None
    ) -> Dict[str, Any]:
        metadata = metadata or {}
        embedding = self._simple_embedding(text)
        document = {
            "id": doc_id,
            "text": text,
            "embedding": embedding,
            "metadata": metadata,
            "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        }
        existing = [item for item in self.documents if item["id"] == doc_id]
        if existing:
            self.documents = [item for item in self.documents if item["id"] != doc_id]
        self.documents.append(document)
        self._save()
        return document

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        query_embedding = self._simple_embedding(query)
        scored = []
        for document in self.documents:
            score = self._cosine_similarity(query_embedding, document["embedding"])
            scored.append((score, document))
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
