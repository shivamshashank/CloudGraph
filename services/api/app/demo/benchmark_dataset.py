"""Ground-truth evaluation dataset for dynamic AIOps benchmark scoring."""

from typing import Any, Dict, List

BENCHMARK_GROUND_TRUTH_SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "scenario-01",
        "query": "payment-service pod OOMKilled memory limit exceeded",
        "target_service": "payment-service",
        "target_entity": "payment-service-pod-7f",
        "root_cause": "oom",
        "expected_tags": ["oom", "memory", "killed", "payment"],
        "ground_truth_claims": [
            "Pod payment-service failed due to OOMKilled",
            "Container memory usage exceeded 512Mi limit",
        ],
    },
    {
        "id": "scenario-02",
        "query": "auth-service database connection timeout postgres",
        "target_service": "auth-service",
        "target_entity": "auth-service-pod-8b",
        "root_cause": "db_timeout",
        "expected_tags": ["timeout", "auth", "postgres", "db"],
        "ground_truth_claims": [
            "Auth service failed to connect to database host",
            "Connection pool exhausted on postgres port 5432",
        ],
    },
    {
        "id": "scenario-03",
        "query": "frontend-service high CPU utilization 98% latency spike",
        "target_service": "frontend-service",
        "target_entity": "node-worker-01",
        "root_cause": "cpu_throttling",
        "expected_tags": ["cpu", "utilization", "frontend", "latency"],
        "ground_truth_claims": [
            "Node worker-01 CPU throttling active",
            "Frontend service response time degraded to 1200ms",
        ],
    },
    {
        "id": "scenario-04",
        "query": "billing-service ImagePullBackOff image registry error",
        "target_service": "billing-service",
        "target_entity": "billing-service-deploy",
        "root_cause": "image_pull",
        "expected_tags": ["image_pull", "billing", "backoff", "deploy"],
        "ground_truth_claims": [
            "Billing service deployment container failed image fetch",
            "Registry authentication credentials missing or invalid",
        ],
    },
    {
        "id": "scenario-05",
        "query": "api-gateway HTTP 500 internal server error cascade",
        "target_service": "api-gateway",
        "target_entity": "api-gateway-service",
        "root_cause": "http_500",
        "expected_tags": ["http_500", "gateway", "error", "cascade"],
        "ground_truth_claims": [
            "API Gateway returned 500 error due to upstream timeout",
            "Upstream service auth-service failed health check",
        ],
    },
    {
        "id": "scenario-06",
        "query": "redis-cache connection refused port 6379",
        "target_service": "redis-cache",
        "target_entity": "redis-cache-pod-0",
        "root_cause": "refused",
        "expected_tags": ["refused", "redis", "cache", "connection"],
        "ground_truth_claims": [
            "Redis cache pod port 6379 connection refused",
            "Redis process terminated due to invalid configuration",
        ],
    },
    {
        "id": "scenario-07",
        "query": "checkout-service CrashLoopBackOff container exit code 137",
        "target_service": "checkout-service",
        "target_entity": "checkout-service-pod-9c",
        "root_cause": "crashloop",
        "expected_tags": ["crashloop", "checkout", "137", "exit"],
        "ground_truth_claims": [
            "Checkout service crashed repeatedly with exit code 137",
            "Memory allocation failure during checkout processing",
        ],
    },
    {
        "id": "scenario-08",
        "query": "inventory-service disk storage volume full 100% capacity",
        "target_service": "inventory-service",
        "target_entity": "pvc-inventory-data",
        "root_cause": "disk_full",
        "expected_tags": ["disk_full", "inventory", "pvc", "volume"],
        "ground_truth_claims": [
            "Persistent volume pvc-inventory-data reached 100% disk usage",
            "Log file rotation failed filling container storage",
        ],
    },
    {
        "id": "scenario-09",
        "query": "notification-service TLS SSL certificate verification expired",
        "target_service": "notification-service",
        "target_entity": "ingress-tls-secret",
        "root_cause": "ssl_expired",
        "expected_tags": ["ssl_expired", "tls", "notification", "cert"],
        "ground_truth_claims": [
            "TLS certificate ingress-tls-secret expired at 00:00 UTC",
            "Notification service HTTPS requests rejected by client",
        ],
    },
    {
        "id": "scenario-10",
        "query": "database-postgres lock deadlock transaction abort",
        "target_service": "database-postgres",
        "target_entity": "postgres-master-0",
        "root_cause": "deadlock",
        "expected_tags": ["deadlock", "postgres", "lock", "transaction"],
        "ground_truth_claims": [
            "Postgres database aborted transaction due to deadlock",
            "Concurrent updates to account table blocked worker threads",
        ],
    },
]
