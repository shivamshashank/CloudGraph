# CloudGraph Installation Guide

## Overview

CloudGraph can be installed on any Kubernetes cluster using a single command. The installation script automatically:

- Detects your Kubernetes environment
- Installs kubeadm if needed
- Deploys CloudGraph and all dependencies via Helm
- Configures RBAC and service discovery

## Quick Start

### Option 1: Using curl (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/shivamshashank/CloudGraph/main/install.sh | bash
```

### Option 2: Direct script execution

```bash
git clone https://github.com/shivamshashank/CloudGraph.git
cd CloudGraph
./install.sh
```

### Option 3: Using Helm directly

```bash
# Add the CloudGraph Helm repository
helm repo add cloudgraph https://charts.cloudgraph.dev
helm repo update

# Install CloudGraph
helm install cloudgraph cloudgraph/cloudgraph \
  --namespace cloudgraph-system \
  --create-namespace
```

## Prerequisites

The installation script requires:

- **kubectl**: Kubernetes command-line tool
- **helm**: Kubernetes package manager (optional - script can install it)

For an existing cluster, no other prerequisites are needed.

## Installation Methods

### 1. Existing Kubernetes Cluster

If you already have a Kubernetes cluster running:

```bash
./install.sh
```

The script will:

1. ✓ Detect your cluster
2. ✓ Verify kubectl connectivity
3. ✓ Install Helm if needed
4. ✓ Deploy CloudGraph with all components
5. ✓ Wait for all pods to be ready

### 2. Bare Metal / On-Premise (Linux)

If you don't have a Kubernetes cluster:

```bash
./install.sh
```

When prompted, select option 1 to install kubeadm. The script will:

1. ✓ Update system packages
2. ✓ Install kubeadm, kubelet, and kubectl
3. ✓ Initialize a Kubernetes cluster
4. ✓ Install a CNI plugin (Flannel)
5. ✓ Configure the master node
6. ✓ Deploy CloudGraph

### 3. macOS / Docker Desktop

For macOS users with Docker Desktop:

1. Enable Kubernetes in Docker Desktop settings
2. Run the installation script:

```bash
./install.sh
```

### 4. Cloud Kubernetes Services

CloudGraph works with any managed Kubernetes service:

- **AWS EKS**: `helm install cloudgraph cloudgraph/cloudgraph ...`
- **Azure AKS**: `helm install cloudgraph cloudgraph/cloudgraph ...`
- **Google GKE**: `helm install cloudgraph cloudgraph/cloudgraph ...`
- **DigitalOcean DOKS**: `helm install cloudgraph cloudgraph/cloudgraph ...`

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

Then install with custom values:

```bash
helm install cloudgraph cloudgraph/cloudgraph \
  --namespace cloudgraph-system \
  --values values-custom.yaml
```

## Verification

After installation, verify CloudGraph is running:

```bash
# Check all pods are ready
kubectl get pods -n cloudgraph-system

# Check deployment status
kubectl get deployments -n cloudgraph-system

# View recent events
kubectl get events -n cloudgraph-system
```

Expected output:

```text
NAME                                READY   STATUS    RESTARTS   AGE
cloudgraph-api-xxxxx                1/1     Running   0          2m
investigation-engine-xxxxx          1/1     Running   0          2m
agent-orchestrator-xxxxx            1/1     Running   0          2m
cloudgraph-ui-xxxxx                 1/1     Running   0          2m
otel-collector-xxxxx                1/1     Running   0          2m
neo4j-xxxxx                         1/1     Running   0          3m
redis-master-xxxxx                  1/1     Running   0          3m
qdrant-xxxxx                        1/1     Running   0          3m
```

## Access CloudGraph

### Local Access (port-forward)

```bash
# Forward UI port
kubectl port-forward -n cloudgraph-system svc/cloudgraph-ui 3000:3000

# Access at http://localhost:3000
```

### Ingress Access

If you enabled Ingress in values.yaml:

```bash
# Get the Ingress URL
kubectl get ingress -n cloudgraph-system
```

### API Access

```bash
# Forward API port
kubectl port-forward -n cloudgraph-system svc/cloudgraph-api 8080:8080

# API available at http://localhost:8080
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
