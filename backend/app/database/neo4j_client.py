import os
from neo4j import GraphDatabase


class Neo4jClient:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "cloudgraph_dev_password")
        self.driver = None

    def connect(self):
        if not self.driver:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )

    def close(self):
        if self.driver:
            self.driver.close()
            self.driver = None

    def execute_query(self, query: str, parameters: dict = None):
        if not self.driver:
            self.connect()
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]


# Global singleton client
neo4j_client = Neo4jClient()
