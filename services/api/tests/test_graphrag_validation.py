"""GraphRAG relevance and latency validation benchmark."""

# pylint: disable=too-few-public-methods,too-many-locals
# pylint: disable=duplicate-code

import time
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

            # Simple helper object mimicking Qdrant remote return types
            class QdrantPoint:  # pylint: disable=too-few-public-methods
                """Mimics Qdrant search result point."""

                def __init__(self, doc_id: str, score_val: float, payload: dict):
                    self.id = doc_id
                    self.score = score_val
                    self.payload = payload

            results.append(QdrantPoint(doc["id"], score, doc))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]


@pytest.fixture
def seeded_validation_data() -> Dict[str, Any]:
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


def test_graphrag_end_to_end_validation(
    seeded_validation_data,
):  # pylint: disable=redefined-outer-name
    """Run E2E validation assessing hybrid retrieval latency and relevance."""
    data = seeded_validation_data
    client = FakeVectorClient(data["vector_docs"])
    store = SemanticVectorStore(embedder=FakeEmbedder(), vector_client=client)
    ranker = HybridRanker()

    # Define Query Benchmark Test Cases
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
        query = case["query"]
        target = case["target"]

        # 1. Evaluate Vector-Only RAG
        t_start = time.perf_counter()
        vector_results = store.search(query, limit=5)
        t_vector = (time.perf_counter() - t_start) * 1000.0

        vector_rank = next(
            (idx + 1 for idx, r in enumerate(vector_results) if r["id"] == target), 0
        )
        vector_rr = 1.0 / vector_rank if vector_rank > 0 else 0.0
        vector_recall = 1.0 if vector_rank > 0 else 0.0

        print(
            f"{case['description']:<30} | {'Vector-Only':<12} | "
            f"{t_vector:6.2f}ms | {vector_rr:8.2f} | {vector_recall:6.1f}"
        )

        # 2. Evaluate Hybrid GraphRAG
        t_start = time.perf_counter()
        query_vec = FakeEmbedder().embed(query)
        raw_vector_hits = []
        for doc in data["vector_docs"]:
            doc_vec = FakeEmbedder().embed(doc["text"])
            dot_product = sum(a * b for a, b in zip(query_vec, doc_vec))
            norm_q = sum(x * x for x in query_vec) ** 0.5
            norm_d = sum(x * x for x in doc_vec) ** 0.5
            cosine_sim = (
                dot_product / (norm_q * norm_d) if (norm_q * norm_d) > 0.0 else 0.0
            )
            raw_vector_hits.append(
                {
                    "id": doc["id"],
                    "text": doc["text"],
                    "score": cosine_sim,
                    "metadata": doc,
                }
            )

        hybrid_results = ranker.rank(
            raw_vector_hits, data["graph_hits"], reference_time=1500, limit=5
        )
        t_hybrid = (time.perf_counter() - t_start) * 1000.0

        hybrid_rank = next(
            (idx + 1 for idx, r in enumerate(hybrid_results) if r["id"] == target), 0
        )
        hybrid_rr = 1.0 / hybrid_rank if hybrid_rank > 0 else 0.0
        hybrid_recall = 1.0 if hybrid_rank > 0 else 0.0

        print(
            f"{case['description']:<30} | {'Hybrid G-RAG':<12} | "
            f"{t_hybrid:6.2f}ms | {hybrid_rr:8.2f} | {hybrid_recall:6.1f}"
        )
        print("-" * 80)

        # Assertions to validate GraphRAG effectiveness
        # 1. Latency targets (Hybrid should run well under 100ms)
        assert (
            t_hybrid < 100.0
        ), f"Hybrid latency exceeds performance threshold: {t_hybrid:.2f}ms"

        # 2. Relevance targets (Hybrid should match or exceed Vector-Only rank/recall)
        assert hybrid_rr >= vector_rr, (
            f"GraphRAG relevance degraded compared to vector baseline: "
            f"Hybrid RR {hybrid_rr:.2f} < Vector RR {vector_rr:.2f}"
        )
        assert hybrid_recall >= vector_recall, (
            f"GraphRAG recall degraded compared to vector baseline: "
            f"Hybrid Recall {hybrid_recall:.1f} < Vector Recall {vector_recall:.1f}"
        )

    print("=" * 80)
    print("GraphRAG relevance & latency benchmark completed successfully.")
    print("=" * 80)
