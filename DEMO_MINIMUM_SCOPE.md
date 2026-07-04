# Minimum Scope for First Demo

This document defines the smallest set of work needed to show a visible, believable prototype of CloudGraph in a first demo.

## Goal of the First Demo

Show that CloudGraph can:

- install or run locally,
- ingest telemetry-like data,
- build a basic graph view of services and relationships,
- present a simple investigation flow,
- and produce a basic root-cause style explanation.

---

## 1. Demo Setup

- [ ] Repository can be cloned and started locally.
- [ ] One-command or simple setup script works for local demo.
- [ ] Core services can be launched with minimal configuration.
- [ ] Demo environment uses sample data instead of requiring full production telemetry.

### Visible Deliverables

- [ ] A local running instance of the API/backend.
- [ ] A simple UI or terminal output showing the system is live.

---

## 2. Basic Ingestion Demo

- [ ] The system accepts at least one telemetry event type clearly.
- [ ] Metrics ingestion works with sample payloads.
- [ ] Logs ingestion works with sample payloads.
- [ ] A deployment or change event can be ingested.
- [ ] The backend returns a success response for each ingestion call.

### Visible Deliverables

- [ ] Demo screen or API response shows incoming telemetry.
- [ ] Sample pod/service data appears in the system.

---

## 3. Basic Knowledge Graph

- [ ] Pods, services, and deployments are represented as graph entities.
- [ ] At least one relationship is visible, such as:
  - [ ] Pod runs on node
  - [ ] Pod belongs to service
  - [ ] Deployment manages pod
- [ ] A simple graph query or visualization can display these nodes and edges.

### Visible Deliverables

- [ ] A small graph view showing services and connections.
- [ ] A clear example of dependency mapping.

---

## 4. Basic Investigation Flow

- [ ] User can trigger a simple investigation for a sample incident.
- [ ] The system gathers evidence from ingested sample data.
- [ ] The system produces a simple explanation of likely cause.
- [ ] The output is human-readable and easy to show in a demo.

### Visible Deliverables

- [ ] A screen or terminal output saying: “Investigation started”.
- [ ] A short RCA-style summary such as “Service X is failing due to Y”.

---

## 5. Minimal UI / Presentation Layer

- [ ] A simple dashboard or page exists.
- [ ] It shows at least:
  - [ ] incidents or investigations
  - [ ] ingested telemetry
  - [ ] graph view or topology
  - [ ] investigation result
- [ ] The UI is simple enough to run and explain quickly.

### Visible Deliverables

- [ ] One-page demo interface.
- [ ] Clear navigation from data ingestion to investigation result.

---

## 6. Demo Data and Scenario

- [ ] A predefined sample incident scenario is available.
- [ ] The scenario should be easy to explain in under 2 minutes.
- [ ] Example scenario ideas:
  - [ ] CrashLoopBackOff on a payment service
  - [ ] High CPU causing slow response
  - [ ] Image pull failure for a deployment
  - [ ] Database timeout causing dependency failure

### Visible Deliverables

- [ ] One polished demo scenario.
- [ ] One script or narrative for the presenter.

---

## 7. Testing for Demo Readiness

- [ ] One happy-path demo flow works end to end.
- [ ] Sample data can be loaded without manual debugging.
- [ ] The demo can be run from a clean environment.
- [ ] The interface does not crash during the planned demo steps.

### Visible Deliverables

- [ ] A repeatable demo script.
- [ ] A known-good sample dataset.

---

## Recommended First Demo Flow

1. Start the platform locally.
2. Load sample telemetry data.
3. Show the graph of services and relationships.
4. Trigger a sample investigation.
5. Show a basic RCA-style explanation.

This is the minimum believable prototype for a first presentation.
