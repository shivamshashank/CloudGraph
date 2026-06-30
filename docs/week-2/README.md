# Week 2 Infrastructure & Observability Setup Pack

This directory contains the Week 2 deliverables and verification details from `ROADMAP.md`.

## Deliverables Mapped to Repository Code

| Deliverable | Location in Repository | Purpose |
| --- | --- | --- |
| **AWS VPC Module** | [vpc/main.tf](../../deployments/terraform/modules/vpc/main.tf) | Provisions the VPC, subnets, route tables, Internet Gateway, and NAT Gateway. |
| **AWS Security Groups Module** | [security-groups/main.tf](../../deployments/terraform/modules/security-groups/main.tf) | Defines secure ingress/egress rules for EKS control plane and worker nodes. |
| **AWS EKS Module** | [eks/main.tf](../../deployments/terraform/modules/eks/main.tf) | Provisions AWS EKS control plane, managed node groups, logs, and core add-ons (CoreDNS, kube-proxy, VPC CNI). |
| **AWS IAM / IRSA Module** | [iam/main.tf](../../deployments/terraform/modules/iam/main.tf) | Configures the OIDC provider and sets up IAM Roles for Service Accounts (IRSA) for EBS CSI, Load Balancer, and Autoscaler. |
| **Root Terraform Configuration** | [main.tf](../../deployments/terraform/main.tf) | Wires together all AWS child modules into a coherent environment deployment. |
| **ArgoCD Applications** | [argocd-applications.yaml](../../deployments/kubernetes/argocd-applications.yaml) | Configures ArgoCD Application CRDs pointing to the Birmingham GitLab project for GitOps. |
| **Observability Stack** | [observability/](../../deployments/kubernetes/observability/) | Raw Kubernetes manifests for Prometheus, Grafana, Loki, Tempo, and OpenTelemetry Collector. |
| **Sample Application (Manifests)** | [sample-app/](../../deployments/kubernetes/sample-app/) | Configures a microservice application with Prometheus scrapers and OTEL exporters to produce telemetry. |
| **Sample Application (Helm Chart)** | [helm/sample-app/](../../deployments/helm/sample-app/) | Custom templates and variables (`values.yaml`) to parameterize sample service deployments for dynamic scaling and settings. |

## Verification and Testing

### 1. Terraform Plan Validation (Offline)
Located in `tests/terraform/`, these tests initialize the modules with mock providers and validate resource declarations offline to ensure syntax, schema, and reference validity.
- **VPC / SG Plan Test**: [vpc_test.go](../../tests/terraform/vpc_test.go)
- **EKS Plan Test**: [eks_test.go](../../tests/terraform/eks_test.go)
- **IAM / IRSA Plan Test**: [iam_test.go](../../tests/terraform/iam_test.go)

### 2. Helm Chart Validation
Coded custom Helm chart for the microservice application.
- Linting command: `helm lint deployments/helm/sample-app` (Passed with 0 errors)

### 3. Observability Endpoints Verification
Located in [observability_test.go](../../tests/observability/observability_test.go), this test validates the responsiveness of:
- Prometheus UI (`/-/healthy`)
- Loki API (`/ready`)
- Tempo API (`/ready`)
- OpenTelemetry Collector (`/metrics`)
It gracefully skips when run outside the Kubernetes cluster context.
