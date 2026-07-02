# CloudGraph Installation Quick Start

**Everything you need to deploy CloudGraph in 3 minutes.**

## 🚀 One-Command Installation

```bash
curl -fsSL https://raw.githubusercontent.com/shivamshashank/CloudGraph/main/install.sh | bash
```

That's it! The script will:

1. ✅ Check for Kubernetes cluster
2. ✅ Offer to install kubeadm if needed
3. ✅ Install the CloudGraph CLI through curl
4. ✅ Prepare the environment for direct API usage
5. ✅ Wait for everything to be ready

## 🔍 What Gets Installed

| Component | Purpose |
|-----------|---------|
| **CloudGraph API** | REST API for investigations |
| **Investigation Engine** | GraphRAG-powered analysis |
| **Agent Orchestrator** | Multi-agent system |
| **Web UI** | User interface |
| **Neo4j** | Knowledge graph database |
| **Qdrant** | Vector database |
| **Redis** | Cache & messaging |
| **OTel Collector** | Telemetry ingestion |

## ✅ Verification

After installation completes:

```bash
# Check pods are running
kubectl get pods -n cloudgraph-system

# Access UI
kubectl port-forward -n cloudgraph-system svc/cloudgraph-ui 3000:3000
# Then visit: http://localhost:3000
```

## 🔧 Manual CLI Usage

If you prefer to use the CLI directly after installation:

```bash
cloudgraph --help
cloudgraph version
cloudgraph health http://localhost:8000
```

## 📝 Environment Options

### Option 1: Existing Kubernetes Cluster

```bash
./install.sh
# Script detects cluster and deploys
```

### Option 2: Bare Metal (Linux)

```bash
./install.sh
# Select option 1 to install kubeadm
```

### Option 3: macOS with Docker Desktop

```bash
# Enable Kubernetes in Docker Desktop settings
# Then run:
./install.sh
```

### Option 4: Cloud Providers (AWS/Azure/GCP)

```bash
# Works with EKS, AKS, GKE, and others
./install.sh
```

## 🔌 Access Methods

### Port-Forward (local testing)

```bash
# UI
kubectl port-forward -n cloudgraph-system svc/cloudgraph-ui 3000:3000

# API
kubectl port-forward -n cloudgraph-system svc/cloudgraph-api 8080:8080
```

### Ingress (production)

```yaml
# Enable in values.yaml
cloudgraphUI:
  ingress:
    enabled: true
    hosts:
      - host: cloudgraph.example.com
```

## 📊 Logs & Debugging

```bash
# View API logs
kubectl logs -n cloudgraph-system deployment/cloudgraph-api -f

# View Investigation Engine logs
kubectl logs -n cloudgraph-system deployment/investigation-engine -f

# View all logs
kubectl logs -n cloudgraph-system -f --all-containers=true
```

## 🛠️ Common Operations

### Check the API

```bash
cloudgraph health http://localhost:8000
```

### Send a sample payload

```bash
cloudgraph ingest http://localhost:8000 /api/v1/telemetry/logs
```

## 📖 Documentation

- **Full Installation Guide**: [INSTALLATION.md](../INSTALLATION.md)
- **Helm Chart Docs**: [deployments/helm/cloudgraph/README.md](./deployments/helm/cloudgraph/README.md)
- **System Architecture**: [docs/architecture/system-overview.md](./docs/architecture/system-overview.md)
- **Implementation Details**: [IMPLEMENTATION_SUMMARY.md](../IMPLEMENTATION_SUMMARY.md)

## ❓ Troubleshooting

### Issue: Pods not starting

```bash
# Check pod status
kubectl describe pod <pod-name> -n cloudgraph-system

# Check for image pull errors
kubectl get events -n cloudgraph-system | grep ImagePull
```

### Issue: Services not accessible

```bash
# Check service endpoints
kubectl get endpoints -n cloudgraph-system

# Test DNS
kubectl run -it --rm debug --image=busybox --restart=Never -- \
  nslookup cloudgraph-api.cloudgraph-system
```

### Issue: Storage/PVC errors

```bash
# Check storage class
kubectl get storageclass

# Check PVCs
kubectl get pvc -n cloudgraph-system

# Describe PVC
kubectl describe pvc <pvc-name> -n cloudgraph-system
```

## 🎯 Next Steps

1. **Installation**: Run `./install.sh`
2. **Verification**: Wait for all pods to be ready
3. **Access UI**: Port-forward to UI and login
4. **Configure**: Connect your observability tools
5. **Investigate**: Start using CloudGraph!

## 🔗 Resources

- **GitHub**: <https://github.com/shivamshashank/CloudGraph>
- **Documentation**: <https://github.com/shivamshashank/CloudGraph/docs>
- **Issues**: <https://github.com/shivamshashank/CloudGraph/issues>
- **Community**: [Discord](https://discord.gg/cloudgraph)

---

**Ready to go?** Run this command:

```bash
curl -fsSL https://raw.githubusercontent.com/shivamshashank/CloudGraph/main/install.sh | bash
```

🚀 CloudGraph will be installed in minutes!
