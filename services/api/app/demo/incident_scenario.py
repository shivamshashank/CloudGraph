"""Generates the demo incident kubernetes manifest payload."""

from pathlib import Path


def build_demo_incident_manifest() -> str:
    """Build the demo incident Kubernetes deployment YAML manifest."""
    return """apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-payment-app
  namespace: cloudgraph-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: demo-payment-app
  template:
    metadata:
      labels:
        app: demo-payment-app
    spec:
      containers:
        - name: payment
          image: nginx:does-not-exist
          env:
            - name: DB_PASSWORD
              value: wrong-password
            - name: DB_HOST
              value: postgres.default.svc.cluster.local
"""


def write_demo_incident_manifest(path: str | None = None) -> Path:
    """Write the generated demo incident manifest to a YAML file."""
    target = Path(path) if path else Path(__file__).with_name("demo_incident.yaml")
    target.write_text(build_demo_incident_manifest(), encoding="utf-8")
    return target
