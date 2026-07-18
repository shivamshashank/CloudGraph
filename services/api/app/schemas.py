"""Pydantic payload schemas used by the FastAPI route handlers."""

from typing import Any, List
from pydantic import BaseModel, Field, model_validator


class MetricPayload(BaseModel):
    """Payload model for Prometheus metrics ingestion."""

    pod_id: str
    pod_name: str
    metric_name: str
    value: float
    timestamp: int
    labels: dict

    def to_dict(self) -> dict[str, Any]:
        """Convert payload model to dictionary representation."""
        return self.model_dump()

    def get_summary(self) -> str:
        """Generate human-readable summary of the metric payload."""
        return f"{self.metric_name}: {self.value}"


class LogPayload(BaseModel):
    """Payload model for Loki logs ingestion."""

    pod_id: str
    pod_name: str
    message: str
    level: str
    timestamp: int
    container_name: str

    def to_dict(self) -> dict[str, Any]:
        """Convert payload model to dictionary representation."""
        return self.model_dump()

    def get_summary(self) -> str:
        """Generate human-readable summary of the log payload."""
        return f"[{self.level.upper()}] {self.message[:60]}"


class GitCommitPayload(BaseModel):
    """Payload model for git webhook commit events."""

    sha: str
    author: str
    message: str
    timestamp: int
    changed_files: List[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert payload model to dictionary representation."""
        return self.model_dump()

    def get_summary(self) -> str:
        """Generate human-readable summary of the commit payload."""
        return f"Commit {self.sha[:7]} by {self.author}"


class ArgoCDDeploymentPayload(BaseModel):
    """Payload model for ArgoCD sync webhooks."""

    app_name: str
    namespace: str
    status: str
    revision: str
    timestamp: int

    def to_dict(self) -> dict[str, Any]:
        """Convert payload model to dictionary representation."""
        return self.model_dump()

    def get_summary(self) -> str:
        """Generate human-readable summary of the deployment payload."""
        return f"Deployment {self.app_name} status: {self.status}"


class PodStatusPayload(BaseModel):
    """Payload model for explicit container/pod state changes."""

    pod_id: str
    status: str
    timestamp: int

    def to_dict(self) -> dict[str, Any]:
        """Convert payload model to dictionary representation."""
        return self.model_dump()

    def get_summary(self) -> str:
        """Generate human-readable summary of the pod status payload."""
        return f"Pod {self.pod_id} changed to {self.status}"


class InvestigationTrigger(BaseModel):
    """Trigger payload configuration for running automated fault investigation."""

    namespace: str = "cloudgraph-system"
    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert payload model to dictionary representation."""
        return self.model_dump()

    def get_summary(self) -> str:
        """Generate human-readable summary of the trigger payload."""
        return f"Trigger investigation namespace: {self.namespace}"


class EvidenceTrigger(BaseModel):
    """Payload to request local evidence node lookup for a specific pod."""

    pod_name: str
    namespace: str = "cloudgraph-system"

    def to_dict(self) -> dict[str, Any]:
        """Convert payload model to dictionary representation."""
        return self.model_dump()

    def get_summary(self) -> str:
        """Generate human-readable summary of the evidence payload."""
        return f"Fetch evidence for pod: {self.pod_name}"


class GraphSearchPayload(BaseModel):
    """Payload for basic keyword search requests over the graph topology."""

    query: str
    namespace: str = "cloudgraph-system"

    def to_dict(self) -> dict[str, Any]:
        """Convert payload model to dictionary representation."""
        return self.model_dump()

    def get_summary(self) -> str:
        """Generate human-readable summary of the search payload."""
        return f"Graph search query: {self.query}"


class GraphRetrievePayload(BaseModel):
    """Payload for neighborhood sub-graph context extraction."""

    query: str
    namespace: str = "cloudgraph-system"

    def to_dict(self) -> dict[str, Any]:
        """Convert payload model to dictionary representation."""
        return self.model_dump()

    def get_summary(self) -> str:
        """Generate human-readable summary of the retrieve payload."""
        return f"Graph retrieve query: {self.query}"


class GraphRAGSearchPayload(BaseModel):
    """Options and parameters configuration for the GraphRAG pipeline search."""

    query: str
    namespace: str = "cloudgraph-system"
    depth: int = Field(default=2, ge=1, le=4)
    start_time: int | None = None
    end_time: int | None = None
    method: str = Field(default="hybrid")

    @model_validator(mode="after")
    def validate_time_window(self):
        """Validate search temporal window bounds correctness."""
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.start_time > self.end_time
        ):
            raise ValueError("start_time must be less than or equal to end_time")
        return self

    @model_validator(mode="after")
    def validate_method(self):
        """Validate method name matches supported strategies."""
        allowed_methods = {"keyword", "vector", "hybrid"}
        normalized_method = self.method.strip().lower()
        if normalized_method not in allowed_methods:
            raise ValueError("method must be one of: keyword, vector, hybrid")
        self.method = normalized_method
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert payload model to dictionary representation."""
        return self.model_dump()

    def get_summary(self) -> str:
        """Generate human-readable summary of the search config."""
        return f"GraphRAG search query '{self.query}' method: {self.method}"


class TracePayload(BaseModel):
    """Payload model for Tempo trace spans ingestion."""

    pod_id: str
    pod_name: str
    span_id: str
    trace_id: str
    parent_span_id: str
    service_name: str
    duration: float
    timestamp: int
    status: str

    def to_dict(self) -> dict[str, Any]:
        """Convert payload model to dictionary representation."""
        return self.model_dump()

    def get_summary(self) -> str:
        """Generate human-readable summary of the trace payload."""
        return (
            f"Trace {self.trace_id} Span {self.span_id}: "
            f"{self.service_name} ({self.duration}ms)"
        )
