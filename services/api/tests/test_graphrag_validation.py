"""GraphRAG relevance and latency validation benchmark."""

import time
from types import SimpleNamespace
from typing import Any, Dict, List
import pytest

from app.retrieval.hybrid_ranker import HybridRanker
from app.services.semantic_store import SemanticVectorStore


class FakeEmbedder:
    """Mock embedder providing deterministic vectors for validation."""

    dimension = 384

    def embed(self, text: str) -> List[float]:
        """Generate validation embedding based on query term frequency."""
        vector = [0.0] * self.dimension
        text_lower = text.lower()
        if "payment" in text_lower:
            vector[0] = 1.0
        if "database" in text_lower or "db" in text_lower:
            vector[1] = 1.0
        if "auth" in text_lower or "password" in text_lower:
            vector[2] = 1.0
        if "timeout" in text_lower or "latency" in text_lower:
            vector[3] = 1.0
        if "cpu" in text_lower or "utilization" in text_lower:
            vector[4] = 1.0
        return vector

    def get_dimension(self) -> int:
        """Get the embedding vector dimension."""
        return self.dimension


class FakeVectorClient:
    """Mock vector store client loaded with validation documents."""

    def __init__(self, documents: List[Dict[str, Any]]):
        """Initialize the client with seeded validation documents."""
        self.documents = documents

    def search(self, vector: List[float], limit: int = 5) -> List[Any]:
        """Search validation documents using dot product similarity."""
        results = []
        for doc in self.documents:
            doc_vec = FakeEmbedder().embed(doc["text"])
            # Simple dot product as cosine similarity approximation
            score = sum(a * b for a, b in zip(vector, doc_vec))
            # Normalize to 0-1 range for similarity
            score = min(
                0.99, max(0.1, score / (sum(x * x for x in vector) ** 0.5 or 1.0))
            )

            results.append(SimpleNamespace(id=doc["id"], score=score, payload=doc))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def get_document_count(self) -> int:
        """Get the total count of documents in the mock store."""
        return len(self.documents)


@pytest.fixture(name="seeded_validation_data")
def validation_fixture() -> Dict[str, Any]:
    """Fixture containing validation incidents, logs, metrics, and commits."""
    # Seeded raw documents for vector store
    vector_docs = [
        {
            "id": "commit-auth",
            "text": (
                "commit sha-auth update payment database password, "
                "changed credentials secret"
            ),
            "type": "commit",
            "label": "Commit",
            "timestamp": 1000,
        },
        {
            "id": "log-timeout",
            "text": "log error request timeout connection to payment service",
            "type": "log",
            "label": "Log",
            "timestamp": 1200,
        },
        {
            "id": "metric-cpu",
            "text": "metric CPU utilization average 98 percent",
            "type": "metrics-summary",
            "label": "Metric",
            "timestamp": 1300,
        },
        {
            "id": "other-noise-1",
            "text": "log info heartbeat service healthy check ok",
            "type": "log",
            "label": "Log",
            "timestamp": 1400,
        },
    ]

    # Mock Neo4j graph traversal records
    graph_hits = [
        {
            "id": "commit-auth",
            "labels": ["Commit"],
            "properties": {"id": "commit-auth", "timestamp": 1000},
            "hop_distance": 2,
            "relationships": ["TRIGGERED_BY"],
            "path": [
                {"name": "payment-pod"},
                {"name": "payment-deployment"},
                {"name": "commit-auth"},
            ],
        },
        {
            "id": "log-timeout",
            "labels": ["Log"],
            "properties": {"id": "log-timeout", "timestamp": 1200},
            "hop_distance": 1,
            "relationships": ["GENERATES"],
            "path": [{"name": "checkout-pod"}, {"name": "log-timeout"}],
        },
        {
            "id": "metric-cpu",
            "labels": ["Metric"],
            "properties": {"id": "metric-cpu", "timestamp": 1300},
            "hop_distance": 1,
            "relationships": ["GENERATES"],
            "path": [{"name": "checkout-pod"}, {"name": "metric-cpu"}],
        },
    ]

    return {"vector_docs": vector_docs, "graph_hits": graph_hits}


def _cos_sim(v1, v2):
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = sum(x * x for x in v1) ** 0.5
    n2 = sum(x * x for x in v2) ** 0.5
    return dot / (n1 * n2) if (n1 * n2) > 0.0 else 0.0


def _evaluate_case(case, store, data, ranker):
    # 1. Evaluate Vector-Only RAG
    t_start = time.perf_counter()
    vector_results = store.search(case["query"], limit=5)
    v_rank = next(
        (i + 1 for i, r in enumerate(vector_results) if r["id"] == case["target"]), 0
    )
    v_rr = 1.0 / v_rank if v_rank > 0 else 0.0

    print(
        f"{case['description']:<30} | {'Vector-Only':<12} | "
        f"{(time.perf_counter() - t_start) * 1000.0:6.2f}ms | "
        f"{v_rr:8.2f} | {1.0 if v_rank > 0 else 0.0:6.1f}"
    )

    # 2. Evaluate Hybrid GraphRAG
    t_start = time.perf_counter()
    raw_vector_hits = [
        {
            "id": doc["id"],
            "text": doc["text"],
            "score": _cos_sim(
                FakeEmbedder().embed(case["query"]), FakeEmbedder().embed(doc["text"])
            ),
            "metadata": doc,
        }
        for doc in data["vector_docs"]
    ]

    hybrid_results = ranker.rank(
        raw_vector_hits, data["graph_hits"], reference_time=1500, limit=5
    )
    t_hybrid = (time.perf_counter() - t_start) * 1000.0

    h_rank = next(
        (i + 1 for i, r in enumerate(hybrid_results) if r["id"] == case["target"]), 0
    )
    h_rr = 1.0 / h_rank if h_rank > 0 else 0.0

    print(
        f"{case['description']:<30} | {'Hybrid G-RAG':<12} | "
        f"{t_hybrid:6.2f}ms | {h_rr:8.2f} | {1.0 if h_rank > 0 else 0.0:6.1f}"
    )
    print("-" * 80)

    assert (
        t_hybrid < 100.0
    ), f"Hybrid latency exceeds performance threshold: {t_hybrid:.2f}ms"

    assert h_rr >= v_rr, (
        f"GraphRAG relevance degraded compared to vector baseline: "
        f"Hybrid RR {h_rr:.2f} < Vector RR {v_rr:.2f}"
    )
    assert (1.0 if h_rank > 0 else 0.0) >= (1.0 if v_rank > 0 else 0.0), (
        f"GraphRAG recall degraded compared to vector baseline: "
        f"Hybrid Recall {1.0 if h_rank > 0 else 0.0:.1f} < "
        f"Vector Recall {1.0 if v_rank > 0 else 0.0:.1f}"
    )


def test_graphrag_end_to_end_validation(seeded_validation_data):
    """Run E2E validation assessing hybrid retrieval latency and relevance."""
    data = seeded_validation_data
    client = FakeVectorClient(data["vector_docs"])
    store = SemanticVectorStore(embedder=FakeEmbedder(), vector_client=client)
    ranker = HybridRanker()

    test_cases = [
        {
            "query": "payment database credentials failure",
            "target": "commit-auth",
            "description": "Auth regression",
        },
        {
            "query": "request connection timeout",
            "target": "log-timeout",
            "description": "Network timeout log",
        },
        {
            "query": "high CPU utilization",
            "target": "metric-cpu",
            "description": "Resource saturation metric",
        },
    ]

    print("\n" + "=" * 80)
    print("                      GRAPHRAG BENCHMARK VALIDATION REPORT")
    print("=" * 80)
    print(
        f"{'Test Case':<30} | {'Method':<12} | "
        f"{'Latency':<9} | {'RR Score':<8} | {'Recall':<6}"
    )
    print("-" * 80)

    for case in test_cases:
        _evaluate_case(case, store, data, ranker)

    print("=" * 80)
    print("GraphRAG relevance & latency benchmark completed successfully.")
    print("=" * 80)
