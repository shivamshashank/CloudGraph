"""Fuse semantic similarity, graph proximity, and evidence recency."""

import math
import os
import time
from typing import Any


class HybridRanker:
    """Fuse semantic similarity, graph proximity, and evidence recency."""

    FORMULA = (
        "hybrid_score = 0.50 * vector_similarity + "
        "0.30 * graph_proximity + 0.20 * recency"
    )

    def __init__(
        self,
        vector_weight: float = 0.50,
        graph_weight: float = 0.30,
        recency_weight: float = 0.20,
        recency_half_life_seconds: int | None = None,
    ):
        self.weights = {
            "vector_similarity": vector_weight,
            "graph_proximity": graph_weight,
            "recency": recency_weight,
        }
        if not math.isclose(sum(self.weights.values()), 1.0, abs_tol=1e-9):
            raise ValueError("hybrid ranking weights must sum to 1.0")
        if any(weight < 0 for weight in self.weights.values()):
            raise ValueError("hybrid ranking weights cannot be negative")
        self.recency_half_life_seconds = recency_half_life_seconds or int(
            os.getenv("GRAPHRAG_RECENCY_HALF_LIFE_SECONDS", "3600")
        )
        if self.recency_half_life_seconds <= 0:
            raise ValueError("recency half-life must be positive")

    def get_weights(self) -> dict[str, float]:
        """Return the active weighting parameters for ranking."""
        return self.weights.copy()

    def rank(
        self,
        vector_hits: list[dict[str, Any]],
        graph_hits: list[dict[str, Any]],
        *,
        reference_time: int | float | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Combines, scores, and ranks vector and graph retrieval results."""
        reference = float(reference_time if reference_time is not None else time.time())
        candidates: dict[str, dict[str, Any]] = {}

        for hit in vector_hits:
            metadata = dict(hit.get("metadata") or {})
            identity = self._identity(hit.get("id"), metadata)
            candidate = candidates.setdefault(identity, self._candidate(identity))
            candidate["id"] = hit.get("id") or identity
            candidate["text"] = hit.get("text", "")
            candidate["metadata"].update(metadata)
            candidate["vector_score"] = max(
                candidate["vector_score"], self._unit_score(hit.get("score"))
            )
            candidate["sources"].add("vector")

        for hit in graph_hits:
            properties = dict(hit.get("properties") or {})
            identity = self._identity(hit.get("id"), properties)
            candidate = candidates.setdefault(identity, self._candidate(identity))
            hop_distance = max(0, int(hit.get("hop_distance") or 0))
            if (
                candidate["hop_distance"] is None
                or hop_distance < candidate["hop_distance"]
            ):
                candidate["id"] = hit.get("id") or identity
                candidate["labels"] = list(hit.get("labels") or [])
                candidate["properties"] = properties
                candidate["hop_distance"] = hop_distance
                candidate["relationships"] = list(hit.get("relationships") or [])
                candidate["path"] = list(hit.get("path") or [])
            candidate["sources"].add("graph")

        ranked = []
        for candidate in candidates.values():
            ranked.append(self._score_candidate(candidate, reference))

        ranked.sort(key=lambda item: (-item["score"], str(item["id"])))
        return ranked[:limit]

    def _score_candidate(
        self, candidate: dict[str, Any], reference: float
    ) -> dict[str, Any]:
        """Calculate combined score metrics and rank explanations for candidate."""
        vector_score = candidate.pop("vector_score")
        hop_distance = candidate["hop_distance"]
        graph_score = 1.0 / (1.0 + hop_distance) if hop_distance is not None else 0.0
        timestamp = self._timestamp(candidate)
        recency_score, age_seconds = self._recency(timestamp, reference)

        final_score = (
            self.weights["vector_similarity"] * vector_score
            + self.weights["graph_proximity"] * graph_score
            + self.weights["recency"] * recency_score
        )

        candidate["sources"] = sorted(candidate["sources"])
        candidate["name"] = self._name(candidate)
        candidate["type"] = self._type(candidate)
        candidate["score"] = round(final_score, 6)
        candidate["score_breakdown"] = {
            "formula": self.FORMULA,
            "vector_similarity": self._component(
                "vector_similarity",
                vector_score,
                "Cosine similarity from the local embedding search.",
            ),
            "graph_proximity": {
                **self._component(
                    "graph_proximity",
                    graph_score,
                    "Inverse hop distance: 1 / (1 + hop_distance).",
                ),
                "hop_distance": hop_distance,
            },
            "recency": {
                **self._component(
                    "recency",
                    recency_score,
                    "Exponential decay with a configurable one-hour half-life.",
                ),
                "timestamp": timestamp,
                "age_seconds": age_seconds,
                "half_life_seconds": self.recency_half_life_seconds,
            },
            "final_score": round(final_score, 6),
        }
        candidate["ranking_rationale"] = self._rationale(
            candidate, vector_score, graph_score, recency_score
        )
        return candidate

    @staticmethod
    def _candidate(identity: str) -> dict[str, Any]:
        return {
            "id": identity,
            "text": "",
            "metadata": {},
            "labels": [],
            "properties": {},
            "hop_distance": None,
            "relationships": [],
            "path": [],
            "vector_score": 0.0,
            "sources": set(),
        }

    @staticmethod
    def _identity(fallback: Any, values: dict[str, Any]) -> str:
        identity = values.get("source_id") or values.get("id") or values.get("sha")
        identity = str(identity or fallback or "unknown")
        if identity.startswith("neo4j:"):
            return identity.rsplit(":", 1)[-1]
        return identity

    @staticmethod
    def _unit_score(value: Any) -> float:
        try:
            return min(1.0, max(0.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    def _component(
        self, name: str, raw_score: float, explanation: str
    ) -> dict[str, Any]:
        return {
            "raw_score": round(raw_score, 6),
            "weight": self.weights[name],
            "contribution": round(raw_score * self.weights[name], 6),
            "explanation": explanation,
        }

    def _recency(
        self, timestamp: int | float | None, reference: float
    ) -> tuple[float, int | None]:
        if timestamp is None:
            return 0.0, None
        timestamp = float(timestamp)
        if timestamp > 10_000_000_000:
            timestamp /= 1000.0
        age = max(0.0, reference - timestamp)
        score = math.exp(-math.log(2) * age / self.recency_half_life_seconds)
        return score, int(age)

    @staticmethod
    def _timestamp(candidate: dict[str, Any]) -> int | float | None:
        for values in (candidate["metadata"], candidate["properties"]):
            for key in ("timestamp", "startTime", "endTime"):
                if values.get(key) is not None:
                    return values[key]
        return None

    @staticmethod
    def _name(candidate: dict[str, Any]) -> str:
        for values in (candidate["metadata"], candidate["properties"]):
            for key in ("name", "title", "message", "id"):
                if values.get(key):
                    return str(values[key])
        return "evidence"

    @staticmethod
    def _type(candidate: dict[str, Any]) -> str:
        if candidate["metadata"].get("type"):
            return str(candidate["metadata"]["type"]).lower()
        if candidate["labels"]:
            return str(candidate["labels"][0]).lower()
        return "evidence"

    def _rationale(
        self,
        candidate: dict[str, Any],
        vector: float,
        graph: float,
        recency: float,
    ) -> list[str]:
        hop_distance = candidate["hop_distance"]
        timestamp = self._timestamp(candidate)
        return [
            (
                "Vector similarity contributed "
                f"{self.weights['vector_similarity'] * vector:.3f} "
                f"from raw score {vector:.3f}."
            ),
            (
                "Graph proximity contributed "
                f"{self.weights['graph_proximity'] * graph:.3f} at "
                f"{hop_distance} hop(s)."
                if hop_distance is not None
                else (
                    "No graph path was available, so graph proximity "
                    "contributed 0.000."
                )
            ),
            (
                "Recency contributed "
                f"{self.weights['recency'] * recency:.3f} for timestamp {timestamp}."
                if timestamp is not None
                else "No timestamp was available, so recency contributed 0.000."
            ),
        ]


hybrid_ranker = HybridRanker()
