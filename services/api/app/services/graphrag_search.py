"""GraphRAG search — keyword/vector/hybrid retrieval over the Neo4j graph
and Qdrant semantic index.

Lives outside app.main deliberately: app.research.report_runner and
app.research.evaluation both need to call this as GPCS's semantic-search
evidence source (see GraphProvenanceClaimScorer.score_claims' search_func
contract), and app.main imports app.routers.report which imports
report_runner — importing app.main from either of those would cycle. This
module has no dependency on app.main or the routers package, so both sides
can import it directly at module scope.
"""

import time
from typing import Any

from fastapi import HTTPException

from app.database.neo4j_client import neo4j_client
from app.dependencies import semantic_store
from app.helpers import format_hybrid_result
from app.retrieval.graph_traversal import graph_traversal_retriever
from app.retrieval.hybrid_ranker import hybrid_ranker
from app.schemas import GraphRAGSearchPayload


def _process_graph_search_record(
    record: dict[str, Any],
    query: str,
    depth: int,
    start_time: int | None,
    end_time: int | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse, link, and rank a raw Neo4j search result record."""
    label = record.get("labels")[0] if record.get("labels") else "Node"
    name = record.get("name") or record.get("title") or "unknown"
    status = record.get("status") or "Active"
    graph_hits = [
        {
            "id": record.get("id"),
            "labels": record.get("labels") or [],
            "properties": {
                **(dict(record.get("properties") or {})),
                "name": name,
                "status": status,
            },
            "hop_distance": 0,
            "relationships": [],
            "path": [
                {
                    "id": record.get("id"),
                    "labels": record.get("labels") or [],
                    "name": name,
                }
            ],
        }
    ]

    evidence_chain = [{"type": "entity", "label": label, "name": name}]

    if label in {"Incident", "Pod"}:
        graph_context = graph_traversal_retriever.retrieve(
            record.get("id"),
            depth=depth,
            start_time=start_time,
            end_time=end_time,
            limit=20,
        )
        graph_hits.extend(graph_context)
        related = [
            {
                "rel": " -> ".join(item["relationships"]),
                "related_name": item["name"],
                "related_labels": item["labels"],
                "hop_distance": item["hop_distance"],
                "path": item["path"],
                "properties": item["properties"],
            }
            for item in graph_context
        ]
    else:
        related = neo4j_client.execute_query(
            """
            MATCH (n)-[r]-(m)
            WHERE elementId(n) = $node_id
            RETURN type(r) as rel,
                   coalesce(m.name, m.title, m.status, m.id) as related_name,
                   labels(m) as related_labels
            LIMIT 6
            """,
            {"node_id": record.get("id")},
        )

    context = []
    for edge in related:
        evidence_chain.append(
            {
                "type": "relation",
                "label": edge.get("rel") or "RELATED_TO",
                "name": edge.get("related_name") or "unknown",
                "hop_distance": edge.get("hop_distance", 1),
            }
        )
        context.append(
            {
                "name": edge.get("related_name") or "unknown",
                "type": str((edge.get("related_labels") or ["Node"])[0]).lower(),
                "relationship": edge.get("rel") or "RELATED_TO",
                "hop_distance": edge.get("hop_distance", 1),
                "path": edge.get("path", []),
            }
        )

    if not context:
        context.append(
            {
                "name": "No adjacent graph nodes",
                "type": "graph",
                "relationship": "none",
            }
        )

    score = 0.6
    if query.lower() in name.lower():
        score += 0.2
    if status and query.lower() in status.lower():
        score += 0.1
    if label.lower() in {"incident", "pod", "service"}:
        score += 0.05

    return {
        "id": record.get("id"),
        "label": label,
        "type": label.lower(),
        "name": name,
        "status": status,
        "evidence_chain": evidence_chain,
        "context": context[:3],
        "related": related,
        "score": round(min(0.99, score + min(0.15, len(context) * 0.03)), 2),
        "sources": ["graph"],
        "detail": (
            f"Matched the current graph context using the term "
            f"'{query}' and expanded nearby nodes for retrieval."
        ),
    }, graph_hits


def _build_search_payload(
    query: str,
    search_method: str,
    payload: GraphRAGSearchPayload,
    data: dict,
) -> dict:
    """Construct search result payload based on chosen method."""
    if search_method == "keyword":
        return {
            "status": "success",
            "query": query,
            "method": search_method,
            "retrieval": {
                "depth": payload.depth,
                "start_time": payload.start_time,
                "end_time": payload.end_time,
                "ranking_formula": "keyword-only",
            },
            "results": data["results"],
        }
    if search_method == "vector":
        return {
            "status": "success",
            "query": query,
            "method": search_method,
            "retrieval": {
                "depth": payload.depth,
                "start_time": payload.start_time,
                "end_time": payload.end_time,
                "ranking_formula": "vector-only",
            },
            "results": data["semantic_results"],
        }

    ref_time = payload.end_time or int(time.time())
    ranked = hybrid_ranker.rank(
        data["semantic_hits"],
        data["graph_hits"],
        reference_time=ref_time,
        limit=10,
    )
    hybrid_items = [format_hybrid_result(item) for item in ranked]
    if not hybrid_items:
        hybrid_items = data["semantic_results"] + hybrid_items
        hybrid_items.sort(key=lambda item: item.get("score", 0.0), reverse=True)

    return {
        "status": "success",
        "query": query,
        "method": search_method,
        "retrieval": {
            "depth": payload.depth,
            "start_time": payload.start_time,
            "end_time": payload.end_time,
            "ranking_formula": hybrid_ranker.FORMULA,
        },
        "results": hybrid_items,
    }


def graphrag_search(payload: GraphRAGSearchPayload, method: str | None = None):
    """Search graphrag context by keyword, semantic vector, or hybrid
    ranking. Registered as the /api/v1/graphrag/search route handler in
    app.main, and called directly (not over HTTP) as GPCS's search_func —
    see this module's docstring for why it lives here rather than in
    app.main."""
    try:
        query = payload.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        search_method = (method or payload.method or "hybrid").strip().lower()
        if search_method not in {"keyword", "vector", "hybrid"}:
            raise HTTPException(
                status_code=400,
                detail="method must be one of: keyword, vector, hybrid",
            )

        raw_results = neo4j_client.execute_query(
            """
            MATCH (n)
            WHERE any(label in labels(n) WHERE label IN [
                'Pod', 'Service', 'Deployment', 'Incident', 'Node', 'Commit'
            ])
              AND any(
                word IN split(toLower($query), ' ') WHERE
                size(word) > 2 AND (
                  toLower(coalesce(n.name, '')) CONTAINS word
                  OR toLower(coalesce(n.title, '')) CONTAINS word
                  OR toLower(coalesce(n.status, '')) CONTAINS word
                  OR toLower(coalesce(n.message, '')) CONTAINS word
                )
              )
            WITH n
            RETURN labels(n) as labels, n.name as name, n.status as status,
                   n.title as title, properties(n) as properties, elementId(n) as id
            ORDER BY CASE WHEN n.status IN [
                'CrashLoopBackOff', 'ERROR', 'Critical'
            ] THEN 1 ELSE 2 END, n.name
            LIMIT 5
            """,
            {"query": query},
        )

        semantic_hits = []
        if search_method in {"vector", "hybrid"}:
            semantic_hits = semantic_store.search(query, limit=5)

        results = []
        graph_hits = []
        for record in raw_results:
            res_and_hts = _process_graph_search_record(
                record,
                query,
                payload.depth,
                payload.start_time,
                payload.end_time,
            )
            results.append(res_and_hts[0])
            graph_hits.extend(res_and_hts[1])

        semantic_results = [
            {
                "id": hit["id"],
                "label": hit["metadata"].get("label", "Node"),
                "type": str(hit["metadata"].get("label", "Node")).lower(),
                "name": hit["metadata"].get("name", hit["id"]),
                "status": hit["metadata"].get("status", "Active"),
                "evidence_chain": [
                    {
                        "type": "semantic",
                        "label": "Embedding",
                        "name": hit["text"],
                    }
                ],
                "context": [
                    {
                        "name": "Semantic text match",
                        "type": "semantic",
                        "relationship": "matched_text",
                    }
                ],
                "related": [],
                "score": round(hit["score"], 3),
                "sources": ["vector"],
                "detail": hit["text"],
            }
            for hit in semantic_hits
        ]

        return _build_search_payload(
            query,
            search_method,
            payload,
            {
                "results": results,
                "semantic_results": semantic_results,
                "semantic_hits": semantic_hits,
                "graph_hits": graph_hits,
            },
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
