"""Dependency injection for CloudGraph API."""

from app.services.semantic_store import SemanticVectorStore

semantic_store = SemanticVectorStore()
