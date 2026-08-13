# CloudGraph Helm Deployment

CloudGraph deployment using Helm 3 - the Kubernetes package manager.

## Quick Start

```bash
# Option 1: Using the installation script (recommended)
cd /Users/shivam_shashank/CloudGraph
./install.sh

# Option 2: Using Helm directly
helm install cloudgraph ./cloudgraph \
  --namespace cloudgraph-system \
  --create-namespace

# Option 3: Using the official Helm repo
helm repo add cloudgraph https://charts.cloudgraph.dev
helm install cloudgraph cloudgraph/cloudgraph \
  --namespace cloudgraph-system \
  --create-namespace
```

## Directory Structure

```text
helm/
├── sample-app/          # Example microservice app
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
├── cloudgraph/          # Main CloudGraph chart (NEW)
│   ├── Chart.yaml
│   ├── values.yaml
│   ├── README.md
│   ├── .helmignore
│   └── templates/
└── README.md
```

## What Gets Installed

The CloudGraph Helm chart deploys:

### Core Services

- CloudGraph API (`cloudgraph-api`)
- Investigation Engine (`investigation-engine`)
- Agent Orchestrator (`agent-orchestrator`)
- Web UI (`cloudgraph-ui`)
- OpenTelemetry Collector (`otel-collector`)

### Databases

- Neo4j - Knowledge graph database
- Qdrant - Vector database

### Kubernetes Integration

- RBAC with cluster roles for discovery
- Service accounts for each component
- Namespace: `cloudgraph-system`
- Network policies (optional)

## Configuration

See [cloudgraph/values.yaml](./cloudgraph/values.yaml) for all options:

```yaml
# Common customizations:
cloudgraphApi:
  replicaCount: 1            # Scale API
  resources:
    limits:
      cpu: 1000m
      memory: 1Gi

cloudgraphUI:
  ingress:
    enabled: true            # Enable Ingress
    className: nginx
    hosts:
      - host: cloudgraph.example.com
```

## Verification

```bash
# Check all pods
kubectl get pods -n cloudgraph-system

# Expected output:
# cloudgraph-api-xxxxx                1/1     Running
# investigation-engine-xxxxx          1/1     Running
# agent-orchestrator-xxxxx            1/1     Running
# cloudgraph-ui-xxxxx                 1/1     Running
# otel-collector-xxxxx                1/1     Running
# neo4j-xxxxx                         1/1     Running
# qdrant-xxxxx                        1/1     Running
```

## Access CloudGraph

```bash
# Port-forward to UI
kubectl port-forward -n cloudgraph-system svc/cloudgraph-ui 3000:3000

# Access at http://localhost:3000
```

## Helm Commands

```bash
# Install
helm install cloudgraph ./cloudgraph -n cloudgraph-system --create-namespace

# Upgrade
helm upgrade cloudgraph ./cloudgraph -n cloudgraph-system

# Rollback
helm rollback cloudgraph -n cloudgraph-system

# Uninstall
helm uninstall cloudgraph -n cloudgraph-system

# Get values
helm get values cloudgraph -n cloudgraph-system

# Get deployment info
helm status cloudgraph -n cloudgraph-system

# Dry-run
helm install cloudgraph ./cloudgraph --dry-run --debug

# Validate chart
helm lint ./cloudgraph
```

## Documentation

- [CloudGraph Helm Chart README](./cloudgraph/README.md)
- [Installation Guide](../../docs/guides/INSTALLATION.md)
- [Implementation Summary](../../docs/project/STATUS.md)
- [System Architecture](../../docs/architecture/system-overview.md)

## Support

For issues or questions:

- GitHub: <https://github.com/shivamshashank/CloudGraph/issues>
- Docs: <https://github.com/shivamshashank/CloudGraph/docs>
