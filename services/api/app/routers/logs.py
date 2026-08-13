"""Logs routes for retrieving and persisting AIOps live agent logs."""

import logging

from fastapi import APIRouter, HTTPException

from app.adapters.k8s_discovery import K8S_ERRORS, _resolve_pod_status, get_k8s_client
from app.database.neo4j_client import neo4j_client
from app.schemas import LogEntryPayload

logger = logging.getLogger(__name__)

router = APIRouter()


def _classify(line: str) -> str:
    """Classify a log line by severity using the same rules as ingestion."""
    lowered = line.lower()
    if "error" in lowered or "fail" in lowered or "exception" in lowered:
        return "ERROR"
    if "warn" in lowered:
        return "WARN"
    return "INFO"


@router.get("/api/v1/logs/pods")
def get_pod_logs(namespace: str | None = None, tail: int = 20):
    """Return real stdout/stderr read from the cluster's pods.

    The Log Stream page used to generate its own lines from a hardcoded list
    of plausible-sounding messages, which meant it displayed invented crash
    and OOM text for healthy pods. This serves the actual container output
    instead, so what the page shows can be checked against `kubectl logs`.
    """
    try:
        apis = get_k8s_client()
    except K8S_ERRORS as exc:
        raise HTTPException(
            status_code=503, detail=f"Kubernetes API unavailable: {exc}"
        ) from exc
    if not apis:
        raise HTTPException(
            status_code=503,
            detail="Kubernetes configuration unavailable; cannot read pod logs",
        )
    v1 = apis[0]

    tail = max(1, min(tail, 200))
    entries: list[dict] = []
    try:
        pod_list = (
            v1.list_namespaced_pod(namespace)
            if namespace
            else v1.list_pod_for_all_namespaces()
        )
    except K8S_ERRORS as exc:
        raise HTTPException(
            status_code=503, detail=f"Could not list pods: {exc}"
        ) from exc

    for pod in pod_list.items:
        if not (pod.spec and pod.spec.containers):
            continue
        status = _resolve_pod_status(pod)
        if status != "Running":
            continue
        container = pod.spec.containers[0].name
        try:
            raw = v1.read_namespaced_pod_log(
                name=pod.metadata.name,
                namespace=pod.metadata.namespace,
                container=container,
                tail_lines=tail,
                timestamps=True,
            )
        except K8S_ERRORS as exc:
            # One unreadable pod must not blank the whole feed.
            logger.debug("Could not read logs for %s: %s", pod.metadata.name, exc)
            continue

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            timestamp, _, message = line.partition(" ")
            if not message:
                timestamp, message = "", line
            entries.append(
                {
                    "timestamp": timestamp,
                    "source": pod.metadata.name,
                    "level": _classify(message),
                    "message": message,
                }
            )

    entries.sort(key=lambda e: e["timestamp"])
    return {"status": "success", "logs": entries, "count": len(entries)}


@router.get("/api/v1/logs")
def get_log_history():
    """Retrieve all stored live logs from Neo4j."""
    try:
        query = """
        MATCH (l:LiveLog)
        RETURN l.timestamp as timestamp,
               l.source as source,
               l.level as level,
               l.message as message,
               l.created_at as created_at
        ORDER BY l.created_at ASC
        """
        records = neo4j_client.execute_query(query)
        logs = [
            {
                "timestamp": r["timestamp"] or "",
                "source": r["source"] or "",
                "level": r["level"] or "",
                "message": r["message"] or "",
            }
            for r in records
        ]
        return {"status": "success", "logs": logs}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/v1/logs")
def add_log_entry(payload: LogEntryPayload):
    """Save a live log entry to Neo4j."""
    try:
        query = """
        CREATE (l:LiveLog {
            timestamp: $timestamp,
            source: $source,
            level: $level,
            message: $message,
            created_at: timestamp()
        })
        WITH l
        MATCH (old:LiveLog)
        WITH count(old) as cnt, old
        ORDER BY old.created_at ASC
        LIMIT CASE WHEN cnt > 5000 THEN cnt - 5000 ELSE 0 END
        DETACH DELETE old
        """
        neo4j_client.execute_query(
            query,
            {
                "timestamp": payload.timestamp,
                "source": payload.source,
                "level": payload.level,
                "message": payload.message,
            },
        )
        return {"status": "success"}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api/v1/logs")
def clear_log_history():
    """Clear all live logs from Neo4j."""
    try:
        query = """
        MATCH (l:LiveLog)
        DETACH DELETE l
        """
        neo4j_client.execute_query(query)
        return {"status": "success"}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
