# Week 3 Knowledge Graph Development Pack

This directory contains the Week 3 deliverables and verification details from `ROADMAP.md`.

## Deliverables Mapped to Repository Code

| Deliverable | Location in Repository | Purpose |
| --- | --- | --- |
| **Neo4j Cypher Schema** | [graph/schema.cypher](../../graph/schema.cypher) | Defines node labels, property constraints, uniqueness constraints, and search indexes for telemetry nodes. |
| **Local Services Orchestration** | [docker-compose.yml](../../docker-compose.yml) | Provisions Neo4j community edition (with APOC plugin enabled) and Qdrant container configurations locally. |
| **Database Connection Handler** | [database/neo4j_client.py](../../backend/app/database/neo4j_client.py) | Python singleton driver to initialize, connect, close, and query the local/remote Neo4j cluster. |
| **Prometheus Telemetry Adapter** | [adapters/prometheus.py](../../backend/app/adapters/prometheus.py) | Ingests metric timeseries points, merges Pod configurations, and maps the `(:Pod)-[:GENERATES]->(:Metric)` relationship. |
| **Loki Logging Adapter** | [adapters/loki.py](../../backend/app/adapters/loki.py) | Ingests Loki log lines, normalizes severities, and maps the `(:Pod)-[:GENERATES]->(:Log)` relationship. |
| **Tempo Tracing Adapter** | [adapters/tempo.py](../../backend/app/adapters/tempo.py) | Ingests trace spans, connects spans within trace trees via parent/child relations, and links trace points to generating Pods. |
| **Webhook Event Receivers** | [adapters/webhooks.py](../../backend/app/adapters/webhooks.py) | Receives triggers from Git repositories and ArgoCD status payloads to map `(:Commit)-[:TRIGGERED_BY]->(:Deployment)` relations. |
| **Graph Construction Engine** | [adapters/graph_constructor.py](../../backend/app/adapters/graph_constructor.py) | Performs entity linking, matches runtime dependencies, tracks historical state changes, and builds service-to-service calls maps. |
| **FastAPI Backend Server** | [app/main.py](../../backend/app/main.py) | Exposes REST ingestion endpoints `/api/v1/telemetry/*`, webhook hooks, health checks, and lifecycle managers using `lifespan`. |

## Verification and Testing

### 1. Automated Integration Tests

The test suite at [tests/test_graph.py](../../backend/tests/test_graph.py) contains mock-based and database-live tests to verify schema integrity:

- **Health Verification**: Assures the REST health probe and Neo4j connectivity are functional.
- **Payload Ingestion**: Asserts correct payload mapping and execution path responses.
- **Uniqueness Constraints**: Verifies database-side schema definitions match requirements.
- **Latency Benchmarks**: Runs traversal queries to assert that queries run within a 100ms budget.

To run tests:

```bash
PYTHONPATH=backend backend/.venv/bin/pytest
```

### 2. Manual Schema Verification

Connect to the Neo4j Browser UI at [http://localhost:7474](http://localhost:7474) (Username: `neo4j`, Password: `cloudgraph_dev_password`) and run:

```cypher
SHOW CONSTRAINTS;
```

This confirms that the 9 constraint rules are correctly loaded.
