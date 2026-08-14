"""Generates demo incident kubernetes manifest payloads.

`build_demo_incident_manifest` (the original, single scenario) is kept
exactly as-is for backward compatibility — it's covered by
tests/test_incident_scenario.py. The additional named incidents below exist
because one failure mode (ImagePullBackOff) isn't enough to meaningfully
exercise the RCA pipeline against different anomaly signatures; see
testing/intensive/ for the script that applies these to a live cluster.
"""

from collections.abc import Callable
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


def build_crashloop_incident_manifest() -> str:
    """CrashLoopBackOff via a container that exits immediately on start."""
    return """apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-checkout-app
  namespace: cloudgraph-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: demo-checkout-app
  template:
    metadata:
      labels:
        app: demo-checkout-app
    spec:
      containers:
        - name: checkout
          image: busybox:latest
          command: ["sh", "-c"]
          args:
            - "echo 'FATAL: unhandled exception in checkout worker' >&2; exit 1"
          env:
            - name: QUEUE_HOST
              value: rabbitmq.cloudgraph-system.svc.cluster.local
"""


def build_oom_incident_manifest() -> str:
    """OOMKilled via a memory limit too low for the image to even start."""
    return """apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-cache-app
  namespace: cloudgraph-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: demo-cache-app
  template:
    metadata:
      labels:
        app: demo-cache-app
    spec:
      containers:
        - name: cache
          image: redis:7-alpine
          resources:
            limits:
              memory: "8Mi"
            requests:
              memory: "8Mi"
          env:
            - name: MAXMEMORY_POLICY
              value: allkeys-lru
"""


def build_config_error_incident_manifest() -> str:
    """CreateContainerConfigError via a Secret reference that doesn't exist."""
    return """apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-notification-app
  namespace: cloudgraph-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: demo-notification-app
  template:
    metadata:
      labels:
        app: demo-notification-app
    spec:
      containers:
        - name: notification
          image: nginx:alpine
          envFrom:
            - secretRef:
                name: notification-smtp-credentials
"""


def build_probe_failure_incident_manifest() -> str:
    """CrashLoopBackOff via a liveness probe that always fails, on an
    otherwise-healthy container — distinct signature from crashloop-on-exit
    (the container starts fine and runs, but keeps getting killed)."""
    return """apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-search-app
  namespace: cloudgraph-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: demo-search-app
  template:
    metadata:
      labels:
        app: demo-search-app
    spec:
      containers:
        - name: search
          image: nginx:alpine
          ports:
            - containerPort: 80
          livenessProbe:
            httpGet:
              path: /healthz/deep
              port: 9999
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 1
          env:
            - name: SEARCH_INDEX_HOST
              value: elasticsearch.cloudgraph-system.svc.cluster.local
"""


# (name, category, builder). Categories match the benchmark's 5-way taxonomy.
DEMO_INCIDENTS: dict[str, tuple[str, Callable[[], str]]] = {
    "image-pull-error": ("Deployment", build_demo_incident_manifest),
    "crashloop": ("Kubernetes", build_crashloop_incident_manifest),
    "oom-killed": ("Observability", build_oom_incident_manifest),
    "config-error": ("Deployment", build_config_error_incident_manifest),
    "probe-failure": ("Networking", build_probe_failure_incident_manifest),
}


def write_demo_incident_manifest(path: str | None = None) -> Path:
    """Write the original single demo incident manifest to a YAML file
    (backward-compatible — unchanged behavior)."""
    target = Path(path) if path else Path(__file__).with_name("demo_incident.yaml")
    target.write_text(build_demo_incident_manifest(), encoding="utf-8")
    return target


def write_all_demo_incident_manifests(directory: str | None = None) -> dict[str, Path]:
    """Write every named incident in DEMO_INCIDENTS to its own YAML file in
    `directory` (default: alongside this module), returning name -> path."""
    target_dir = Path(directory) if directory else Path(__file__).parent
    target_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for name, (_category, builder) in DEMO_INCIDENTS.items():
        target = target_dir / f"demo_incident_{name}.yaml"
        target.write_text(builder(), encoding="utf-8")
        written[name] = target
    return written
