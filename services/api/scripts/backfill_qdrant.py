#!/usr/bin/env python3
"""Backfill Neo4j evidence nodes into the CloudGraph semantic store/Qdrant."""

import argparse
import logging
from typing import Any

from app.database.neo4j_client import neo4j_client
from app.services.semantic_store import SemanticVectorStore


QUERY = """
MATCH (n)
WHERE n:Log OR n:Metric OR n:Incident OR n:Deployment OR n:Commit
RETURN labels(n)[0] AS type, properties(n) AS properties
ORDER BY coalesce(n.timestamp, n.startTime, 0)
"""


def evidence_document(row: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """Convert a Neo4j row representation to a vector document."""
    kind = row["type"]
    props = row["properties"]
    normalized = kind.lower()
    identity = str(
        props.get("id")
        or props.get("sha")
        or props.get("name")
        or props.get("timestamp")
    )

    if normalized == "log":
        text = str(props.get("message", ""))
    elif normalized == "metric":
        text = (
            f"metric summary {props.get('name')} value {props.get('value')} "
            f"timestamp {props.get('timestamp')} labels {props.get('labels', '')}"
        )
        normalized = "metrics-summary"
    elif normalized == "incident":
        text = (
            f"incident {props.get('title', '')}: {props.get('description', '')}; "
            f"severity {props.get('severity', '')}; recommendation "
            f"{props.get('recommendation', '')}"
        )
    elif normalized == "deployment":
        text = (
            f"deployment {props.get('name', '')} "
            f"namespace {props.get('namespace', '')} "
            f"status {props.get('status', '')} "
            f"timestamp {props.get('timestamp', '')}"
        )
    else:
        text = (
            f"commit {props.get('sha', '')} by {props.get('author', '')}: "
            f"{props.get('message', '')}; changed files {props.get('changedFiles', [])}"
        )

    metadata = {
        "type": normalized,
        "label": kind,
        "name": props.get("name") or props.get("title") or props.get("sha") or identity,
        "timestamp": props.get("timestamp") or props.get("startTime"),
    }
    return f"neo4j:{kind}:{identity}", text, metadata


def backfill(
    store: SemanticVectorStore, rows: list[dict[str, Any]], dry_run=False
) -> int:
    """Ingest a list of Neo4j rows into the semantic vector store."""
    count = 0
    for row in rows:
        doc_id, text, metadata = evidence_document(row)
        if not text.strip():
            continue
        if not dry_run:
            store.index_document(doc_id, text, metadata)
        count += 1
    return count


def main() -> int:
    """Parse CLI arguments and run the Neo4j-to-Qdrant backfill job."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--types",
        default="log,metric,incident,deployment,commit",
        help="Comma-separated Neo4j labels to backfill",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    allowed = {item.strip().lower() for item in args.types.split(",") if item.strip()}

    logging.basicConfig(level=logging.INFO)
    try:
        rows = neo4j_client.execute_query(QUERY)
        rows = [row for row in rows if row["type"].lower() in allowed]
        count = backfill(SemanticVectorStore(), rows, dry_run=args.dry_run)
        action = "would backfill" if args.dry_run else "backfilled"
        print(f"{action} {count} evidence documents")
        return 0
    finally:
        neo4j_client.close()


if __name__ == "__main__":
    raise SystemExit(main())
