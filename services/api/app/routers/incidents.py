"""Incident routes for manual incidents and triage comments."""

import time
import uuid
from fastapi import APIRouter, HTTPException

from app.database.neo4j_client import neo4j_client
from app.schemas import CommentCreate, IncidentCreate, IncidentUpdate

router = APIRouter()


@router.get("/api/v1/incidents")
def get_incidents():
    """Retrieve all incident records from Neo4j, sorted by timestamp descending."""
    try:
        query = """
        MATCH (i:Incident)
        OPTIONAL MATCH (p:Pod)-[:AFFECTED_BY]->(i)
        RETURN i.id as id,
               i.title as title,
               i.severity as severity,
               i.status as status,
               i.description as cause,
               i.recommendation as remediation,
               i.timestamp as timestamp,
               i.assigned as assigned,
               i.error_logs as error_logs,
               p.name as pod_name
        ORDER BY i.timestamp DESC
        """
        records = neo4j_client.execute_query(query)
        incidents = []
        for r in records:
            incidents.append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "severity": r["severity"],
                    "status": r["status"] or "Active",
                    "cause": r["cause"] or "",
                    "remediation": r["remediation"] or "",
                    "timestamp": (
                        int(r["timestamp"]) if r["timestamp"] else int(time.time())
                    ),
                    "assigned": r["assigned"] or "Unassigned",
                    "error_logs": r["error_logs"] or [],
                    "pod_name": r["pod_name"] or "",
                }
            )
        return {"status": "success", "incidents": incidents}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/v1/incidents")
def create_incident(payload: IncidentCreate):
    """Create a new manual incident record in Neo4j."""
    try:
        incident_id = f"incident-{int(time.time() * 1000)}-{uuid.uuid4().hex[:5]}"
        query = """
        CREATE (i:Incident {
            id: $id,
            title: $title,
            severity: $severity,
            status: $status,
            description: $cause,
            recommendation: $remediation,
            timestamp: $timestamp,
            assigned: $assigned,
            error_logs: $error_logs
        })
        RETURN i.id as id
        """
        neo4j_client.execute_query(
            query,
            {
                "id": incident_id,
                "title": payload.title,
                "severity": payload.severity,
                "status": payload.status,
                "cause": payload.cause,
                "remediation": payload.remediation,
                "timestamp": int(time.time()),
                "assigned": payload.assigned,
                "error_logs": payload.error_logs,
            },
        )
        return {"status": "success", "id": incident_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.patch("/api/v1/incidents/{incident_id}")
def update_incident(incident_id: str, payload: IncidentUpdate):
    """Update status and/or assignee of an incident, adding an audit comment."""
    try:
        check_query = """
        MATCH (i:Incident {id: $id})
        RETURN i.status as status, i.assigned as assigned
        """
        records = neo4j_client.execute_query(check_query, {"id": incident_id})
        if not records:
            raise HTTPException(status_code=404, detail="Incident not found")

        current = records[0]
        old_status = current.get("status") or "Active"
        old_assigned = current.get("assigned") or "Unassigned"

        updates = []
        params = {"id": incident_id}
        if payload.status is not None:
            updates.append("i.status = $status")
            params["status"] = payload.status
        if payload.assigned is not None:
            updates.append("i.assigned = $assigned")
            params["assigned"] = payload.assigned

        if updates:
            update_query = f"""
            MATCH (i:Incident {{id: $id}})
            SET {", ".join(updates)}
            RETURN i.id as id
            """
            neo4j_client.execute_query(update_query, params)

        if payload.status is not None and payload.status != old_status:
            comment_text = (
                f"Status updated from **{old_status}** to **{payload.status}**."
            )
            _add_system_comment(incident_id, comment_text)

        if payload.assigned is not None and payload.assigned != old_assigned:
            comment_text = (
                f"Ownership assigned from **{old_assigned}** to "
                f"**{payload.assigned}**."
            )
            _add_system_comment(incident_id, comment_text)

        return {"status": "success", "id": incident_id}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/api/v1/incidents/{incident_id}/comments")
def get_incident_comments(incident_id: str):
    """Retrieve comments for a specific incident, ordered by timestamp ascending."""
    try:
        query = """
        MATCH (i:Incident {id: $id})
        OPTIONAL MATCH (i)-[:HAS_COMMENT]->(c:Comment)
        RETURN c.author as author, c.text as text, c.timestamp as timestamp
        ORDER BY c.timestamp ASC
        """
        records = neo4j_client.execute_query(query, {"id": incident_id})
        comments = []
        for r in records:
            if r.get("text"):
                comments.append(
                    {
                        "author": r["author"] or "Unknown",
                        "text": r["text"],
                        "timestamp": (
                            int(r["timestamp"])
                            if r["timestamp"]
                            else int(time.time() * 1000)
                        ),
                    }
                )
        return {"status": "success", "comments": comments}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/v1/incidents/{incident_id}/comments")
def add_incident_comment(incident_id: str, payload: CommentCreate):
    """Add a new comment or triage note to an incident."""
    try:
        check_query = "MATCH (i:Incident {id: $id}) RETURN i.id as id"
        if not neo4j_client.execute_query(check_query, {"id": incident_id}):
            raise HTTPException(status_code=404, detail="Incident not found")

        comment_query = """
        MATCH (i:Incident {id: $id})
        CREATE (i)-[:HAS_COMMENT]->(c:Comment {
            author: $author,
            text: $text,
            timestamp: $timestamp
        })
        RETURN c.timestamp as timestamp
        """
        neo4j_client.execute_query(
            comment_query,
            {
                "id": incident_id,
                "author": payload.author,
                "text": payload.text,
                "timestamp": int(time.time() * 1000),
            },
        )
        return {"status": "success"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


def _add_system_comment(incident_id: str, text: str):
    """Helper to insert a system-generated audit log comment."""
    comment_query = """
    MATCH (i:Incident {id: $id})
    CREATE (i)-[:HAS_COMMENT]->(c:Comment {
        author: "System (Triage Engine)",
        text: $text,
        timestamp: $timestamp
    })
    """
    neo4j_client.execute_query(
        comment_query,
        {
            "id": incident_id,
            "text": text,
            "timestamp": int(time.time() * 1000),
        },
    )
