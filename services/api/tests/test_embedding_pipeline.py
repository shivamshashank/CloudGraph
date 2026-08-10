"""Tests verifying the document chunking and vector embedding pipelines."""

from types import SimpleNamespace

from app.services.evidence_chunking import chunk_evidence
from app.services.semantic_store import SemanticVectorStore
from scripts.backfill_qdrant import backfill, evidence_document


class FakeEmbedder:
    """Mock embedder providing deterministic vectors for testing."""

    dimension = 384

    def embed(self, text):
        """Generate vector based on specific word occurrence."""
        vector = [0.0] * self.dimension
        vector[0] = float(text.lower().count("database"))
        vector[1] = float(text.lower().count("healthy"))
        return vector

    def reset(self):
        """No-op reset for test compatibility."""


class FakeVectorClient:
    """Mock vector database client recording upsert operations."""

    def __init__(self):
        self.upserts = []
        self.points = []
        self.collections_written = []
        self.collections_searched = []
        self.filters_applied = []

    def upsert(self, doc_id, vector, payload, collection_name=None):
        """Record upsert values, including the collection written to.

        collection_name is accepted because evaluation runs redirect the
        store to a dedicated collection; a stand-in with a narrower
        signature than the real client turns that into a swallowed
        TypeError and an empty result set rather than a clear failure."""
        self.upserts.append((doc_id, vector, payload))
        self.collections_written.append(collection_name)
        return True

    def search(self, _vector, limit=5, query_filter=None, collection_name=None):
        """Mock searching vectors, returning pre-populated points list."""
        self.collections_searched.append(collection_name)
        self.filters_applied.append(query_filter)
        return self.points[:limit]


def test_log_chunking_preserves_complete_lines():
    """Verify log chunking preserves boundary lines and splits logically."""
    lines = [f"line {index} " + ("x" * 300) for index in range(6)]
    chunks = chunk_evidence("\n".join(lines), "log")

    assert len(chunks) > 1
    assert all(line in "\n".join(chunks) for line in lines)


def test_metric_and_change_metadata_remain_single_causal_units():
    """Verify that metrics and other deployments are kept as single chunks."""
    assert (
        len(chunk_evidence("cpu average 95 over five minutes", "metrics-summary")) == 1
    )
    assert len(chunk_evidence("deployment api revision abc failed", "deployment")) == 1
    assert len(chunk_evidence("commit abc changed auth secret", "commit")) == 1


def test_real_embedding_path_indexes_qdrant_and_file_fallback(tmp_path):
    """
    Verify correct execution of document indexing to both database and json backup.
    """
    vector_client = FakeVectorClient()
    store = SemanticVectorStore(
        storage_path=str(tmp_path / "semantic.json"),
        embedder=FakeEmbedder(),
        vector_client=vector_client,
    )

    document = store.index_document(
        "incident-1",
        "database authentication failure",
        {"type": "incident", "label": "Incident"},
    )

    assert len(document["embedding"]) == 384
    assert document["metadata"]["embedding_backend"] == "sentence-transformer"
    assert vector_client.upserts[0][0] == "incident-1"
    assert (tmp_path / "semantic.json").exists()


def test_search_maps_qdrant_payload_to_existing_store_interface(tmp_path):
    """Verify search maps external vector responses to local document attributes."""
    vector_client = FakeVectorClient()
    vector_client.points = [
        SimpleNamespace(
            id="uuid-1",
            score=0.93,
            payload={
                "id": "incident-1",
                "text": "database authentication failure",
                "type": "incident",
                "label": "Incident",
            },
        )
    ]
    store = SemanticVectorStore(
        storage_path=str(tmp_path / "semantic.json"),
        embedder=FakeEmbedder(),
        vector_client=vector_client,
    )

    result = store.search("database failure", limit=1)[0]

    assert result["id"] == "incident-1"
    assert result["metadata"]["type"] == "incident"
    assert result["score"] == 0.93


def test_backfill_formats_and_indexes_existing_neo4j_nodes(tmp_path):
    """Verify mapping and backfilling of Neo4j graph nodes to the vector store."""
    store = SemanticVectorStore(
        storage_path=str(tmp_path / "semantic.json"),
        embedder=FakeEmbedder(),
        vector_client=FakeVectorClient(),
    )
    rows = [
        {
            "type": "Log",
            "properties": {
                "id": "log-1",
                "message": "database connection refused",
                "timestamp": 123,
            },
        },
        {
            "type": "Metric",
            "properties": {
                "id": "metric-1",
                "name": "error_rate",
                "value": 0.9,
                "timestamp": 124,
            },
        },
    ]

    assert backfill(store, rows) == 2
    assert {doc["metadata"]["type"] for doc in store.documents} == {
        "log",
        "metrics-summary",
    }
    assert evidence_document(rows[0])[0] == "neo4j:Log:log-1"
