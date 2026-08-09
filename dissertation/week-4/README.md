# Week 4: GraphRAG Retrieval

## Part 1.2: Embedding Pipeline

CloudGraph uses the local
[`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
model. It produces 384-dimensional normalized embeddings suitable for cosine
similarity. The model is downloaded while building the API image, so a running
CloudGraph deployment does not call a hosted embedding API and remains usable
without internet access.

The model can be changed with `EMBEDDING_MODEL`. If its output is not 384
dimensions, set `QDRANT_VECTOR_SIZE` to the same dimension before creating the
collection.

## Storage and Offline Behavior

`SemanticVectorStore` keeps its existing JSON file store as a fallback while
using Qdrant as the primary vector index. When the sentence-transformer and
Qdrant are available, evidence is written to both stores and searches use
Qdrant. If Qdrant is unavailable, cosine search runs against the JSON store. If
the local model cannot load, CloudGraph uses its deterministic hashed file-only
fallback and does not insert those fallback vectors into Qdrant.

## Evidence Chunking

| Evidence | Strategy |
| --- | --- |
| Logs | Preserve complete lines; group adjacent lines up to 1,200 characters. |
| Metric summaries | Store one aggregate-window summary; raw time-series points are not split into isolated chunks. |
| Incidents | Keep coherent paragraphs together, splitting long narratives at 1,600 characters. |
| Deployments and commits | Keep each change and its metadata as one causal unit. |

Live API ingestion indexes logs, metric summaries, Git commits, Argo CD
deployments, and generated incidents. Each Qdrant payload includes its evidence
type, original Neo4j/source ID, chunk index, display metadata, and text.

## Backfill Existing Neo4j Evidence

From `services/api`, run:

```bash
python scripts/backfill_qdrant.py
```

Preview the number of eligible nodes without embedding them:

```bash
python scripts/backfill_qdrant.py --dry-run
```

Restrict the backfill when required:

```bash
python scripts/backfill_qdrant.py --types log,incident,metric
```

The command reads existing `Log`, `Metric`, `Incident`, `Deployment`, and
`Commit` nodes, formats each as typed evidence, embeds it locally, and upserts it
into the unified Qdrant `evidence` collection.

## Part 1.3: Graph Traversal Retrieval

`GraphTraversalRetriever` starts from a Neo4j `Incident` or `Pod` and expands
the operational relationships `BELONGS_TO`, `RUNS_ON`, `MANAGES`, `GENERATES`,
`AFFECTED_BY`, `AFFECTS`, `TRIGGERED_BY`, `HAS_STATE_HISTORY`, `CALLS`, and
`DEPENDS_ON`. The default depth is two hops and callers may request one to four
hops. The bound is validated before it is interpolated into Cypher.

Time-bearing nodes (`Log`, `Metric`, `Trace`, `Commit`, `Deployment`,
`Incident`, and `StateChange`) must fall inside the retrieval window. Callers
can send `start_time` and `end_time` as Unix timestamps. If either is omitted,
the retriever derives that boundary from the incident seed—or the incident
connected to a pod seed—using `startTime`, `endTime`, or `timestamp` and a
one-hour default configured through `GRAPHRAG_TIME_WINDOW_SECONDS`.

Example:

```http
POST /api/v1/graphrag/search
Content-Type: application/json

{
  "query": "payment database failure",
  "depth": 3,
  "start_time": 1751302800,
  "end_time": 1751306400
}
```

Each graph result exposes `hop_distance`, the relationship sequence, and the
node path so later hybrid ranking and UI explainability can use the traversal
without issuing another graph query.

## Part 1.4: Hybrid Ranking

CloudGraph merges Qdrant vector hits and Neo4j traversal evidence by their
source IDs, then ranks the unified candidates with:

```text
hybrid_score = 0.50 * vector_similarity
             + 0.30 * graph_proximity
             + 0.20 * recency
```

All components are normalized to `[0, 1]`:

- `vector_similarity` is the cosine similarity returned by Qdrant, clamped to
  the unit interval.
- `graph_proximity = 1 / (1 + hop_distance)`, so a seed scores `1.0`, a
  one-hop neighbour `0.5`, a two-hop neighbour `0.333`, and so on.
- `recency = exp(-ln(2) * age_seconds / half_life_seconds)`. The default
  half-life is one hour and can be changed through
  `GRAPHRAG_RECENCY_HALF_LIFE_SECONDS`.

A missing vector path, graph path, or timestamp contributes zero for that
component rather than inventing evidence. The query's `end_time` is used as the
recency reference when supplied; otherwise the current server time is used.

Every result includes `score_breakdown`, containing each raw score, weight,
weighted contribution, hop distance, evidence timestamp, age, half-life, final
score, and formula. `ranking_rationale` also provides short human-readable
sentences suitable for the UI evidence panel and dissertation RQ3 analysis.

## Part 1.5: API Surface

Both retrieval endpoints now accept a `method` selector so the same query can be
run as `keyword`, `vector`, or `hybrid`. The request body can include a
`method` field, and the same value can also be supplied as a query parameter.

Example:

```http
POST /api/v1/graphrag/search?method=hybrid
Content-Type: application/json

{
  "query": "payment database failure"
}
```

`/api/v1/investigations/trigger` now asks the retrieval layer for ranked
context around the anomalous pod before falling back to the existing rule-based
investigation summary if retrieval is unavailable.
