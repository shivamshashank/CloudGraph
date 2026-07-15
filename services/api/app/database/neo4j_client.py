"""Neo4j client wrapper for executing Cypher queries."""

import logging
import os

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

logger = logging.getLogger(__name__)

NEO4J_CONNECTION_ERRORS = (
    RuntimeError,
    ConnectionError,
    OSError,
    ServiceUnavailable,
    Neo4jError,
)


class Neo4jClient:
    """Wrapper class for connection and query execution in Neo4j."""

    def __init__(self):
        """Initialize the client with environment-specified Bolt settings."""
        neo4j_host = os.getenv("NEO4J_HOST")
        if neo4j_host:
            self.uri = os.getenv("NEO4J_URI", f"bolt://{neo4j_host}:7687")
        else:
            self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        # Parse NEO4J_AUTH if present (format: username/password)
        neo4j_auth = os.getenv("NEO4J_AUTH")
        if neo4j_auth and "/" in neo4j_auth:
            parts = neo4j_auth.split("/", 1)
            self.user = parts[0]
            self.password = parts[1]
        else:
            self.user = os.getenv("NEO4J_USER", "neo4j")
            self.password = os.getenv("NEO4J_PASSWORD", "")
        self.driver = None

    def connect(self):
        """Establish the driver connection using standard credentials."""
        if self.driver is not None:
            return self.driver

        try:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            return self.driver
        except NEO4J_CONNECTION_ERRORS:
            self.driver = None
            raise

    def close(self):
        """Close the active driver instance."""
        if self.driver:
            self.driver.close()
            self.driver = None

    def execute_query(self, query: str, parameters: dict = None):
        """Execute a Cypher query on the graph and return results as list of dict."""
        if not self.driver:
            try:
                self.connect()
            except NEO4J_CONNECTION_ERRORS as exc:
                logger.warning(
                    "Neo4j is unavailable; returning offline fallback: %s", exc
                )
                raise RuntimeError("Neo4j unavailable") from exc
        if not self.driver:
            raise RuntimeError("Neo4j unavailable")
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]


# Global singleton client
neo4j_client = Neo4jClient()
