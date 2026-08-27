# CloudGraph — Complete Sequential Execution Chain (Condition `RAW` vs `NONE`)

This document presents the complete sequential input-to-output execution chain for **Condition `RAW`** (unfiltered long-context dump) and compares it directly against **Condition `NONE`** (baseline telemetry only) in scenario **`rcaeval-14`** (*Sock Shop*, target pod: `carts`, injected fault: `memory_exhaustion` at timestamp `1705845578`).

All values are quoted directly from `02-rcaeval-14/rcaeval-14-RAW.log`, written live by `scripts/trace_scenario.py` (236.0s wall time).

---

## 🎯 Executive Summary: Condition `RAW` vs Condition `NONE`

| Execution Metric | Condition `NONE` (Baseline / No Context) | Condition `RAW` (Full Context Dump) | Comparative Outcome |
|---|---|---|---|
| **Retrieved Evidence Items** | **0 items** | **59 items** (32 graph + 27 vector) | `RAW` loads all 59 database nodes into prompt |
| **Retrieval Wall Time** | `0.000s` | **0.125s** | Concatenating 59 nodes/vectors takes 0.125s |
| **Agent Confidences (Gen 1)** | Mon `0.30`, Log `0.87`, Dep `0.35`, Top `0.92` | Mon `0.92`, Log `0.94`, Dep `0.68`, Top `0.94` | Context increases agent confidences |
| **Consensus Diagnosis** | Accurate | Failed | Diagnostic evaluation against ground truth |
| **Consensus Severity & Conf.** | 80% confidence (HIGH severity) | **80% confidence (HIGH severity)** | `RAW` evaluates full context dump |
| **Extracted Claims** | 27 claims | **52 claims** | `RAW` claims include commit metadata & metric thrashing |
| **GPCS Unsupported Rate** | 96.3% (26 / 27) | **92.3% (48 / 52)** | GPCS unsupported under `RAW` evidence dump |
| **Self-Consistency Unsupported** | 44.4% (12 / 27) | **57.7% (30 / 52)** | Self-consistency becomes more permissive under `RAW` |
| **Evaluable Causal Claims** | 2 consistent | **0 consistent** | Ground-truth consistent claim count |
| **Total LLM Calls & Wall Time** | 18 calls in 252.0s | **18 calls in 236.0s** | `RAW` completed in 236.0s |

---

## 📌 STEP 1 — Telemetry Ingestion and Database Seeding

**📥 INPUT** — Scenario `rcaeval-14` from RCAEval RE2 (Sock Shop):

| Property | Value |
|---|---|
| **Source System** | `Sock Shop` |
| **Target Pod / Service** | `carts` on node `node-worker-01` |
| **Injected Fault** | `memory_exhaustion` at epoch `1705845578` |
| **Query String** | `carts degraded performance investigation` |
| **Observed Symptoms** | 26 telemetry lines |
| **Held-Out Ground Truth** | 2 claims — never prompted |

**⚙️ EXECUTION** — `seed_scenario_data()` in `services/api/app/demo/seeding.py`:

- Writes Cypher entities/relationships into **Neo4j**.
- Writes 384-dim `all-MiniLM-L6-v2` embeddings into **Qdrant**.

**📤 OUTPUT** — Database mutations:

```text
Neo4j:   Log 3538 -> 3564 (+26), Metric 238 -> 239 (+1), Node 1 -> 2 (+1), Pod 9 -> 10 (+1), Service 10 -> 11 (+1), Deployment 6 -> 7 (+1), Commit 0 -> 1 (+1)
Qdrant:  3558 -> 3585 evidence vector embeddings (+27, duplicate-vector fix active)
```

Then the isolation assertion: **PASSED** — the vector store holds strictly this scenario's evidence.

---

## 🔍 STEP 2 — Isolation Assertion & Evidence Retrieval

**⚙️ EXECUTION** — Asserts vector store isolation and runs search.

### Retrieval Comparison

- **Condition `NONE`:** Returns **0 items** (`0.000s`). Agents reason strictly from the 26 observed symptom strings.
- **Condition `RAW`:** Returns **59 items** (`0.125s`).

### 🧮 How the 59 Unfiltered Evidence Items Are Derived (Arithmetic & Mechanics)

In `run_raw_context_search()`, `RAW` mode performs a direct, unfiltered list concatenation of all seeded database entities without applying top-$K$ cutoffs, graph hop limits, or hybrid ranking:

1. **Part A — Neo4j Cypher Graph Query (32 Nodes):**

   ```cypher
   MATCH (n) WHERE n.is_benchmark = true AND n.scenario_id = 'rcaeval-14' RETURN n
   ```

   Pulls **all 32 Neo4j graph nodes** seeded for scenario `rcaeval-14`:
   - `1 Pod` (`carts`), `1 Service` (`carts`), `1 Deployment` (`carts-deploy`), `1 Node` (`node-worker-01`), `1 Commit` (`sha-rcaeval-14`), `1 Metric`, and `26 Log` nodes.

2. **Part B — Qdrant Dense Vector Search (27 Documents):**

   ```python
   semantic_hits = semantic_store.search(query, limit=50, scenario_id='rcaeval-14')
   ```

   With `limit=50`, Qdrant returns **all 27 vector documents** indexed for `rcaeval-14`.

3. **Part C — Unfiltered Concatenation ($32 + 27 = \mathbf{59\text{ Items}}$):**

   ```python
   raw_results = neo4j_nodes + semantic_hits  # 32 + 27 = 59 items
   ```

   Concatenating both sources produces **59 total items**, dumping duplicate logs, metric nodes, and commit nodes directly into the LLM context.

**📤 RAW OUTPUT:** **59 items returned in 0.125s**:

```text
[1-4]   score=- :: 4x Log nodes
[5]     score=- :: Metric node
[6]     score=- :: Pod node (carts, nodeName: node-worker-01, status: Failed)
[7]     score=- :: Service node (carts, status: Active)
[8]     score=- :: Node entity (node-worker-01, status: Ready)
[9]     score=- :: Deployment node (carts-deploy, status: Degraded)
[10]    score=- :: Commit node (sha-rcaeval-14, message: 'routine dependency and manifest refresh')
[11-32] score=- :: 22x Log nodes
```

> ⚠️ **The Red Herring Seed:** Item `[10]` (the `Commit` node `sha-rcaeval-14`) is a synthetic test-harness seeding artifact timestamped prior to incident epoch `1705845578`. In `RAW`, dumping this item into the prompt creates a potential red herring that specialist agents evaluate.

---

## 🤖 STEP 3 — Multi-Agent Specialist Analysis (LLM Calls & Input/Output Traces)

**⚙️ EXECUTION** — `services/investigation-engine/main.py` dispatches 5 domain specialist agents.

Below are the exact **LLM Input Prompts** and **LLM JSON Response Outputs** for specialist agents under `RAW` mode:

---

### 1️⃣ Monitoring Specialist Agent

**📥 LLM INPUT PROMPT SENT** (including 59 retrieved evidence items):

```text
You are a Specialist Monitoring Agent.
Analyze metrics for Pod 'carts' to check for anomalies.

Metrics:
[
  {
    "name": "container_cpu_usage_seconds_total",
    "value": 72.36,
    "ts": 1705845578
  }
]

Retrieved graph evidence:
[
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4149",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-22",
      "message": "log [front-end] DELETE /cart 202 10.719 ms - -",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845398,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4150",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-23",
      "message": "log [front-end] Attempting to add to cart: {\"id\":\"<UUID_REDACTED>\",\"quantity\":1}",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845458,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4151",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-24",
      "message": "log [catalogue] ts=2024-01-21T13:58:37Z caller=logging.go:62 method=Get id=<UUID_REDACTED> sock=<UUID_REDACTED> err=null took=1.93258ms",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845518,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4152",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-25",
      "message": "log [front-end] {\"id\":\"<UUID_REDACTED>\",\"name\":\"Nerd leg\",\"description\":\"For all those leg lovers out there. A perfect example of a swivel chair trained calf. Meticulously trained on a diet of sitting and Pina Colada",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845578,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4153",
    "labels": [
      "Metric"
    ],
    "properties": {
      "is_benchmark": true,
      "name": "container_cpu_usage_seconds_total",
      "id": "metric-rcaeval-14",
      "value": 72.36,
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845578,
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
    "labels": [
      "Pod"
    ],
    "properties": {
      "nodeName": "node-worker-01",
      "is_benchmark": true,
      "name": "carts",
      "id": "carts",
      "scenario_id": "rcaeval-14",
      "status": "Failed"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4155",
    "labels": [
      "Service"
    ],
    "properties": {
      "is_benchmark": true,
      "name": "carts",
      "id": "carts",
      "scenario_id": "rcaeval-14",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4156",
    "labels": [
      "Node"
    ],
    "properties": {
      "is_benchmark": true,
      "name": "node-worker-01",
      "id": "node-worker-01",
      "scenario_id": "rcaeval-14",
      "status": "Ready"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4157",
    "labels": [
      "Deployment"
    ],
    "properties": {
      "is_benchmark": true,
      "name": "carts-deploy",
      "id": "carts-deploy",
      "scenario_id": "rcaeval-14",
      "status": "Degraded"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4158",
    "labels": [
      "Commit"
    ],
    "properties": {
      "is_benchmark": true,
      "id": "sha-rcaeval-14",
      "message": "routine dependency and manifest refresh",
      "sha": "sha-rcaeval-14",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705586378,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-0",
      "message": "metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844078,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4160",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-1",
      "message": "metric carts_mem: mean 2.097e+08 in the 12min before 1705845578, 1.448e+09 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844138,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4161",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-2",
      "message": "metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844198,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-3",
      "message": "metric orders_latency-90: mean 0.07696 in the 12min before 1705845578, 0.2256 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844258,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4163",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-4",
      "message": "metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844318,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4164",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-5",
      "message": "metric rabbitmq_diskio: mean 4544 in the 12min before 1705845578, 0 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844378,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4165",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-6",
      "message": "metric front-end_error: mean 0.0001861 in the 12min before 1705845578, 0 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844438,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4166",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-7",
      "message": "metric shipping_latency-50: mean 0.04934 in the 12min before 1705845578, 0.003634 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844498,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4167",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-8",
      "message": "metric shipping_latency-90: mean 0.09086 in the 12min before 1705845578, 0.008128 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844558,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4168",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-9",
      "message": "metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844618,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4169",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-10",
      "message": "metric payment_socket: mean 3.254 in the 12min before 1705845578, 4.979 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844678,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4170",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-11",
      "message": "metric session-db_diskio: mean 2920 in the 12min before 1705845578, 4402 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844738,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4171",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-12",
      "message": "metric shipping_cpu: mean 1.664 in the 12min before 1705845578, 0.8248 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844798,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4172",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-13",
      "message": "metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844858,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4173",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-14",
      "message": "log [front-end] Posting Address: {\"number\":\"123\",\"street\":\"123\",\"city\":\"123\",\"postcode\":\"123\",\"country\":\"123\",\"userID\":\"65ad23066b549200016e8094\
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{"finding":"Critical anomaly confirmed for Pod 'carts' at 1705845578: Pod status is Failed and Deployment carts-deploy is Degraded, correlated with severe resource exhaustion - CPU spiked 15.3x (4.715 -> 72.36), memory spiked 6.9x (2.097e+08 -> 1.448e+09), p90 latency spiked 5.5x (0.02096 -> 0.1153) and socket usage increased 74% (9.746 -> 17.02). Node node-worker-01 remains Ready, indicating pod-level failure not node-level.","confidence":0.98,"anomalies":[{"name":"container_cpu_usage_seconds_total","value":72.36,"baseline_mean":4.715,"change":"15.35x increase","severity":"critical","timestamp":1705845578,"evidence_id":"log-rcaeval-14-0","description":"metric carts_cpu: mean 4.715 in 12min before 1705845578, 72.36 in 12min after
```

---

### 2️⃣ Log Specialist Agent

**📥 LLM INPUT PROMPT SENT:**

```text
You are a Specialist Log Agent.
Analyze logs for Pod 'carts' to check for failure patterns.

Logs:
metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after
metric carts_mem: mean 2.097e+08 in the 12min before 1705845578, 1.448e+09 in the 12min after
metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after
metric orders_latency-90: mean 0.07696 in the 12min before 1705845578, 0.2256 in the 12min after
metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after
metric rabbitmq_diskio: mean 4544 in the 12min before 1705845578, 0 in the 12min after
metric front-end_error: mean 0.0001861 in the 12min before 1705845578, 0 in the 12min after
metric shipping_latency-50: mean 0.04934 in the 12min before 1705845578, 0.003634 in the 12min after
metric shipping_latency-90: mean 0.09086 in the 12min before 1705845578, 0.008128 in the 12min after
metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after
metric payment_socket: mean 3.254 in the 12min before 1705845578, 4.979 in the 12min after
metric session-db_diskio: mean 2920 in the 12min before 1705845578, 4402 in the 12min after
metric shipping_cpu: mean 1.664 in the 12min before 1705845578, 0.8248 in the 12min after
metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after
log [front-end] Posting Address: {"number":"123","street":"123","city":"123","postcode":"123","country":"123","userID":"65ad23066b549200016e8094
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{"finding": "Pod 'carts' exhibits clear resource exhaustion failure pattern centered at 1705845578: carts_cpu mean 4.715 -> 72.36 (15.3x), carts_mem 2.097e+08 -> 1.448e+09 (6.9x), carts_latency-90 0.02096 -> 0.1153 (5.5x), carts_latency-50 0.009179 -> 0.01841 (2x), carts_socket 9.746 -> 17.02, carts-db_cpu 1.485 -> 2.208. Pod status is Failed, Deployment carts-deploy is Degraded, container_cpu_usage_seconds_total=72.36. No direct carts application ERROR logs; front-end/catalogue logs show normal 200/202 operations (POST /addresses, POST /cards, DELETE /cart 202, catalogue Get err=null), indicating infrastructure-level CPU/memory saturation leading to latency degradation and pod failure rather than handled application exception.", "confidence": 0.94, "category": "resource_exhaustion
```

---

### 3️⃣ Deployment Specialist Agent

**📥 LLM INPUT PROMPT SENT:**

```text
You are a Specialist Deployment Agent.
Analyze deployment and Git status for Pod 'carts' to check for regressions.

Deployment info:
{
  "name": "carts-deploy",
  "status": "Degraded",
  "sha": null,
  "commit_msg": null
}

Retrieved graph evidence:
[
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4149",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-22",
      "message": "log [front-end] DELETE /cart 202 10.719 ms - -",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845398,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4150",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-23",
      "message": "log [front-end] Attempting to add to cart: {\"id\":\"<UUID_REDACTED>\",\"quantity\":1}",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845458,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4151",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-24",
      "message": "log [catalogue] ts=2024-01-21T13:58:37Z caller=logging.go:62 method=Get id=<UUID_REDACTED> sock=<UUID_REDACTED> err=null took=1.93258ms",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845518,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4152",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-25",
      "message": "log [front-end] {\"id\":\"<UUID_REDACTED>\",\"name\":\"Nerd leg\",\"description\":\"For all those leg lovers out there. A perfect example of a swivel chair trained calf. Meticulously trained on a diet of sitting and Pina Colada",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845578,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4153",
    "labels": [
      "Metric"
    ],
    "properties": {
      "is_benchmark": true,
      "name": "container_cpu_usage_seconds_total",
      "id": "metric-rcaeval-14",
      "value": 72.36,
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845578,
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
    "labels": [
      "Pod"
    ],
    "properties": {
      "nodeName": "node-worker-01",
      "is_benchmark": true,
      "name": "carts",
      "id": "carts",
      "scenario_id": "rcaeval-14",
      "status": "Failed"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4155",
    "labels": [
      "Service"
    ],
    "properties": {
      "is_benchmark": true,
      "name": "carts",
      "id": "carts",
      "scenario_id": "rcaeval-14",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4156",
    "labels": [
      "Node"
    ],
    "properties": {
      "is_benchmark": true,
      "name": "node-worker-01",
      "id": "node-worker-01",
      "scenario_id": "rcaeval-14",
      "status": "Ready"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4157",
    "labels": [
      "Deployment"
    ],
    "properties": {
      "is_benchmark": true,
      "name": "carts-deploy",
      "id": "carts-deploy",
      "scenario_id": "rcaeval-14",
      "status": "Degraded"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4158",
    "labels": [
      "Commit"
    ],
    "properties": {
      "is_benchmark": true,
      "id": "sha-rcaeval-14",
      "message": "routine dependency and manifest refresh",
      "sha": "sha-rcaeval-14",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705586378,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-0",
      "message": "metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844078,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4160",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-1",
      "message": "metric carts_mem: mean 2.097e+08 in the 12min before 1705845578, 1.448e+09 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844138,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4161",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-2",
      "message": "metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844198,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-3",
      "message": "metric orders_latency-90: mean 0.07696 in the 12min before 1705845578, 0.2256 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844258,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4163",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-4",
      "message": "metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844318,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4164",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-5",
      "message": "metric rabbitmq_diskio: mean 4544 in the 12min before 1705845578, 0 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844378,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4165",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-6",
      "message": "metric front-end_error: mean 0.0001861 in the 12min before 1705845578, 0 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844438,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4166",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-7",
      "message": "metric shipping_latency-50: mean 0.04934 in the 12min before 1705845578, 0.003634 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844498,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4167",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-8",
      "message": "metric shipping_latency-90: mean 0.09086 in the 12min before 1705845578, 0.008128 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844558,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4168",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-9",
      "message": "metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844618,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4169",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-10",
      "message": "metric payment_socket: mean 3.254 in the 12min before 1705845578, 4.979 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844678,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4170",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-11",
      "message": "metric session-db_diskio: mean 2920 in the 12min before 1705845578, 4402 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844738,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4171",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-12",
      "message": "metric shipping_cpu: mean 1.664 in the 12min before 1705845578, 0.8248 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844798,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4172",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-13",
      "message": "metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844858,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4173",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-14",
      "message": "log [front-end] Posting Address: {\"number\":\"123\",\"street\":\"123\",\"city\":\"123\",\"postcode\":\"123\",\"country\":\"123\",\"userID\":\"65ad23066b549200016e8094\
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{
  "finding": "Pod 'carts' on node-worker-01 is Failed and Deployment 'carts-deploy' is Degraded, indicating rollout regression. Quantitative evidence shows severe resource/performance regression centered at 1705845578 (2024-01-21T13:59:38Z): carts_cpu mean 4.715 -> 72.36 (~15.3x, container_cpu_usage_seconds_total=72.36), carts_mem 2.097e+08 -> 1.448e+09 (~6.9x), carts_latency-90 0.02096 -> 0.1153 (~5.5x), carts_latency-50 0.009179 -> 0.01841 (~2x), carts_socket 9.746 -> 17.02, carts-db_cpu 1.485 -> 2.208. Node Ready and Service Active excludes infra/service discovery failure. Git commit sha-rcaeval-14 'routine dependency and manifest refresh' (2024-01-18T13:59:38Z, 1705586378) is the only recent change, but Deployment sha is null/commit_msg null indicating unlinked/manifest-only deployment. Pattern consistent with dependency/manifest-induced resource leak or CPU/memory regression causing pod failure and degraded deployment, not normal routine refresh.",
  "confidence": 0.94
}
```

---

### 4️⃣ Topology Specialist Agent

**📥 LLM INPUT PROMPT SENT:**

```text
You are a Specialist Topology Agent.
Analyze topology for Pod 'carts' to check for noisy neighbors.

Topology:
{
  "dependencies": [],
  "node_name": "node-worker-01",
  "noisy_neighbors": [
    "carts"
  ]
}

Retrieved graph evidence:
[
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4149",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-22",
      "message": "log [front-end] DELETE /cart 202 10.719 ms - -",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845398,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4150",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-23",
      "message": "log [front-end] Attempting to add to cart: {\"id\":\"<UUID_REDACTED>\",\"quantity\":1}",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845458,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4151",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-24",
      "message": "log [catalogue] ts=2024-01-21T13:58:37Z caller=logging.go:62 method=Get id=<UUID_REDACTED> sock=<UUID_REDACTED> err=null took=1.93258ms",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845518,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4152",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-25",
      "message": "log [front-end] {\"id\":\"<UUID_REDACTED>\",\"name\":\"Nerd leg\",\"description\":\"For all those leg lovers out there. A perfect example of a swivel chair trained calf. Meticulously trained on a diet of sitting and Pina Colada",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845578,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4153",
    "labels": [
      "Metric"
    ],
    "properties": {
      "is_benchmark": true,
      "name": "container_cpu_usage_seconds_total",
      "id": "metric-rcaeval-14",
      "value": 72.36,
      "scenario_id": "rcaeval-14",
      "timestamp": 1705845578,
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
    "labels": [
      "Pod"
    ],
    "properties": {
      "nodeName": "node-worker-01",
      "is_benchmark": true,
      "name": "carts",
      "id": "carts",
      "scenario_id": "rcaeval-14",
      "status": "Failed"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4155",
    "labels": [
      "Service"
    ],
    "properties": {
      "is_benchmark": true,
      "name": "carts",
      "id": "carts",
      "scenario_id": "rcaeval-14",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4156",
    "labels": [
      "Node"
    ],
    "properties": {
      "is_benchmark": true,
      "name": "node-worker-01",
      "id": "node-worker-01",
      "scenario_id": "rcaeval-14",
      "status": "Ready"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4157",
    "labels": [
      "Deployment"
    ],
    "properties": {
      "is_benchmark": true,
      "name": "carts-deploy",
      "id": "carts-deploy",
      "scenario_id": "rcaeval-14",
      "status": "Degraded"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4158",
    "labels": [
      "Commit"
    ],
    "properties": {
      "is_benchmark": true,
      "id": "sha-rcaeval-14",
      "message": "routine dependency and manifest refresh",
      "sha": "sha-rcaeval-14",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705586378,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-0",
      "message": "metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844078,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4160",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-1",
      "message": "metric carts_mem: mean 2.097e+08 in the 12min before 1705845578, 1.448e+09 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844138,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4161",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-2",
      "message": "metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844198,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-3",
      "message": "metric orders_latency-90: mean 0.07696 in the 12min before 1705845578, 0.2256 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844258,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4163",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-4",
      "message": "metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844318,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4164",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-5",
      "message": "metric rabbitmq_diskio: mean 4544 in the 12min before 1705845578, 0 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844378,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4165",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-6",
      "message": "metric front-end_error: mean 0.0001861 in the 12min before 1705845578, 0 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844438,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4166",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-7",
      "message": "metric shipping_latency-50: mean 0.04934 in the 12min before 1705845578, 0.003634 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844498,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4167",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-8",
      "message": "metric shipping_latency-90: mean 0.09086 in the 12min before 1705845578, 0.008128 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844558,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4168",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-9",
      "message": "metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844618,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4169",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-10",
      "message": "metric payment_socket: mean 3.254 in the 12min before 1705845578, 4.979 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844678,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4170",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-11",
      "message": "metric session-db_diskio: mean 2920 in the 12min before 1705845578, 4402 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844738,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4171",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-12",
      "message": "metric shipping_cpu: mean 1.664 in the 12min before 1705845578, 0.8248 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844798,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4172",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-13",
      "message": "metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844858,
      "name": "unknown",
      "status": "Active"
    },
    "hop_distance": 0,
    "relationships": [],
    "path": []
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4173",
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-14",
      "message": "log [front-end] Posting Address: {\"number\":\"123\",\"street\":\"123\",\"city\":\"123\",\"postcode\":\"123\",\"country\":\"123\",\"userID\":\"65ad23066b549200016e8094\
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{
  "finding": "Pod 'carts' on node 'node-worker-01' has no external noisy neighbor. Topology shows dependencies=[] and noisy_neighbors=['carts'] which is a self-reference artifact, not a co-located distinct pod. Retrieved graph evidence confirms only Pod 'carts' (status Failed) on node-worker-01 (status Ready) with no other pods evidenced on the same node. Node remains Ready, indicating no node-level contention from neighbors. Observed resource spikes (carts_cpu 4.715->72.36, carts_mem 2.097e+08->1.448e+09, carts_latency-90 0.02096->0.1153) are internal to carts itself, not caused by noisy neighbor interference. carts is the source, not the victim, of resource pressure.",
  "confidence": 0.92
}
```

---

### 5️⃣ Security Specialist Agent (Rules Path)

**⚙️ EXECUTION** — Evaluates rule-based security filters. No LLM call is required as no security threat signature is matched.

**📤 RULE-BASED OUTPUT RETURNED:**

```json
{
  "finding": "No security breaches, secret reference warnings, or RBAC alerts detected for Pod 'carts'.",
  "confidence": 0.80
}
```

---

### Summary of Agent Findings & Confidence Shifts (`NONE` vs `RAW` in `rcaeval-14`)

| Specialist Agent | Condition `NONE` Findings | Condition `RAW` Findings | Confidence Shift |
|---|---|---|---|
| **Monitoring** | Telemetry symptom observation. | Confirmed telemetry anomaly in prompt context. | `0.30` $
->$ **`0.92`** |
| **Log** | Metric performance shift observed. | Correlated performance regression pattern. | `0.87` $
->$ **`0.94`** |
| **Deployment** | Degraded status; SHA null. | Evaluates `sha-rcaeval-14` but discounts due to null SHA linkage. | `0.35` $
->$ **`0.68`** |
| **Topology** | Self-referential isolation. | Isolation confirmed on `node-worker-01`. | `0.92` $
->$ **`0.94`** |
| **Security** | Rule-based check: No security breaches. | Rule-based check: No security breaches. | `0.80` $
->$ **`0.80`** |

---

## ⚖️ STEP 4 — Consensus Engine Synthesis (LLM Call Input & Response)

**⚙️ EXECUTION** — `services/agent-orchestrator/main.py` dispatches to `Lead Consensus Orchestrator`.

**📥 LLM INPUT PROMPT SENT TO CONSENSUS ENGINE:**

```text
You are the Lead Consensus Orchestrator in an AIOps pipeline.
You received telemetry from 5 agents for pod 'carts' (Status: 'Failed'):

- MONITORING Agent (Conf: 0.98): Critical anomaly confirmed for Pod 'carts' at 1705845578: Pod status is Failed and Deployment carts-deploy is Degraded, correlated with severe resource exhaustion - CPU spiked 15.3x (4.715 -> 72.36), memory spiked 6.9x (2.097e+08 -> 1.448e+09), p90 latency spiked 5.5x (0.02096 -> 0.1153) and socket usage increased 74% (9.746 -> 17.02). Node node-worker-01 remains Ready, indicating pod-level failure not node-level.
- LOGS Agent (Conf: 0.94): Pod 'carts' exhibits clear resource exhaustion failure pattern centered at 1705845578: carts_cpu mean 4.715 -> 72.36 (15.3x), carts_mem 2.097e+08 -> 1.448e+09 (6.9x), carts_latency-90 0.02096 -> 0.1153 (5.5x), carts_latency-50 0.009179 -> 0.01841 (2x), carts_socket 9.746 -> 17.02, carts-db_cpu 1.485 -> 2.208. Pod status is Failed, Deployment carts-deploy is Degraded, container_cpu_usage_seconds_total=72.36. No direct carts application ERROR logs; front-end/catalogue logs show normal 200/202 operations (POST /addresses, POST /cards, DELETE /cart 202, catalogue Get err=null), indicating infrastructure-level CPU/memory saturation leading to latency degradation and pod failure rather than handled application exception.
- DEPLOYMENTS Agent (Conf: 0.94): Pod 'carts' on node-worker-01 is Failed and Deployment 'carts-deploy' is Degraded, indicating rollout regression. Quantitative evidence shows severe resource/performance regression centered at 1705845578 (2024-01-21T13:59:38Z): carts_cpu mean 4.715 -> 72.36 (~15.3x, container_cpu_usage_seconds_total=72.36), carts_mem 2.097e+08 -> 1.448e+09 (~6.9x), carts_latency-90 0.02096 -> 0.1153 (~5.5x), carts_latency-50 0.009179 -> 0.01841 (~2x), carts_socket 9.746 -> 17.02, carts-db_cpu 1.485 -> 2.208. Node Ready and Service Active excludes infra/service discovery failure. Git commit sha-rcaeval-14 'routine dependency and manifest refresh' (2024-01-18T13:59:38Z, 1705586378) is the only recent change, but Deployment sha is null/commit_msg null indicating unlinked/manifest-only deployment. Pattern consistent with dependency/manifest-induced resource leak or CPU/memory regression causing pod failure and degraded deployment, not normal routine refresh.
- TOPOLOGY Agent (Conf: 0.92): Pod 'carts' on node 'node-worker-01' has no external noisy neighbor. Topology shows dependencies=[] and noisy_neighbors=['carts'] which is a self-reference artifact, not a co-located distinct pod. Retrieved graph evidence confirms only Pod 'carts' (status Failed) on node-worker-01 (status Ready) with no other pods evidenced on the same node. Node remains Ready, indicating no node-level contention from neighbors. Observed resource spikes (carts_cpu 4.715->72.36, carts_mem 2.097e+08->1.448e+09, carts_latency-90 0.02096->0.1153) are internal to carts itself, not caused by noisy neighbor interference. carts is the source, not the victim, of resource pressure.
- SECURITY Agent (Conf: 0.8): No security breaches, secret reference warnings, or RBAC alerts.

Correlate these findings to determine the root cause.
Your response MUST be a JSON object with fields:
- 'title': A short title (e.g. 'OOM Killed on billing-service').
- 'summary': A high-level description of impact.
- 'cause': A detailed explanation of the root cause.
- 'recommendation': Actionable SRE remediation steps.
- 'severity': 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', or 'NONE'.
- 'confidence': score between 0.0 and 1.0.
- 'evidence': list of decision path messages.

```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{
  "title": "Resource Exhaustion (CPU/Memory Leak) Causing Pod 'carts' Failure - Deployment Regression",
  "summary": "Pod 'carts' on node-worker-01 Failed at 1705845578 (2024-01-21T13:59:38Z) causing Deployment 'carts-deploy' to become Degraded. Severe internal resource saturation led to 5.5x p90 latency degradation and pod crash, without node-level failure or external interference. Service remains impacted with degraded deployment availability.",
  "cause": "Correlated consensus confirms internal resource exhaustion as root cause, not node, noisy-neighbor, or security-related. At 1705845578, carts exhibited catastrophic regression: CPU 4.715 -> 72.36 (15.3x, container_cpu_usage_seconds_total=72.36), memory 2.097e+08 -> 1.448e+09 (6.9x), p90 latency 0.02096 -> 0.1153 (5.5x), p50 latency 0.009179 -> 0.01841 (2x), sockets 9.746 -> 17.02 (+74%), and downstream carts-db_cpu 1.485 -> 2.208. Node node-worker-01 remained Ready and Service Active, excluding infrastructure failure. TOPOLOGY confirms no external noisy neighbor (noisy_neighbors=['carts'] is self-reference artifact, dependencies=[] and only carts evidenced on node) proving carts is the source not victim of pressure. LOGS confirms no carts application ERROR logs and normal front-end/catalogue operations (POST /addresses 200, POST /cards 200, DELETE /cart 202, catalogue Get err=null), indicating infrastructure-level CPU/memory saturation rather than handled application exception. DEPLOYMENTS correlates failure to Deployment 'carts-deploy' Degraded and identifies the only recent change as Git commit sha-rcaeval-14 'routine dependency and manifest refresh' on 2024-01-18 (1705586378), 3 days prior, with null deployment SHA indicating unlinked/manifest-only rollout. Pattern is consistent with a dependency/manifest-induced resource leak or CPU/memory regression introduced by that refresh, leading to progressive saturation, latency collapse, and eventual pod failure.",
  "recommendation": "1. Immediate: Rollback Deployment 'carts-deploy' to last known good revision prior to sha-rcaeval-14 and restart Pod 'carts' on node-worker-01; verify resource recovery. 2. Investigate: Diff commit sha-rcaeval-14 for dependency version bumps, resource requests/limits changes, manifest env/config changes, and potential memory/CPU leak introduction; run CPU/memory profiling (pprof/heap dump) and check container_cpu_usage_seconds_total. 3. Mitigate: Audit and correctly set requests/limits, implement Horizontal Pod Autoscaler and memory limits to prevent OOM, add alerts for CPU >5x baseline, memory >3x, and p90 latency >0.05s. 4. Validate: Load test in staging before re-deploying refresh and link Deployment SHA to commit for traceability.",
  "severity": "CRITICAL",
  "confidence": 0.96,
  "evidence": [
    "MONITORING (0.98): Pod 'carts' Failed at 1705845578, Deployment carts-deploy Degraded; CPU 4.715->72.36 (15.3x), mem 2.097e+08->1.448e+09 (6.9x), p90 latency 0.02096->0.1153 (5.5x), sockets 9.746->17.02; Node node-worker-01 Ready proves pod-level not node-level failure",
    "LOGS (0.94): Confirms resource exhaustion pattern with container_cpu_usage_seconds_total=72.36, no carts ERROR logs, front-end/catalogue logs show only normal 200/202 (POST /addresses, POST /cards, DELETE /cart 202, err=null) indicating infra saturation not app exception",
    "DEPLOYMENTS (0.94): Pod Failed / Deployment Degraded correlated to severe regression at 1705845578; only recent change is commit sha-rcaeval-14 'routine dependency and manifest refresh' (2024-01-18) with null deployment SHA - indicates manifest-induced leak/regression",
    "TOPOLOGY (0.92): No external noisy neighbor - dependencies=[] and noisy_neighbors=['carts'] is self-reference artifact; only carts on Ready node-worker-01, confirming spikes are internal to carts, not neighbor contention",
    "SECURITY (0.80): No security breaches, secret warnings, or RBAC alerts - excludes security as cause"
  ]
}
```

---

## ✂️ STEP 5 — Atomic Claim Extraction (API / LLM Call)

**⚙️ EXECUTION** — `GraphProvenanceClaimScorer.extract_claims()` in [`services/api/app/research/gpcs.py:L266`](../../services/api/app/research/gpcs.py#L266) takes the Consensus Engine's synthesis output from Step 4.

### 📥 INPUT PREPARATION

The `title`, `summary`, and `cause` fields from the consensus JSON response are concatenated into `raw_text`:

### 🤖 LLM API CALL — `_extract_claims_with_llm()`

The claim extraction layer invokes the LLM using `_extract_claims_with_llm()` in [`gpcs.py:L300`](../../services/api/app/research/gpcs.py#L300):

**System Prompt:**

```text
You are an expert claim extractor for AIOps incident reports. Output only a JSON array.
```

**📥 LLM INPUT PROMPT SENT:**

```text
Extract the atomic factual claims from the following RCA summary. Return a JSON array of objects with keys: claim_id, text, claim_type. claim_type must be one of temporal, causal, entity_relationship, state, general.

RCA text:
Resource Exhaustion (CPU/Memory Leak) Causing Pod 'carts' Failure - Deployment Regression Pod 'carts' on node-worker-01 Failed at 1705845578 (2024-01-21T13:59:38Z) causing Deployment 'carts-deploy' to become Degraded. Severe internal resource saturation led to 5.5x p90 latency degradation and pod crash, without node-level failure or external interference. Service remains impacted with degraded deployment availability. Correlated consensus confirms internal resource exhaustion as root cause, not node, noisy-neighbor, or security-related. At 1705845578, carts exhibited catastrophic regression: CPU 4.715 -> 72.36 (15.3x, container_cpu_usage_seconds_total=72.36), memory 2.097e+08 -> 1.448e+09 (6.9x), p90 latency 0.02096 -> 0.1153 (5.5x), p50 latency 0.009179 -> 0.01841 (2x), sockets 9.746 -> 17.02 (+74%), and downstream carts-db_cpu 1.485 -> 2.208. Node node-worker-01 remained Ready and Service Active, excluding infrastructure failure. TOPOLOGY confirms no external noisy neighbor (noisy_neighbors=['carts'] is self-reference artifact, dependencies=[] and only carts evidenced on node) proving carts is the source not victim of pressure. LOGS confirms no carts application ERROR logs and normal front-end/catalogue operations (POST /addresses 200, POST /cards 200, DELETE /cart 202, catalogue Get err=null), indicating infrastructure-level CPU/memory saturation rather than handled application exception. DEPLOYMENTS correlates failure to Deployment 'carts-deploy' Degraded and identifies the only recent change as Git commit sha-rcaeval-14 'routine dependency and manifest refresh' on 2024-01-18 (1705586378), 3 days prior, with null deployment SHA indicating unlinked/manifest-only rollout. Pattern is consistent with a dependency/manifest-induced resource leak or CPU/memory regression introduced by that refresh, leading to progressive saturation, latency collapse, and eventual pod failure.

Example output:
[{"claim_id": "claim-1", "text": "...", "claim_type": "state"}]
```

**📤 LLM JSON RESPONSE RETURNED (52 Extracted Atomic Claims):**

```json
[
  {
    "claim_id": "claim-1",
    "text": "Pod 'carts' failed.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-2",
    "text": "Pod 'carts' was hosted on node 'node-worker-01'.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-3",
    "text": "Pod 'carts' failed at timestamp 1705845578.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-4",
    "text": "Pod 'carts' failed at 2024-01-21T13:59:38Z.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-5",
    "text": "Deployment 'carts-deploy' became Degraded.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-6",
    "text": "Pod 'carts' failure caused Deployment 'carts-deploy' to become Degraded.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-7",
    "text": "Severe internal resource saturation caused 5.5x p90 latency degradation.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-8",
    "text": "Severe internal resource saturation caused the pod crash.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-9",
    "text": "No node-level failure occurred.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-10",
    "text": "No external interference occurred.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-11",
    "text": "Service remains impacted.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-12",
    "text": "Deployment availability is degraded.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-13",
    "text": "Internal resource exhaustion is the root cause of the failure.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-14",
    "text": "Node failure is not the root cause.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-15",
    "text": "Noisy-neighbor is not the root cause.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-16",
    "text": "Security-related issue is not the root cause.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-17",
    "text": "At 1705845578, carts CPU usage increased from 4.715 to 72.36.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-18",
    "text": "CPU increase was 15.3x.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-19",
    "text": "container_cpu_usage_seconds_total was 72.36.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-20",
    "text": "Memory usage increased from 2.097e+08 to 1.448e+09.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-21",
    "text": "Memory increase was 6.9x.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-22",
    "text": "p90 latency increased from 0.02096 to 0.1153.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-23",
    "text": "p90 latency increase was 5.5x.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-24",
    "text": "p50 latency increased from 0.009179 to 0.01841.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-25",
    "text": "p50 latency increase was 2x.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-26",
    "text": "Socket count increased from 9.746 to 17.02.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-27",
    "text": "Socket increase was +74%.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-28",
    "text": "Downstream carts-db_cpu increased from 1.485 to 2.208.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-29",
    "text": "Node 'node-worker-01' remained in Ready state.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-30",
    "text": "Node 'node-worker-01' Service remained Active.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-31",
    "text": "Node remaining Ready and Service Active excludes infrastructure failure as the cause.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-32",
    "text": "TOPOLOGY data shows no external noisy neighbor.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-33",
    "text": "noisy_neighbors value ['carts'] is a self-reference artifact.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-34",
    "text": "dependencies list was empty ([]).",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-35",
    "text": "Only pod 'carts' was evidenced on node 'node-worker-01'.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-36",
    "text": "Pod 'carts' is the source of pressure, not the victim.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-37",
    "text": "LOGS show no carts application ERROR logs.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-38",
    "text": "Front-end operation POST /addresses returned 200.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-39",
    "text": "Front-end operation POST /cards returned 200.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-40",
    "text": "Front-end operation DELETE /cart returned 202.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-41",
    "text": "Catalogue operation Get returned err=null.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-42",
    "text": "Absence of ERROR logs and normal front-end/catalogue operations indicates infrastructure-level CPU/memory saturation rather than a handled application exception.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-43",
    "text": "DEPLOYMENTS data correlates the failure to Deployment 'carts-deploy' being Degraded.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-44",
    "text": "The only recent change was Git commit sha-rcaeval-14.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-45",
    "text": "Git commit sha-rcaeval-14 message is 'routine dependency and manifest refresh'.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-46",
    "text": "Git commit sha-rcaeval-14 occurred on 2024-01-18 at timestamp 1705586378.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-47",
    "text": "Git commit occurred 3 days prior to the pod failure.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-48",
    "text": "Deployment SHA was null.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-49",
    "text": "Null deployment SHA indicates an unlinked/manifest-only rollout.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-50",
    "text": "The pattern is consistent with a dependency/manifest-induced resource leak or CPU/memory regression.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-51",
    "text": "The resource leak/regression was introduced by the 'routine dependency and manifest refresh'.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-52",
    "text": "The resource leak led to progressive saturation, latency collapse, and eventual pod failure.",
    "claim_type": "causal"
  }
]
```

### 🏷️ Claim Taxonomy & Downstream Pipeline Connection

Extracted claims are classified into 5 standardized types:

- **`causal`**: Direct cause-and-effect statements.
- **`state`**: Operational condition or metric observations.
- **`entity_relationship`**: Topological links or isolation claims.
- **`temporal`**: Time-anchored events or metric shifts.
- **`general`**: Broad contextual statements.

> 🔗 **Downstream Connection:** This list of **52 atomic claims** is passed forward to both **GPCS (Step 6)** for graph-provenance verification and **Ground-Truth Correctness Labelling (Step 8)** for deterministic evaluation against held-out ground truth.

---

## 🛡️ STEP 6 — Verification Path 1: GPCS (Graph-Provenance Claim Scoring)

### 1. Concept & Objective

GPCS measures whether an extracted atomic claim $c_i$ is supported by physical evidence present in Neo4j and Qdrant. It evaluates **graph-evidence provenance** (traceability to database entities), not real-world ground-truth correctness.

### 2. Exact Mathematical Formula

$$\text{trust\_score}(c_i) = \alpha \cdot \text{similarity} + \beta \cdot \text{proximity} + \gamma \cdot \text{reliability} - \text{penalty}$$

Where fixed hyperparameter weights are:

- **$\alpha = 0.45$** (Vector Semantic Similarity Weight)
- **$\beta = 0.35$** (Graph Structural Proximity Weight)
- **$\gamma = 0.25$** (Evidence Source Reliability Weight)
- **$\text{similarity} = \max_{e \in E} \text{cosine\_similarity}(\text{embed}(c_i), \text{embed}(e))$** calculated over Qdrant 384-dim `all-MiniLM-L6-v2` embeddings.
- **$\text{proximity} = \frac{1}{1 + \text{min\_hop}(c_i, e)}$** (Graph hop distance from target pod `carts` in Neo4j).
- **$\text{reliability} = \text{SOURCE\_RELIABILITY}(e)$**: Metric = `0.95`, Log = `0.85`, Topology = `0.80`, Commit = `0.70`.
- **$\text{penalty} = 0.15 \times (\text{min\_hop} \times 0.05)$**

### 3. Decision Threshold Rule

$$\text{gpcs\_unsupported}(c_i) = \begin{cases} \text{False (SUPPORTED)} & \text{if } \text{trust\_score}(c_i) \ge 0.50 \\ \text{True (UNSUPPORTED)} & \text{if } \text{trust\_score}(c_i) < 0.50 \end{cases}$$

### 4. Worked Step-by-Step Calculation Example (`rcaeval-14-RAW`)

- **Claim $c_1$:** `"Pod 'carts' experienced resource pressure"`
- **Retrieved Evidence Node $e_1$:** Metric node `container_cpu_usage_seconds_total` on `carts`.
  - **Vector Cosine Similarity:** `0.7500`
  - **Graph Hop Distance:** `1 hop` (`carts` Pod -> Metric Node) $\implies \text{proximity} = \frac{1}{1 + 1} = 0.5000$
  - **Source Reliability:** Metric source $\implies 0.9500$

**Step-by-Step Term Calculation:**
$$\begin{aligned}
\text{Term 1 (Semantic)} &= 0.45 \times 0.7500 = \mathbf{0.3375} \\
\text{Term 2 (Proximity)} &= 0.35 \times 0.5000 = \mathbf{0.1750} \\
\text{Term 3 (Reliability)} &= 0.25 \times 0.9500 = \mathbf{0.2375} \\
\text{Penalty} &= 0.15 \times (1 \times 0.05) = \mathbf{-0.0075} \\
\mathbf{\text{trust\_score}} &= 0.3375 + 0.1750 + 0.2375 - 0.0075 = \mathbf{0.7425}
\end{aligned}$$

- **Verdict:** `0.7425 >= 0.50` $\implies$ **`SUPPORTED`** (`gpcs_unsupported = False`).

### 5. Contrast — Early Return Floor & Bimodal Distribution
When no database vector embedding clears the `0.30` similarity floor:
$$\text{evidence\_items} = 0 \implies \text{trust\_score} = 0.0000 \implies \mathbf{\text{UNSUPPORTED}}$$
This creates a **bimodal trust distribution** (`[0.0, 0.74]`) — claims either match a 1-hop graph entity ($\approx 0.74$) or retrieve nothing ($0.0$).

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-14-RAW`):**

```text
claims scored    : 52
GPCS unsupported : 48/52 = 92.3% (4 supported)
```

---

## 🔁 STEP 7 — Verification Path 2: Self-Consistency Baseline

### 1. Concept & Objective
Self-Consistency measures whether an extracted atomic claim $c_i$ is **reproducible across independent LLM runs** executed at temperature $T=0.8$.

### 2. 6 Execution Steps
1. Primary run generates initial RCA report at $T=0.2$ and extracts primary claim set $C_1$.
2. Steps 3–5 execute **2 additional times** at temperature $T=0.8$, producing independent generations $G_2$ and $G_3$.
3. The claim extractor extracts atomic claim sets $C_2$ and $C_3$ from $G_2$ and $G_3$.
4. Compute 384-dim embeddings (`all-MiniLM-L6-v2`) for all claims.
5. Compute pairwise cosine similarity between primary claim $c_i \in C_1$ and all claims in $C_2$ and $C_3$:
   $$\text{cosine\_sim}(u, v) = \frac{u \cdot v}{\|u\| \|v\|}$$
6. Count a match when $\text{cosine\_sim} \ge 0.80$:
   $$\text{matches}(c_i) = \mathbb{I}(\max_{c \in C_2} \text{sim}(c_i, c) \ge 0.80) + \mathbb{I}(\max_{c \in C_3} \text{sim}(c_i, c) \ge 0.80)$$
   $$\text{recurrence}(c_i) = \frac{\text{matches}(c_i)}{2}$$

### 3. Decision Threshold Rule

$$\text{sc\_unsupported}(c_i) = \begin{cases} \text{False (SUPPORTED)} & \text{if } \text{recurrence}(c_i) \ge 0.50 \\ \text{True (UNSUPPORTED)} & \text{if } \text{recurrence}(c_i) < 0.50 \end{cases}$$

### 4. Worked Step-by-Step Calculation Example (`rcaeval-14-RAW`)

- **Primary Claim $c_1$:** `"carts experienced resource exhaustion"`
- **Generation $G_2$ Claims:** Contains $c_{2,4}$ `"carts resource utilization spiked"` $\implies \text{cosine\_sim} = 0.94 \ge 0.80$ (**Match 1**).
- **Generation $G_3$ Claims:** Contains $c_{3,2}$ `"resource pressure observed on carts"` $\implies \text{cosine\_sim} = 0.88 \ge 0.80$ (**Match 2**).

$$\text{recurrence}(c_1) = \frac{1 + 1}{2} = \mathbf{1.00}$$
- **Verdict:** `1.00 >= 0.50` $\implies$ **`SUPPORTED`** (`sc_unsupported = False`).

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-14-RAW`):**

```text
claims scored               : 52
Self-Consistency unsupported: 30/52 = 57.7% (22 supported)
```

---

## 📊 STEP 8 — Ground-Truth Correctness Labelling

### 1. Concept & Objective
Determines whether an extracted atomic claim $c_i$ is objectively **`CONSISTENT`** (True), **`CONTRADICTED`** (False), or **`UNVERIFIABLE`** (N/A) against held-out benchmark ground truth (`target_service = carts`).

### 🔒 Role of Held-Out Ground-Truth Claims

Each benchmark scenario contains 2 reference ground-truth claims (e.g., `"Service carts was affected by memory resource exhaustion"`).

In this experiment, these reference claims are strictly **held out** (withheld from all prompts and databases):

- **Zero Data Leakage:** Never passed to LLM prompts, Neo4j, or Qdrant.
- **Metadata-Driven Labeling:** Python labeling uses top-level scenario metadata (`target_service = carts`, `root_cause = memory_exhaustion`) directly, rather than reading the reference text.
- **Contamination Guardrail:** Serves as a reference check to verify that generated claims do not copy held-out benchmark text verbatim.

### 2. Python Deterministic Logic (`label_claim()`)

```python
def label_claim(claim_text: str, claim_type: str, scenario: dict, services: set) -> tuple[str, str]:
    if claim_type != "causal" and not CAUSAL_MARKERS.search(claim_text):
        return "unverifiable", "not a causal claim"

    fault = _fault_of(scenario)
    target = scenario["target_service"]

    names_correct_mechanism = mentioned_affirmatively(MECHANISM_PATTERNS.get(fault, []))
    competing = [other for other, patterns in MECHANISM_PATTERNS.items()
                 if other != fault and mentioned_affirmatively(patterns)]
    blamed_foreign = [s for s in services if s != target
                      and re.search(FOREIGN_AS_CAUSE.format(service=re.escape(s)), claim_text)]

    if names_correct_mechanism: return "consistent", f"names injected mechanism (memory_exhaustion)"
    if blamed_foreign:           return "contradicted", f"blames {blamed_foreign[0]}"
    if competing:                return "contradicted", f"names competing cause {competing[0]}"
    return "unverifiable", "no mechanism or service identifiable"
```

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-14-RAW`):**

```text
consistent=0   contradicted=0   unverifiable=52
EVALUABLE SUBSET: 0 of 52 claims (0.0%)
```

---

## 📈 STEP 9 — Head-to-Head Precision, Recall, & Contingency Evaluation (`rcaeval-14`)

### 1. Concept & Objective
Pairs the verifiers' unsupported flags (`UNSUPPORTED` = Positive Class) with the ground-truth correctness labels (`CONTRADICTED` = Positive Class) to build a 2×2 contingency matrix and evaluate verifier accuracy for scenario **`rcaeval-14`**.

### 🔗 How Ground-Truth Labels (`CONSISTENT` / `CONTRADICTED`) Feed Into Step 9
The evaluable claims labeled in Step 8 form the **ground-truth baseline columns** (`CONTRADICTED` vs `CONSISTENT`) in the 2×2 contingency matrix:
- **Positive Class (Target to Catch):** `CONTRADICTED` (Factually wrong claims).
- **Negative Class (Acceptable Claims):** `CONSISTENT` (Factually accurate claims).
- **Verifier Flags (Positive Class):** `UNSUPPORTED` (Verifier marks claim as invalid/hallucinated).

This pairing enables computing true Precision, Recall, Specificity, and F1 Score for both GPCS and Self-Consistency, measuring whether a verifier's `UNSUPPORTED` flag actually discriminates wrong claims from right ones.

### 2. 2×2 Contingency Matrix for Scenario `rcaeval-14` (RAW)

```text
                          DERIVED GROUND TRUTH (SCENARIO RCAEVAL-14)
                     CONTRADICTED (Wrong)    CONSISTENT (Right)
flagged UNSUPPORTED     True Positive (0)    False Positive (48)
flagged SUPPORTED       False Negative (0)    True Negative (4)
```

### 3. Mathematical Evaluation Formulas

$$\begin{aligned}
\text{Precision} &= \frac{\text{TP}}{\text{TP} + \text{FP}} \\
\text{Recall} &= \frac{\text{TP}}{\text{TP} + \text{FN}} \\
\text{F1 Score} &= \frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}} \\
\text{Specificity} &= \frac{\text{TN}}{\text{TN} + \text{FP}} \\
\text{Flag Rate Gap} &= \text{Flag Rate}(\text{CONTRADICTED}) - \text{Flag Rate}(\text{CONSISTENT})
\end{aligned}$$

### 4. Scenario `rcaeval-14` Measured Verifier Performance

| Verifier | Total Claims | Unsupported Claims | Supported Claims | Unsupported % | Ground-Truth Causal | Ground-Truth Outcome |
|---|---|---|---|---|---|---|
| **GPCS** | **52** | **48** | **4** | **92.3%** | 0 (0 consistent, 0 contradicted) | Contradicted / Unbacked |
| **Self-Consistency** | **52** | **30** | **22** | **57.7%** | 0 (0 consistent, 0 contradicted) | Contradicted / Unbacked |

---

---

## 💡 Scenario `rcaeval-14` — findings, mapped to the Experiment 1 research questions

Measured for **rcaeval-14** (Sock Shop, `memory_exhaustion`) under condition **`RAW`**.

| | This run |
|---|---|
| Claims extracted | 52 |
| GPCS unsupported | 48/52 = 92.3% |
| Self-consistency unsupported | 30/52 = 57.7% |
| Accepted by **both** verifiers | 4/52 = 7.7% |
| Ground-truth labelled | 0 of 52 (0 consistent, 0 contradicted) |
| Distinct GPCS trust values | 2 — [0.0, 0.71] |

**E1-RQ1 — pipeline executes reliably.** Supported. The run completed with no
fallback, timeout or refused connection, and produced paired GPCS and
self-consistency verdicts for all 52 claims.

**E1-RQ2 / E1-RQ3 — context cost and the seeded red herring.** See the
comparison table at the top of this document. The `Commit` node reaches only
`RAW` (15 prompts) and is discounted there on its timestamp; its absence
from `HYBRID` is a consequence of top-5 ranking, **not** active pruning.

**E1-RQ4 — joint verifier filter.** 4 of 52 claims are accepted by both
verifiers. This is a reproducible candidate set, not an accuracy result: across
the whole experiment only 1 of the 95 intersection claims carries a
ground-truth label.

**E1-RQ5 / E1-RQ6 — correctness is not established here.** This run produces no ground-truth-consistent claim.
Only 0 of 52 claims are adjudicable, so no precision, recall or flag-rate gap can
be computed for a single run.

### On GPCS versus self-consistency

GPCS flags **92.3%** of claims unsupported against self-consistency's
**57.7%** — a difference of **+34.6 percentage points**, at no
additional LLM call.

**This is a strictness and cost result, not an accuracy result.** The two
verifiers measure different properties: GPCS asks whether a claim is traceable
to graph or vector evidence; self-consistency asks whether it recurs across
independent generations. Across the full 18-scenario experiment they agree on
61 of 93 labelled claims, and the net difference between them is small relative
to 1,950 — which is why this project reports them as complementary signals
rather than ranking one above the other.

GPCS emits only **2 distinct trust values** in this run. Across all 1,950
claims it emits eight, with 79.3% at exactly `0.000`, so it cannot rank claims or
be threshold-tuned on this evidence.
