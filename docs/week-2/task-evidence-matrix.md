# Week 2 Task Evidence Matrix

This file maps every checked Week 2 roadmap task to a concrete repository artifact. Use it as an audit trail when verifying project milestone achievements.

## Infrastructure

| Roadmap Task | Evidence File | What Was Completed |
| --- | --- | --- |
| Provision AWS EKS | [modules/eks/](../../deployments/terraform/modules/eks/) | Wrote the Terraform module to create control plane, node groups, and cloudwatch logs. |
| Configure Terraform | [main.tf](../../deployments/terraform/main.tf) | Defined root configuration, providers (AWS/TLS), local variables, and backend block. |
| Configure IAM | [modules/iam/](../../deployments/terraform/modules/iam/) | Set up OIDC provider integration and trust policies for EKS Add-on IAM Roles (IRSA). |
| Setup VPC | [modules/vpc/](../../deployments/terraform/modules/vpc/) | Created the VPC layout with public/private subnets, routes, internet gateway, and NAT gateway. |

## Kubernetes

| Roadmap Task | Evidence File | What Was Completed |
| --- | --- | --- |
| Deploy sample applications | [sample-app/](../../deployments/kubernetes/sample-app/) | Defined namespace, service, and deployment with OTEL telemetry exporter & Prometheus scraper configurations. |
| Configure Helm | [helm/sample-app/](../../deployments/helm/sample-app/) | Created a complete Helm chart templates structure for Checkout and Payment services, parameters in `values.yaml`, and validated with `helm lint`. |
| Configure ArgoCD | [argocd-applications.yaml](../../deployments/kubernetes/argocd-applications.yaml) | Created ArgoCD application CRDs referencing the GitLab repository `sxs2511` to bootstrap GitOps, linking the Helm chart directly. |

## Observability

| Roadmap Task | Evidence File | What Was Completed |
| --- | --- | --- |
| Install Prometheus | [prometheus.yaml](../../deployments/kubernetes/observability/prometheus.yaml) | Declared deployment, service, configmap, and RBAC to collect metrics. |
| Install Grafana | [grafana.yaml](../../deployments/kubernetes/observability/grafana.yaml) | Setup Grafana UI service and configmap datasource mappings for metrics, logs, and traces. |
| Install Loki | [loki.yaml](../../deployments/kubernetes/observability/loki.yaml) | Configured Loki logs storage, single-binary container deployment, and ingress service. |
| Install Tempo | [tempo.yaml](../../deployments/kubernetes/observability/tempo.yaml) | Set up Tempo trace ingestion, storage configuration, and readiness endpoint. |
| Configure OpenTelemetry | [otel-collector.yaml](../../deployments/kubernetes/observability/otel-collector.yaml) | Created OpenTelemetry Collector pipeline configuration forwarding traces to Tempo, logs to Loki, and exposing metrics. |

## Testing

| Roadmap Task | Evidence File | What Was Completed |
| --- | --- | --- |
| Verify metrics collection | [observability_test.go](../../tests/observability/observability_test.go) | Validates Prometheus `/-/healthy` and OpenTelemetry `/metrics` endpoints. |
| Verify tracing | [observability_test.go](../../tests/observability/observability_test.go) | Validates Tempo `/ready` endpoint. |
| Verify logging | [observability_test.go](../../tests/observability/observability_test.go) | Validates Loki `/ready` endpoint. |
| Run plan validation | [tests/terraform/](../../tests/terraform/) | Go tests to run local dry-run plan checks for all modules offline. |
