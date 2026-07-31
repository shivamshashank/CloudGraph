"""Settings routes for LLM provider credentials and model configurations."""

from fastapi import APIRouter, HTTPException

from app.database.neo4j_client import neo4j_client
from app.schemas import SettingsPayload

router = APIRouter()


@router.get("/api/v1/settings")
def get_settings():
    """Retrieve LLM settings from Neo4j."""
    try:
        query = """
        MATCH (s:Settings {id: "llm_settings"})
        RETURN s.provider as provider, s.api_key as api_key, s.model as model
        LIMIT 1
        """
        records = neo4j_client.execute_query(query)
        if records:
            return {
                "status": "success",
                "settings": {
                    "provider": records[0]["provider"] or "",
                    "api_key": records[0]["api_key"] or "",
                    "model": records[0]["model"] or "",
                },
            }
        return {"status": "success", "settings": {}}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/api/v1/settings")
def save_settings(payload: SettingsPayload):
    """Save LLM settings to Neo4j."""
    try:
        query = """
        MERGE (s:Settings {id: "llm_settings"})
        SET s.provider = $provider,
            s.api_key = $api_key,
            s.model = $model
        RETURN s.id as id
        """
        neo4j_client.execute_query(
            query,
            {
                "provider": payload.provider,
                "api_key": payload.api_key,
                "model": payload.model,
            },
        )
        return {"status": "success"}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/api/v1/settings")
def clear_settings():
    """Clear LLM settings from Neo4j."""
    try:
        query = """
        MATCH (s:Settings {id: "llm_settings"})
        DETACH DELETE s
        """
        neo4j_client.execute_query(query)
        return {"status": "success"}
    except (RuntimeError, ValueError, KeyError, TypeError, AttributeError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
