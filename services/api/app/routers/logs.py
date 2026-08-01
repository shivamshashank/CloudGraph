"""Logs routes for retrieving and persisting AIOps live agent logs."""

from fastapi import APIRouter, HTTPException

from app.database.neo4j_client import neo4j_client
from app.schemas import LogEntryPayload

router = APIRouter()


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
