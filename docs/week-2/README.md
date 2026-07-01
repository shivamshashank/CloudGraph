# Week 2 Infrastructure & Observability Setup Pack

This directory contains the Week 2 deliverables and verification details from `ROADMAP.md`.

## Deliverables Mapped to Repository Code

| Deliverable | Location in Repository | Purpose |
| --- | --- | --- |
| **ArgoCD Applications** | [argocd-applications.yaml](../../deployments/kubernetes/argocd-applications.yaml) | Configures ArgoCD Application CRDs pointing to the Birmingham GitLab project for GitOps. |
| **Observability Stack** | [observability/](../../deployments/kubernetes/observability/) | Raw Kubernetes manifests for Prometheus, Grafana, Loki, and OpenTelemetry Collector. |
| **Sample Application (Manifests)** | [sample-app/](../../deployments/kubernetes/sample-app/) | Configures a microservice application with Prometheus scrapers and OTEL exporters to produce telemetry. |
| **Sample Application (Helm Chart)** | [helm/sample-app/](../../deployments/helm/sample-app/) | Custom templates and variables (`values.yaml`) to parameterize sample service deployments for dynamic scaling and settings. |

## Verification and Testing

### 1. Helm Chart Validation

Coded custom Helm chart for the microservice application.

- Linting command: `helm lint deployments/helm/sample-app` (Passed with 0 errors)

### 2. Observability Endpoints Verification

Located in [observability_test.go](../../tests/observability/observability_test.go), this test validates the responsiveness of:

- Prometheus UI (`/-/healthy`)
- Loki API (`/ready`)
- OpenTelemetry Collector (`/metrics`)
It gracefully skips when run outside the Kubernetes cluster context.
