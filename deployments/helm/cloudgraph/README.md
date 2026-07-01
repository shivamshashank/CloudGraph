# CloudGraph Helm Chart

Production-ready Helm chart for deploying CloudGraph on any Kubernetes cluster.

## Overview

This chart deploys the complete CloudGraph stack:

- **API Server**: REST API for incident investigation
- **Investigation Engine**: GraphRAG-powered investigation logic
- **Agent Orchestrator**: Multi-agent system orchestration
- **UI**: Web-based user interface
- **Data Services**: Neo4j, Qdrant, Redis
- **Telemetry**: OpenTelemetry Collector
- **RBAC**: Kubernetes access control

## Quick Start

### Prerequisites

- Kubernetes 1.24+
- Helm 3.0+
- kubectl configured to access your cluster

### Installation

```bash
# Add the CloudGraph Helm repository
helm repo add cloudgraph https://charts.cloudgraph.dev
helm repo update

# Install CloudGraph
helm install cloudgraph cloudgraph/cloudgraph \
  --namespace cloudgraph-system \
  --create-namespace
```

Or from the local chart:

```bash
helm install cloudgraph ./cloudgraph \
  --namespace cloudgraph-system \
  --create-namespace
```

## Chart Structure

```text
cloudgraph/
├── Chart.yaml                 # Chart metadata
├── values.yaml               # Default values
├── .helmignore               # Files to ignore
└── templates/
    ├── _helpers.tpl          # Template helpers
    ├── rbac.yaml             # RBAC & namespace
    ├── api.yaml              # CloudGraph API
    ├── ui.yaml               # Web UI
    ├── investigation-engine.yaml
    ├── agent-orchestrator.yaml
    ├── otel-collector.yaml   # OpenTelemetry
    └── NOTES.txt             # Post-install notes
```

## Configuration

### Default Values

See [values.yaml](./values.yaml) for all configurable options.

### Common Customizations

#### 1. High Availability

```yaml
# values-ha.yaml
cloudgraphApi:
  replicaCount: 3

investigationEngine:
  replicaCount: 3

agentOrchestrator:
  replicaCount: 2

redis:
  replica:
    replicaCount: 2
```

Install with HA configuration:

```bash
helm install cloudgraph cloudgraph/cloudgraph \
  --values values-ha.yaml \
  --namespace cloudgraph-system
```

#### 2. Custom Domain with Ingress

```yaml
# values-ingress.yaml
cloudgraphUI:
  ingress:
    enabled: true
    className: nginx
    hosts:
      - host: cloudgraph.example.com
        paths:
          - path: /
            pathType: Prefix
    tls:
      - secretName: cloudgraph-tls
        hosts:
          - cloudgraph.example.com
```

#### 3. External Observability Stack

If you have existing Prometheus, Grafana, or Loki:

```yaml
# values-external-obs.yaml
otelCollector:
  config:
    exporters:
      prometheus:
        endpoint: prometheus.monitoring.svc.cluster.local:9090
```

#### 4. Custom Resource Limits

```yaml
# values-resources.yaml
cloudgraphApi:
  resources:
    limits:
      cpu: 2000m
      memory: 2Gi
    requests:
      cpu: 500m
      memory: 1Gi

neo4j:
  resources:
    cpu: 2000m
    memory: 4Gi
```

### Installing Dependencies

The chart has optional dependencies. Update dependencies:

```bash
helm dependency update cloudgraph/
```

To install with bundled dependencies:

```bash
helm install cloudgraph cloudgraph/cloudgraph \
  --set neo4j.enabled=true \
  --set redis.enabled=true \
  --set qdrant.enabled=true
```

## Verification

Verify the installation:

```bash
# Check pods
kubectl get pods -n cloudgraph-system

# Check deployments
kubectl get deployments -n cloudgraph-system

# Check services
kubectl get svc -n cloudgraph-system

# Check events
kubectl get events -n cloudgraph-system --sort-by='.lastTimestamp'
```

Expected output:

```text
NAME                                READY   STATUS    RESTARTS   AGE
cloudgraph-api-xxxxx                1/1     Running   0          2m
investigation-engine-xxxxx          1/1     Running   0          2m
agent-orchestrator-xxxxx            1/1     Running   0          2m
cloudgraph-ui-xxxxx                 1/1     Running   0          2m
otel-collector-xxxxx                1/1     Running   0          2m
neo4j-xxxxx                         1/1     Running   0          2m
redis-master-xxxxx                  1/1     Running   0          2m
qdrant-xxxxx                        1/1     Running   0          2m
```

## Accessing CloudGraph

### Port-Forward Method

```bash
# UI
kubectl port-forward -n cloudgraph-system svc/cloudgraph-ui 3000:3000
# Visit: http://localhost:3000

# API
kubectl port-forward -n cloudgraph-system svc/cloudgraph-api 8080:8080
# Visit: http://localhost:8080

# Neo4j Browser
kubectl port-forward -n cloudgraph-system svc/neo4j 7474:7474
# Visit: http://localhost:7474
```

### Ingress Method (if enabled)

```bash
# Get ingress URL
kubectl get ingress -n cloudgraph-system

# Access via configured host
# e.g., http://cloudgraph.example.com
```

## Troubleshooting

### Check pod status

```bash
kubectl describe pod <pod-name> -n cloudgraph-system
kubectl logs <pod-name> -n cloudgraph-system
```

### Check service connectivity

```bash
# Test DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  nslookup cloudgraph-api.cloudgraph-system

# Check endpoints
kubectl get endpoints -n cloudgraph-system
```

### Check storage

```bash
# List persistent volumes
kubectl get pv -n cloudgraph-system

# List persistent volume claims
kubectl get pvc -n cloudgraph-system

# Describe a PVC
kubectl describe pvc <pvc-name> -n cloudgraph-system
```

## Upgrading

Update to a newer version:

```bash
# Update Helm repository
helm repo update cloudgraph

# Upgrade release
helm upgrade cloudgraph cloudgraph/cloudgraph \
  --namespace cloudgraph-system \
  --values values.yaml
```

Check upgrade status:

```bash
helm status cloudgraph -n cloudgraph-system
helm history cloudgraph -n cloudgraph-system
```

## Rollback

If an upgrade fails, rollback to the previous version:

```bash
helm rollback cloudgraph -n cloudgraph-system
```

List available revisions:

```bash
helm history cloudgraph -n cloudgraph-system
```

Rollback to a specific revision:

```bash
helm rollback cloudgraph 2 -n cloudgraph-system
```

## Uninstalling

Remove CloudGraph:

```bash
helm uninstall cloudgraph -n cloudgraph-system
```

Delete the namespace:

```bash
kubectl delete namespace cloudgraph-system
```

## Values Reference

### Global Settings

```yaml
global:
  namespace: cloudgraph-system  # Deployment namespace
  imagePullPolicy: IfNotPresent # Image pull policy
```

### CloudGraph Components

- `cloudgraphApi`: REST API configuration
- `investigationEngine`: Investigation engine configuration
- `agentOrchestrator`: Agent orchestration configuration
- `cloudgraphUI`: Web UI configuration

### Data Services

- `neo4j`: Neo4j knowledge graph database
- `redis`: Redis cache and message queue
- `qdrant`: Qdrant vector database

### Observability

- `otelCollector`: OpenTelemetry collector configuration
- `serviceMonitor`: Prometheus service monitor
- `observabilityStack`: Optional Prometheus, Grafana, and Loki

### Security

- `rbac`: RBAC configuration
- `podSecurityPolicy`: Pod security policies
- `networkPolicy`: Network policies

## Support

- **Issues**: <https://github.com/shivamshashank/CloudGraph/issues>
- **Docs**: <https://github.com/shivamshashank/CloudGraph/docs>
- **Discord**: [Join Community](https://discord.gg/cloudgraph)

## License

See [LICENSE](../../../LICENSE) in the root repository.
