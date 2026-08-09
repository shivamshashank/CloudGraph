"""Relationship-aware, temporal Neo4j neighborhood retrieval."""

import os
from typing import Any

from app.database.neo4j_client import neo4j_client


RELATIONSHIP_TYPES = (
    "BELONGS_TO|RUNS_ON|MANAGES|GENERATES|AFFECTED_BY|AFFECTS|"
    "TRIGGERED_BY|HAS_STATE_HISTORY|CALLS|DEPENDS_ON"
)
MIN_DEPTH = 1
MAX_DEPTH = 4


class GraphTraversalRetriever:
    """Expand an Incident or Pod seed into a bounded evidence neighborhood."""

    def __init__(self, client=None, default_window_seconds: int | None = None):
        self.client = client or neo4j_client
        self.default_window_seconds = default_window_seconds or int(
            os.getenv("GRAPHRAG_TIME_WINDOW_SECONDS", "3600")
        )

    def get_default_window_seconds(self) -> int:
        """Return the default window duration in seconds."""
        return self.default_window_seconds

    def retrieve(
        self,
        seed_id: str,
        *,
        depth: int = 2,
        limit: int = 50,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """Retrieve multi-hop evidence neighborhood starting from a seed ID."""
        start_time = kwargs.get("start_time")
        end_time = kwargs.get("end_time")
        if not MIN_DEPTH <= depth <= MAX_DEPTH:
            raise ValueError(f"depth must be between {MIN_DEPTH} and {MAX_DEPTH}")
        if start_time is not None and end_time is not None and start_time > end_time:
            raise ValueError("start_time must be less than or equal to end_time")
        if limit < 1:
            raise ValueError("limit must be positive")

        # Depth is interpolated only after strict integer range validation because
        # Neo4j does not accept a parameter for variable-length path bounds.
        query = f"""
        MATCH (seed)
        WHERE (seed:Incident OR seed:Pod OR seed:Deployment OR seed:Node)
          AND (
            elementId(seed) = $seed_id
            OR seed.id = $seed_id
            OR seed.name = $seed_id
          )
        OPTIONAL MATCH (seed)-[:AFFECTED_BY|AFFECTS]-(seed_incident:Incident)
        WITH seed, head(collect(seed_incident)) AS seed_incident
        WITH seed, seed_incident,
             coalesce(
               $start_time,
               seed.startTime,
               seed_incident.startTime,
               CASE WHEN coalesce(seed.timestamp, seed_incident.timestamp) IS NOT NULL
                    THEN (
                        coalesce(seed.timestamp, seed_incident.timestamp)
                        - $window_seconds
                    )
                    ELSE null END
             ) AS window_start,
             coalesce(
               $end_time,
               seed.endTime,
               seed_incident.endTime,
               CASE WHEN coalesce(seed.timestamp, seed_incident.timestamp) IS NOT NULL
                    THEN (
                        coalesce(seed.timestamp, seed_incident.timestamp)
                        + $window_seconds
                    )
                    ELSE null END
             ) AS window_end
        MATCH path = (seed)-[:{RELATIONSHIP_TYPES}*1..{depth}]-(context)
        WHERE context <> seed
          AND all(path_node IN nodes(path) WHERE
            NOT (
              path_node:Log OR path_node:Metric OR path_node:Trace OR
              path_node:Commit OR path_node:Deployment OR
              path_node:Incident OR path_node:StateChange
            )
            OR coalesce(path_node.timestamp, path_node.startTime) IS NULL
            OR (
              (window_start IS NULL OR
               coalesce(path_node.timestamp, path_node.startTime) >= window_start)
              AND
              (window_end IS NULL OR
               coalesce(path_node.timestamp, path_node.startTime) <= window_end)
            )
          )
        WITH context, path
        ORDER BY length(path) ASC
        WITH context, head(collect(path)) AS shortest_path
        RETURN elementId(context) AS id,
               labels(context) AS labels,
               properties(context) AS properties,
               length(shortest_path) AS hop_distance,
               [rel IN relationships(shortest_path) | type(rel)] AS relationships,
               [node IN nodes(shortest_path) | {{
                 id: elementId(node),
                 labels: labels(node),
                 name: coalesce(node.name, node.title, node.message, node.id)
               }}] AS path
        ORDER BY hop_distance ASC, id ASC
        LIMIT $limit
        """
        rows = self.client.execute_query(
            query,
            {
                "seed_id": seed_id,
                "start_time": start_time,
                "end_time": end_time,
                "window_seconds": self.default_window_seconds,
                "limit": limit,
            },
        )
        return [self._normalize(row) for row in rows]

    @staticmethod
    def _normalize(row: dict[str, Any]) -> dict[str, Any]:
        properties = dict(row.get("properties") or {})
        labels = list(row.get("labels") or [])
        return {
            "id": row.get("id"),
            "labels": labels,
            "type": (labels[0] if labels else "Node").lower(),
            "name": (
                properties.get("name")
                or properties.get("title")
                or properties.get("message")
                or properties.get("id")
                or row.get("id")
            ),
            "properties": properties,
            "hop_distance": int(row.get("hop_distance") or 0),
            "relationships": list(row.get("relationships") or []),
            "path": list(row.get("path") or []),
        }


graph_traversal_retriever = GraphTraversalRetriever()
