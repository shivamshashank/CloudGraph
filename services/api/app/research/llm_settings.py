"""Shared helper for reading the LLM provider/key/model saved via the
Settings UI, so research/evaluation code paths (benchmark, self-consistency)
can use whatever key the user has configured without ever needing it typed
into a chat session or an env var by hand — it only travels
UI -> Neo4j -> here -> the orchestrator request.
"""

import logging
from typing import Dict, Optional

from neo4j.exceptions import Neo4jError, ServiceUnavailable

from app.database.neo4j_client import neo4j_client

logger = logging.getLogger(__name__)


def load_stored_llm_settings() -> Dict[str, Optional[str]]:
    """Read the LLM settings saved via `POST /api/v1/settings`.

    Returns an empty dict (not raises) if unavailable — callers should
    treat missing values as "let the orchestrator fall back to its own
    server-side env vars," not as an error.
    """
    try:
        records = neo4j_client.execute_query(
            """
            MATCH (s:Settings {id: "llm_settings"})
            RETURN s.provider as provider, s.api_key as api_key, s.model as model
            LIMIT 1
            """
        )
    except (RuntimeError, ValueError, Neo4jError, ServiceUnavailable) as exc:
        logger.warning("Could not read stored LLM settings: %s", exc)
        return {}
    if not records:
        return {}
    return {
        "provider": records[0].get("provider") or None,
        "api_key": records[0].get("api_key") or None,
        "model": records[0].get("model") or None,
    }
