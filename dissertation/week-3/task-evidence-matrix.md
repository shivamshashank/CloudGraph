# Week 3 Task Evidence Matrix

This file maps every checked Week 3 roadmap task to a concrete repository artifact. Use it as an audit trail when verifying project milestone achievements.

## Neo4j Database & Schema Architecture

| Roadmap Task | Evidence File | What Was Completed |
| --- | --- | --- |
| Deploy Neo4j | [docker-compose.yml](../../docker-compose.yml) | Set up local Neo4j Docker Compose configuration with Bolt (7687) and Browser UI (7474) ports, and APOC plugins enabled. |
| Create graph schema | [graph/schema.cypher](../../graph/schema.cypher) | Defined schema configurations including node unique requirements and secondary indices on timestamps. |
| Design node models | [app/main.py](../../services/api/app/main.py#L34-L74) | Coded Pydantic payloads matching Service, Pod, Node, Deployment, Metric, Log, Commit, and Incident schemas. |
| Design relationships | [app/adapters/](../../services/api/app/adapters/) | Implemented relationship creation logic for `BELONGS_TO`, `RUNS_ON`, `MANAGES`, `GENERATES`, `TRIGGERED_BY`, `CALLS`, and `HAS_STATE_HISTORY` in Neo4j adapter routines. |

## Data Ingestion & Telemetry Parser

| Roadmap Task | Evidence File | What Was Completed |
| --- | --- | --- |
| Metrics ingestion | [adapters/prometheus.py](../../services/api/app/adapters/prometheus.py) | Created handler to parse Prometheus range-based metrics, ingest points, and relate metrics to Pods. |
| Logs ingestion | [adapters/loki.py](../../services/api/app/adapters/loki.py) | Coded Loki logs adapter parsing log bodies, mapping log levels, and creating generates relations. |
| Legacy tracing placeholder | [adapters/tempo.py](../../services/api/app/adapters/tempo.py) | Retained as a compatibility placeholder for older graph concepts. |
| Deployment ingestion | [adapters/webhooks.py](../../services/api/app/adapters/webhooks.py) | Created receiver parsing status revisions, syncing deployment configurations, and matching Git triggers. |
| Git ingestion | [adapters/webhooks.py](../../services/api/app/adapters/webhooks.py) | Wrote Git repository commit receiver extracting SHAs, metadata, and files list. |

## Graph Construction & Entity Linking

| Roadmap Task | Evidence File | What Was Completed |
| --- | --- | --- |
| Entity linking | [adapters/graph_constructor.py](../../services/api/app/adapters/graph_constructor.py#L3-L41) | Created runtime mapping scripts linking Pods to underlying Node hosts, and mapping Pods to parent Services/Deployments. |
| Dependency mapping | [adapters/graph_constructor.py](../../services/api/app/adapters/graph_constructor.py#L43-L63) | Built service dependency mapping logic from runtime relationships. |
| Service relationship generation | [adapters/graph_constructor.py](../../services/api/app/adapters/graph_constructor.py#L65-L87) | Wrote temporal indexing logic to keep historical records of kubernetes configuration status transitions. |

## Testing & QA

| Roadmap Task | Evidence File | What Was Completed |
| --- | --- | --- |
| Graph validation | [tests/test_graph.py](../../services/api/tests/test_graph.py#L69-L95) | Wrote integration checks to verify constraints and validate graph structure constraints. |
| Query performance testing | [tests/test_graph.py](../../services/api/tests/test_graph.py#L101-L115) | Implemented automated latency checks asserting that multi-hop Cypher queries complete within a 100ms threshold. |
| Relationship accuracy testing | [tests/test_graph.py](../../services/api/tests/test_graph.py#L27-L63) | Wrote payload injection tests verifying that properties, relationships, and nodes are properly registered. |
