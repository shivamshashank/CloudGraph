"""Tests verifying the offline-safe Qdrant client wrapper functionality."""

from types import SimpleNamespace

from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app import main
from app.database.qdrant import QdrantClientWrapper


class FakeQdrantClient:
    """Mock implementation of the QdrantClient for testing connection states."""

    def __init__(self, existing=()):
        self.existing = set(existing)
        self.created = []
        self.upserted = []
        self.closed = False

    def get_collections(self):
        """Mock retrieving Qdrant collections."""
        return SimpleNamespace(collections=[])

    def collection_exists(self, collection_name):
        """Mock verification of whether collection exists."""
        return collection_name in self.existing

    def create_collection(self, collection_name, vectors_config):
        """Mock collection creation."""
        self.existing.add(collection_name)
        self.created.append((collection_name, vectors_config))

    def query_points(self, **_kwargs):
        """Mock querying points."""
        return SimpleNamespace(points=[SimpleNamespace(id="evidence-1", score=0.9)])

    def upsert(self, **kwargs):
        """Mock upserting records."""
        self.upserted.append(kwargs)

    def close(self):
        """Mock closing connection."""
        self.closed = True


def test_uses_qdrant_host_and_creates_unified_evidence_collection(monkeypatch):
    """
    Verify Qdrant client host configuration and collection structure initialization.
    """
    monkeypatch.setenv("QDRANT_HOST", "qdrant.cloudgraph.svc")
    monkeypatch.setenv("QDRANT_VECTOR_SIZE", "768")
    fake = FakeQdrantClient()
    factory_args = {}

    def factory(**kwargs):
        factory_args.update(kwargs)
        return fake

    client = QdrantClientWrapper(client_factory=factory)

    assert client.ensure_collections() is True
    assert factory_args["host"] == "qdrant.cloudgraph.svc"
    assert fake.created[0][0] == "evidence"
    assert fake.created[0][1].size == 768


def test_existing_collection_is_not_recreated():
    """Verify that verify_collections does not recreate an existing collection."""
    fake = FakeQdrantClient(existing={"evidence"})
    client = QdrantClientWrapper(client_factory=lambda **_kwargs: fake)

    assert client.ensure_collections() is True
    assert not fake.created


def test_offline_qdrant_returns_empty_results_without_raising():
    """Verify that offline exceptions are caught and return default failure values."""

    def unavailable(**_kwargs):
        raise ConnectionError("Qdrant is offline")

    client = QdrantClientWrapper(client_factory=unavailable)

    assert client.ensure_collections() is False
    assert not client.search([0.0] * client.vector_size)


def test_search_returns_qdrant_points_and_close_resets_client():
    """Verify searching results from the active connection and client reset on close."""
    fake = FakeQdrantClient(existing={"evidence"})
    client = QdrantClientWrapper(client_factory=lambda **_kwargs: fake)

    results = client.search([0.1] * client.vector_size, limit=1)

    assert results[0].id == "evidence-1"
    client.close()
    assert fake.closed is True
    assert client.client is None


def test_upsert_uses_stable_qdrant_point_id():
    """Verify stable UUID generation from document IDs for upserted vectors."""
    fake = FakeQdrantClient(existing={"evidence"})
    client = QdrantClientWrapper(client_factory=lambda **_kwargs: fake)

    assert client.upsert("log-1", [0.1] * 384, {"type": "log"}) is True
    first_id = fake.upserted[0]["points"][0].id
    assert client.upsert("log-1", [0.2] * 384, {"type": "log"}) is True
    assert fake.upserted[1]["points"][0].id == first_id


def test_qdrant_local_mode_collection_upsert_and_search():
    """Verify correct integration of Wrapper against an in-memory instance."""
    local = QdrantClient(":memory:")
    client = QdrantClientWrapper(client_factory=lambda **_kwargs: local)

    assert client.ensure_collections() is True
    vector = [0.0] * 384
    vector[7] = 1.0
    assert client.upsert("incident-1", vector, {"id": "incident-1"}) is True

    results = client.search(vector, limit=1)
    assert results[0].payload["id"] == "incident-1"
    assert results[0].score == 1.0


def test_api_lifespan_initializes_and_closes_qdrant(monkeypatch):
    """Verify integration of the client wrapper inside FastAPI lifespan events."""
    calls = []
    monkeypatch.setattr(main.neo4j_client, "connect", lambda: None)
    monkeypatch.setattr(main.neo4j_client, "close", lambda: None)
    monkeypatch.setattr(
        main.qdrant_client, "ensure_collections", lambda: calls.append("initialize")
    )
    monkeypatch.setattr(main.qdrant_client, "close", lambda: calls.append("close"))

    with TestClient(main.app) as client:
        assert client.get("/ready").status_code == 200

    assert calls == ["initialize", "close"]
