# CloudGraph Installation Guide

> [!IMPORTANT]
> CloudGraph is supported **exclusively on Linux** (both AMD64 and ARM64 architectures).

## Overview

CloudGraph is deployed and managed via the `cloudgraph` CLI. The CLI supports:

- Native single-command installation on Linux.
- Automated single-command deployment (`cloudgraph deploy`) of Kubernetes (kubeadm), Helm, and the CloudGraph Core stack.
- Automated uninstallation (`cloudgraph uninstall`) for clean teardown.

## Quick Start

### Option 1: Curl Installer (Recommended)

To download and install the pre-compiled `cloudgraph` Linux binary matching your CPU architecture (AMD64/ARM64) from GitHub Releases:

```bash
curl -fsSL https://raw.githubusercontent.com/shivamshashank/CloudGraph/main/install.sh | sudo bash
```

Once installed, proceed directly to deploying the stack:

```bash
sudo cloudgraph deploy
```

---

### Option 2: Build From Source (Development)

If you have Go (1.23+) installed on your Linux machine, you can compile the CLI directly:

```bash
git clone https://github.com/shivamshashank/CloudGraph.git
cd CloudGraph
go build -o cloudgraph ./cmd/cloudgraph
sudo ./cloudgraph deploy
```

---

### Option 3: Go Install (Global Path)

```bash
go install github.com/shivamshashank/CloudGraph@latest
```

This installs `cloudgraph` directly to your `$GOPATH/bin` (or `$HOME/go/bin`).

## Prerequisites

The deployment command requires:

- **Go**: Version 1.23+ (only if compiling from source)
- **kubectl**: Kubernetes command-line tool

For an existing cluster, no other prerequisites are needed.

## Installation Methods

### 1. Automated Script Installation

```bash
curl -fsSL https://raw.githubusercontent.com/shivamshashank/CloudGraph/main/install.sh | sudo bash
sudo cloudgraph deploy
```

The deploy command will:

1. ✓ Configure kubeconfig access
2. ✓ Prompt to install kubeadm and initialize a cluster (if no cluster is detected)
3. ✓ Install Rancher Local Path storage provisioner and Ingress NGINX controller
4. ✓ Check Helm and deploy the CloudGraph stack
5. ✓ Wait for all deployments to be healthy

### 2. Existing environment

If you already have the API running, you can skip the installer and use the CLI directly:

```bash
cloudgraph health http://localhost:8000
```

## What Gets Installed

The installation deploys the complete CloudGraph stack:

### Core Components

- **CloudGraph API**: REST API for incident investigation
- **Investigation Engine**: GraphRAG-powered investigation logic
- **Agent Orchestrator**: Multi-agent orchestration system
- **CloudGraph UI**: Web-based user interface

### Data Layer

- **Neo4j**: Knowledge graph database (stores infrastructure relationships)
- **Qdrant**: Vector database (embeddings for GraphRAG)
- **Redis**: Cache and message queue

### Observability

- **OpenTelemetry Collector**: Telemetry ingestion and processing
- **RBAC**: Kubernetes role-based access control
- **Service Discovery**: Automatic Kubernetes cluster discovery
- **Custom Resource Definitions**: CloudGraph CRDs

### Optional Components (can be enabled in values.yaml)

- Prometheus (metrics)
- Grafana (visualization)
- Loki (log aggregation)

## Configuration

### Custom Values

To customize the installation, create a `values-custom.yaml`:

```yaml
# Example: Increase API replicas
cloudgraphApi:
  replicaCount: 3

# Example: Enable Ingress
cloudgraphUI:
  ingress:
    enabled: true
    hosts:
      - host: cloudgraph.example.com
        paths:
          - path: /
            pathType: Prefix

# Example: Enable existing observability stack
neo4j:
  neo4jPassword: "your-secure-password"
```

Then use the CLI against your running API:

```bash
cloudgraph health http://localhost:8000
```

## Verification

After installation, verify the CLI works:

```bash
cloudgraph --help
cloudgraph version
```

## Access CloudGraph

### 1. Ingress Access (Recommended / Automated)

Since the NGINX Ingress Controller is installed and configured automatically by `cloudgraph deploy`, the entire stack is exposed on port 80/443 of the host/VM network. You can access the UI and API directly in your browser without running any manual port-forwarding:

- **Web UI:** [http://localhost/](http://localhost/) (or `http://<node-ip>/`)
- **Backend API:** [http://localhost/api/](http://localhost/api/)

---

### 2. Manual Access (port-forward fallback)

If Ingress is disabled, you can manually forward the service ports from the cluster:

#### Web UI

```bash
kubectl port-forward -n cloudgraph-system svc/cloudgraph-ui 3000:3000
# Access at http://localhost:3000
```

#### Backend API

```bash
kubectl port-forward -n cloudgraph-system svc/cloudgraph-api 8080:8080
# Access at http://localhost:8080
```

## Useful Commands

### View Logs

```bash
# API logs
kubectl logs -n cloudgraph-system deployment/cloudgraph-api -f

# Investigation Engine logs
kubectl logs -n cloudgraph-system deployment/investigation-engine -f

# Agent Orchestrator logs
kubectl logs -n cloudgraph-system deployment/agent-orchestrator -f

# All logs
kubectl logs -n cloudgraph-system -f --all-containers=true --timestamps=true
```

### Access Neo4j

```bash
# Port-forward Neo4j
kubectl port-forward -n cloudgraph-system svc/neo4j 7474:7474 7687:7687

# Get Neo4j password
kubectl get secret -n cloudgraph-system neo4j -o jsonpath='{.data.password}' | base64 -d

# Access Neo4j Browser at http://localhost:7474
```

### Access Redis

```bash
# Port-forward Redis
kubectl port-forward -n cloudgraph-system svc/redis-master 6379:6379

# Connect with redis-cli
redis-cli -h localhost -p 6379
```

## Troubleshooting

### Issue: Pods not starting

```bash
# Check pod status and events
kubectl describe pod <pod-name> -n cloudgraph-system

# Check logs for errors
kubectl logs <pod-name> -n cloudgraph-system
```

### Issue: ImagePullBackOff

```bash
# Verify image availability
kubectl get events -n cloudgraph-system | grep ImagePull

# Check image pull secrets
kubectl get secrets -n cloudgraph-system
```

### Issue: PVC stuck in Pending

```bash
# Check available storage classes
kubectl get storageclass

# Check PVC status
kubectl get pvc -n cloudgraph-system

# Describe PVC for details
kubectl describe pvc <pvc-name> -n cloudgraph-system
```

### Issue: Services not accessible

```bash
# Check service endpoints
kubectl get endpoints -n cloudgraph-system

# Check DNS resolution
kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup cloudgraph-api.cloudgraph-system
```

## Upgrading

To upgrade CloudGraph to a newer version:

```bash
helm repo update cloudgraph

helm upgrade cloudgraph cloudgraph/cloudgraph \
  --namespace cloudgraph-system
```

## Uninstalling

To remove CloudGraph:

```bash
helm uninstall cloudgraph \
  --namespace cloudgraph-system
```

To delete the namespace and all resources:

```bash
kubectl delete namespace cloudgraph-system
```

## Why Helm?

Helm is the standard package manager for Kubernetes and keeps deployment simple:

1. **Simpler Kubernetes Operations**: Helm is the standard package manager for Kubernetes
2. **Cloud Agnostic**: Works on any Kubernetes cluster without cloud-specific configuration
3. **Easier Updates**: Helm upgrades are simpler and safer than infrastructure-state management
4. **Community Standard**: Aligns with Kubernetes ecosystem best practices
5. **Faster Deployment**: One-command installation and built-in rollback

## Support

For issues or questions:

- GitHub Issues: <https://github.com/shivamshashank/CloudGraph/issues>
- Documentation: <https://github.com/shivamshashank/CloudGraph/docs>
- Discord Community: [Join us](https://discord.gg/cloudgraph)

## Next Steps

After CloudGraph is installed:

1. **Configure Observability Integration**: Connect to your Prometheus, Grafana, and Loki instances
2. **Set Up Alerts**: Configure incident detection and alert routing
3. **Customize Incident Rules**: Define custom investigation rules for your environment
4. **Integrate with Your Incident Manager**: Connect PagerDuty, Opsgenie, or similar
5. **Start Investigations**: Begin AI-powered root cause analysis

Refer to the [CloudGraph Documentation](https://github.com/shivamshashank/CloudGraph/docs) for detailed guides.
