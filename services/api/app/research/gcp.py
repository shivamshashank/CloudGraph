"""Graph Confidence Propagation (GCP) algorithm class implementation."""

import math
from typing import Any, Dict, List

from app.database.neo4j_client import neo4j_client


class GraphUnavailableError(RuntimeError):
    """Raised when confidence propagation has no graph to run over.

    Subclasses RuntimeError so existing callers that already guard with
    `except RuntimeError` keep working.
    """


EDGE_WEIGHTS = {
    "GENERATES": 0.95,
    "BELONGS_TO": 0.80,
    "CALLS": 0.75,
    "RUNS_ON": 0.60,
    "MANAGES": 0.85,
    "UPDATED_BY": 0.90,
    "TRIGGERED_BY": 0.90,
}


class GraphConfidencePropagator:
    """Propagates belief/confidence scores across Kubernetes graph topology."""

    def __init__(self, max_depth: int = 3, decay_factor: float = 0.85):
        self.max_depth = max_depth
        self.decay_factor = decay_factor

    def _eval_log_conf(self, message: str) -> float:
        msg = message.lower()
        if any(w in msg for w in ["oom", "out of memory", "killed"]):
            return 0.95
        if any(w in msg for w in ["error", "fail", "refused", "timeout"]):
            return 0.85
        return 0.50

    def _eval_metric_conf(self, name: str, val: float) -> float:
        name_lower = name.lower()
        if "cpu" in name_lower and val > 80.0:
            return 0.85
        if ("memory" in name_lower or "mem" in name_lower) and val > 90.0:
            return 0.90
        return 0.40

    def _eval_deployment_conf(self, status: str) -> float:
        status_lower = status.lower()
        if status_lower in ["failed", "progressing", "degraded"]:
            return 0.80
        return 0.60

    def assign_initial_confidence(
        self, labels: List[str], props: Dict[str, Any]
    ) -> float:
        """Assign initial confidence to telemetry evidence nodes."""
        if "confidence" in props:
            try:
                return float(props["confidence"])
            except (ValueError, TypeError):
                pass

        if "Log" in labels:
            return self._eval_log_conf(props.get("message", ""))
        if "Metric" in labels:
            try:
                val = float(props.get("value", 0.0))
            except (ValueError, TypeError):
                val = 0.0
            return self._eval_metric_conf(props.get("name", ""), val)
        if "Commit" in labels:
            return 0.70
        if "Deployment" in labels:
            return self._eval_deployment_conf(props.get("status", ""))

        return 0.0

    def build_adjacency_map(
        self, edges: List[Dict[str, Any]]
    ) -> Dict[str, List[tuple]]:
        """Construct bidirectional adjacency dictionary from Neo4j edges."""
        adjacency = {}
        for edge in edges:
            start, end, rel_type = edge["start_id"], edge["end_id"], edge["type"]
            adjacency.setdefault(start, []).append((end, rel_type))
            adjacency.setdefault(end, []).append((start, rel_type))
        return adjacency

    def propagate_confidence_scores(
        self,
        scores: Dict[str, float],
        init_scores: Dict[str, float],
        adjacency: Dict[str, List[tuple]],
    ) -> Dict[str, float]:
        """Perform confidence score traversal using BFS and Noisy-OR."""
        queue = [(nid, score, 0) for nid, score in init_scores.items() if score > 0.0]
        path_scores = {nid: [] for nid in scores}

        while queue:
            curr_id, curr_conf, curr_depth = queue.pop(0)
            if curr_depth >= self.max_depth:
                continue

            for neighbor, rel_type in adjacency.get(curr_id, []):
                # The edge query reaches one hop further than the node query that
                # produced `scores`, so adjacency can name nodes outside the
                # modelled subgraph. They have no initial confidence and must be
                # skipped; indexing them raised KeyError and 500'd the whole
                # investigation.
                if neighbor not in scores:
                    continue

                propagated = (
                    curr_conf * EDGE_WEIGHTS.get(rel_type, 0.50) * self.decay_factor
                )
                if propagated > 0.01:
                    path_scores[neighbor].append(propagated)

                    # Noisy-OR calculation using math.prod
                    term = (1.0 - init_scores[neighbor]) * math.prod(
                        1.0 - c for c in path_scores[neighbor]
                    )
                    new_c = 1.0 - term

                    if new_c - scores[neighbor] > 0.05:
                        scores[neighbor] = new_c
                        queue.append((neighbor, propagated, curr_depth + 1))
                    else:
                        scores[neighbor] = new_c
        return scores

    def run_propagation(self, pod_name: str) -> Dict[str, Any]:
        """Query Neo4j topology around anomalous pod, propagate confidences.

        Raises GraphUnavailableError if there is no graph to propagate
        over. This used to return a hard-coded {"root_cause": 0.80,
        "recommendation": 0.75} instead, which was actively harmful: 0.80
        clears GCP_CORRECTNESS_THRESHOLD, so a scenario where Neo4j was
        simply unreachable scored as a *correct* GCP result. Confidence
        that was never computed must not be reported as confidence.
        """
        if not neo4j_client.driver:
            raise GraphUnavailableError(
                "Neo4j is unavailable, so no confidence can be propagated "
                f"for pod {pod_name!r}"
            )

        nodes = neo4j_client.execute_query(
            "MATCH (p:Pod {name: $pod_name})-[*0..3]-(n) "
            "RETURN DISTINCT elementId(n) as id, labels(n) as labels, "
            "properties(n) as props",
            {"pod_name": pod_name},
        )
        edges = neo4j_client.execute_query(
            "MATCH (p:Pod {name: $pod_name})-[*0..3]-(a)-[r]-(b) "
            "RETURN DISTINCT elementId(a) as start_id, elementId(b) as end_id, "
            "type(r) as type",
            {"pod_name": pod_name},
        )

        if not nodes:
            # No topology around the pod means nothing propagated, so there is
            # no confidence to report.
            raise GraphUnavailableError(
                f"No graph topology found around pod {pod_name!r}; "
                "nothing to propagate confidence over"
            )

        adjacency = self.build_adjacency_map(edges)
        scores = {}
        init_scores = {}
        target_id = None

        for nd in nodes:
            nid = nd["id"]
            if "Pod" in nd["labels"] and nd["props"].get("name") == pod_name:
                target_id = nid
            init_c = self.assign_initial_confidence(nd["labels"], nd["props"])
            scores[nid] = init_c
            init_scores[nid] = init_c

        scores = self.propagate_confidence_scores(scores, init_scores, adjacency)

        for nid, final_score in scores.items():
            neo4j_client.execute_query(
                "MATCH (n) WHERE elementId(n) = $id SET n.confidence = $score",
                {"id": nid, "score": round(final_score, 3)},
            )

        # 0.0, not 0.80, when the target is absent: a confident default would
        # clear the correctness threshold on a scenario never scored.
        root_cause = round(scores.get(target_id, 0.0), 2)
        return {
            "root_cause": root_cause,
            "recommendation": round(root_cause * 0.90, 2),
        }
