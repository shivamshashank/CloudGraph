# CloudGraph — complete sequential input-to-output chain (Condition `NONE`)

A strictly sequential breakdown of how CloudGraph operates under **Condition `NONE`** (baseline execution without retrieval context). Each step states:

1. **📥 INPUT** — what data enters
2. **⚙️ EXECUTION** — what code processes it
3. **📤 OUTPUT** — what is produced
4. **🔗 CONNECTION** — how that output becomes the next step's input

Illustrated throughout with scenario **`rcaeval-03`** (*Train Ticket*, target pod: `ts-order-service`, injected fault: `cpu_exhaustion` at timestamp `1705935125`).

> Every value is quoted from `01-rcaeval-03/rcaeval-03-NONE.log`, written live by `scripts/trace_scenario.py` (265.9s wall time).

---

## 📌 STEP 1 — Telemetry ingestion and database seeding

**📥 INPUT** — scenario `rcaeval-03` from RCAEval RE2 (Train Ticket):

| Property | Value |
|---|---|
| Target pod | `ts-order-service` on node `node-worker-01` |
| Injected fault | `cpu_exhaustion` at epoch `1705935125` |
| Observed symptoms | 26 telemetry symptom lines |
| Held out | 2 ground-truth claims — never prompted |

```text
metric ts-order-service_cpu: mean baseline in the 12min before 1705935125
metric ts-order-service_mem: mean baseline in the 12min before 1705935125
   ... 24 more telemetry lines
```

**⚙️ EXECUTION** — `seed_scenario_data()` in `services/api/app/demo/seeding.py`:

- Cypher `MERGE` writes entities and typed relationships into **Neo4j**
- `semantic_store.index_document()` writes 384-dim `all-MiniLM-L6-v2` embeddings into **Qdrant**

**📤 OUTPUT** — measured deltas in the log:

```text
Neo4j   Log       3538 -> 3564   (+26, one per symptom)
        Metric     238 -> 239    (+1)
        Node         1 -> 2      (+1)
        Pod          9 -> 10     (+1)
        Service     10 -> 11     (+1)
        Deployment   6 -> 7      (+1)
        Commit       0 -> 1      (+1)
Qdrant  evidence  3558 -> 3585   (+27, duplicate-vector fix active)
```

Then the isolation assertion: **PASSED** — the vector store holds strictly this scenario's evidence.

**🔗 CONNECTION → STEP 2** — the populated Neo4j and Qdrant are now available for database operations.

---

## 🔍 STEP 2 — GraphRAG evidence retrieval

**📥 INPUT**

- Seed pod: `ts-order-service`
- Query: `"ts-order-service degraded performance investigation"`
- The stores from Step 1

**⚙️ EXECUTION** — `_retrieval_results_for_condition()` in `report_runner.py`:

```python
if condition == "none":
    return None                                    # ← this run
if condition == "raw":
    return run_raw_context_search(query, scenario_id=...)
return run_hybrid_search(query, reference_time=..., scenario_id=...)
```

Under `none` the function **returns before any query runs** — no Qdrant call, no graph traversal.

For contrast, `hybrid` would rank candidates by:

$$\text{hybrid\_score} = 0.50 \cdot \text{vector\_similarity} + 0.30 \cdot \text{graph\_proximity} + 0.20 \cdot \text{recency}$$

**📤 OUTPUT**

```text
condition=none   returned 0 items in 0.000s (no LLM involved)
```

**🔗 CONNECTION → STEP 3** — the (empty) `retrieval_context` is attached to the orchestrator payload. The agents therefore work from telemetry symptoms plus each agent's own Neo4j queries.

---

## 🤖 STEP 3 — Multi-agent specialist analysis

**📥 INPUT** — pod metadata (`ts-order-service`, `Failed`, `cloudgraph-system`), the 26 symptoms, and the empty retrieval context.

**⚙️ EXECUTION** — `services/investigation-engine/main.py` dispatches five specialists:

| Agent | Function | Line in `main.py` |
|---|---|---|
| Monitoring | `run_monitoring_agent` | **391** |
| Log | `run_log_agent` | **480** |
| Deployment | `run_deployment_agent` | **563** |
| Topology | `run_topology_agent` | **647** |
| Security | `run_security_agent` | **739** |

---

### 1️⃣ Monitoring specialist

**📥 Prompt sent:**

```text
You are a Specialist Monitoring Agent.
Analyze metrics for Pod 'ts-order-service' to check for anomalies.

Metrics:
[
  {
    "name": "container_cpu_usage_seconds_total",
    "value": 37.52,
    "ts": 1705935125
  }
]

Output JSON with: 'finding', 'confidence', 'anomalies'.
```

**📤 Response:**

```json
{
  "finding": "insufficient_data - single data point for container_cpu_usage_seconds_total (37.52) cannot determine rate or anomaly, no anomaly detected",
  "confidence": 0.35,
  "anomalies": []
}
```

---

### 2️⃣ Log specialist

**📥 Prompt sent:**

```text
You are a Specialist Log Agent.
Analyze logs for Pod 'ts-order-service' to check for failure patterns.

Logs:
metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after
metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after
metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after
metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after
metric ts-user-service_latency-90: mean 0.3185 in the 12min before 1705935125, 0.02313 in the 12min after
metric ts-assurance-service_latency-90: mean 0.2479 in the 12min before 1705935125, 0.01962 in the 12min after
metric ts-consign-price-service_latency-90: mean 0.2664 in the 12min before 1705935125, 0.02301 in the 12min after
metric ts-user-service_latency-50: mean 0.1637 in the 12min before 1705935125, 0.01572 in the 12min after
metric ts-payment-service_latency-90: mean 0.2192 in the 12min before 1705935125, 0.02844 in the 12min after
metric ts-consign-service_latency-90: mean 0.5301 in the 12min before 1705935125, 0.08559 in the 12min after
metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after
metric ts-admin-basic-info-service_latency-90: mean 0.1138 in the 12min before 1705935125, 0.02441 in the 12min after
metric ts-admin-travel-service_latency-90: mean 1.032 in the 12min before 1705935125, 0.2397 in the 12min after
metric ts-consign-price-service_latency-50: mean 0.06286 in the 12min before 1705935125, 0.01507 in the 12min after
log [ts-travel2-service] 2024-01-22 14:51:04.501  INFO 1 --- [io-16346-exec-3] travel2.service.Travel2ServiceImpl       : [Travel Other Service][Get Route By Id] Success.
log [ts-travel-service] 2024-01-22 14:51:04.501  INFO 1 --- [io-12346-exec-4] travel.service.TravelServiceImpl         : [Travel Service][Get Route By Id] Route ID：<UUID_REDACTED>
log [ts-route-service] 2024-01-22 14:51:04.503  INFO 1 --- [io-11178-exec-1] route.controller.RouteController         : Route id: <UUID_REDACTED>
log [ts-travel-service] 2024-01-22 14:51:04.506  INFO 1 --- [io-12346-exec-4] travel.service.TravelServiceImpl         : Routes Response is : Response(status=1, msg=Success, data={id=<UUID_REDACTED>, stations=[nanjing, suzho
log [ts-travel-service] 2024-01-22 14:51:04.507  INFO 1 --- [io-12346-exec-4] travel.service.TravelServiceImpl         : Route is: Route{id='<UUID_REDACTED>', stations=[nanjing, suzhou, shanghai], distances=[0, 200, 250], st
log [ts-basic-service] 2024-01-22 14:51:04.508  INFO 1 --- [io-15680-exec-9] f.microservice.service.BasicServiceImpl  : [Basic Information Service][Check Station Exists] Station Name: Nan Jing
log [ts-travel-service] 2024-01-22 14:51:04.512  INFO 1 --- [io-12346-exec-4] travel.service.TravelServiceImpl         : [Travel Service][Get Route By Id] Route ID：<UUID_REDACTED>
log [ts-basic-service] 2024-01-22 14:51:04.514  INFO 1 --- [io-15680-exec-9] f.microservice.service.BasicServiceImpl  : [Basic Information Service][Check Station Exists] Station Name: Shang Hai
log [ts-route-service] 2024-01-22 14:51:04.515  INFO 1 --- [o-11178-exec-11] route.controller.RouteController         : Route id: <UUID_REDACTED>
log [ts-travel-service] 2024-01-22 14:51:04.518  INFO 1 --- [io-12346-exec-4] travel.service.TravelServiceImpl         : Routes Response is : Response(status=1, msg=Success, data={id=<UUID_REDACTED>, stations=[suzhou, shangh
log [ts-travel-service] 2024-01-22 14:51:04.518  INFO 1 --- [io-12346-exec-4] travel.service.TravelServiceImpl         : Route is: Route{id='<UUID_REDACTED>', stations=[suzhou, shanghai], distances=[0, 50], startStationId='s
log [ts-basic-service] 2024-01-22 14:51:04.519  INFO 1 --- [io-15680-exec-9] f.microservice.service.BasicServiceImpl  : [Basic Information Service][Query Train Type] Train Type: ZhiDa

Output JSON with: 'finding', 'confidence', 'category'.
```

**📤 Response:**

```json
{"finding":"No error/failure log patterns detected for ts-order-service in provided window - zero ts-order-service log lines present, all 12 sampled logs are INFO Success from ts-travel-service, ts-travel2-service, ts-route-service, ts-basic-service at 2024-01-22 14:51:04. Metrics show isolated post-1705935125 degradation for ts-order-service: cpu mean 5.289->37.52 (+609%), latency-50 0.01019->0.03552 (3.48x), latency-90 0.03546->0.08698 (2.45x), diskio 1.216e+06->5.201e+04 (-95.7%), while 8 other services' latency-50/90 all decreased 4-13x (e.g., ts-user-service p90 0.3185->0.02313), indicating CPU-bound saturation/performance anomaly isolated to ts-order-service without logged exceptions.","confidence":0.89,"category":"performance_degradation
```

---

### 3️⃣ Deployment specialist

**📥 Prompt sent:**

```text
You are a Specialist Deployment Agent.
Analyze deployment and Git status for Pod 'ts-order-service' to check for regressions.

Deployment info:
{
  "name": "ts-order-service-deploy",
  "status": "Degraded",
  "sha": null,
  "commit_msg": null
}

Output JSON with: 'finding', 'confidence'.
```

**📤 Response:**

```json
{"finding": "Deployment ts-order-service-deploy is Degraded but Git metadata is unavailable (sha: null, commit_msg: null) - cannot correlate degraded status to a specific commit or determine if regression was introduced. Manual investigation of pod logs/events and Git history required.", "confidence": "low
```

---

### 4️⃣ Topology specialist

**📥 Prompt sent:**

```text
You are a Specialist Topology Agent.
Analyze topology for Pod 'ts-order-service' to check for noisy neighbors.

Topology:
{
  "dependencies": [],
  "node_name": "node-worker-01",
  "noisy_neighbors": [
    "ts-order-service"
  ]
}

Output JSON with: 'finding', 'confidence'.
```

**📤 Response:**

```json
{
  "finding": "Pod 'ts-order-service' on node 'node-worker-01' is flagged as a noisy neighbor. It has no dependencies and is the sole entry in the noisy_neighbors list, indicating it is the source of resource contention on its host node rather than being victim to other co-located pods.",
  "confidence": 0.95
}
```

---

### 5️⃣ Security specialist — **no LLM call**

**⚙️ EXECUTION** — rule-based fallback path evaluated (0 LLM calls):

```python
if threat_detected:
    llm_res = _call_llm_agent(...)
finding, confidence = _analyze_security_rules(metadata, threat_detected)
```

**📤 Response:**

```json
{
  "finding": "No security breaches, secret reference warnings, or RBAC alerts detected for Pod 'ts-order-service'.",
  "confidence": 0.80
}
```

---

**📤 STEP 3 OUTPUT** — an array of five findings:
`[monitoring, logs, deployments, topology, security]`

**🔗 CONNECTION → STEP 4** — that array is passed to `ConsensusEngine.resolve_incident()`.

---

## ⚖️ STEP 4 — Consensus synthesis

**📥 INPUT** — the five findings from Step 3.

**⚙️ EXECUTION** — `services/agent-orchestrator/main.py`.

**Path A — LLM synthesis (used here).** The five findings are formatted into one prompt:

**📥 LLM INPUT PROMPT SENT:**

```text
You are the Lead Consensus Orchestrator in an AIOps pipeline.
You received telemetry from 5 agents for pod 'ts-order-service' (Status: 'Failed'):

- MONITORING Agent (Conf: 0.35): insufficient_data - single data point for container_cpu_usage_seconds_total (37.52) cannot determine rate or anomaly, no anomaly detected
- LOGS Agent (Conf: 0.89): No error/failure log patterns detected for ts-order-service in provided window - zero ts-order-service log lines present, all 12 sampled logs are INFO Success from ts-travel-service, ts-travel2-service, ts-route-service, ts-basic-service at 2024-01-22 14:51:04. Metrics show isolated post-1705935125 degradation for ts-order-service: cpu mean 5.289->37.52 (+609%), latency-50 0.01019->0.03552 (3.48x), latency-90 0.03546->0.08698 (2.45x), diskio 1.216e+06->5.201e+04 (-95.7%), while 8 other services' latency-50/90 all decreased 4-13x (e.g., ts-user-service p90 0.3185->0.02313), indicating CPU-bound saturation/performance anomaly isolated to ts-order-service without logged exceptions.
- DEPLOYMENTS Agent (Conf: 0.35): Deployment ts-order-service-deploy is Degraded but Git metadata is unavailable (sha: null, commit_msg: null) - cannot correlate degraded status to a specific commit or determine if regression was introduced. Manual investigation of pod logs/events and Git history required.
- TOPOLOGY Agent (Conf: 0.95): Pod 'ts-order-service' on node 'node-worker-01' is flagged as a noisy neighbor. It has no dependencies and is the sole entry in the noisy_neighbors list, indicating it is the source of resource contention on its host node rather than being victim to other co-located pods.
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

**Path B — static weighted aggregation (NOT used here).** Documented for fallback when LLM is unavailable:

$$\text{Confidence} = 0.30(\text{log}) + 0.20(\text{monitoring}) + 0.20(\text{deployment}) + 0.15(\text{topology}) + 0.15(\text{security})$$

**That path did not run.** The LLM performed the synthesis directly.

**📤 LLM JSON RESPONSE RETURNED:**

```json
{
  "title": "CPU Saturation Noisy Neighbor Failure on ts-order-service",
  "summary": "Pod 'ts-order-service' on node 'node-worker-01' has Failed due to isolated CPU-bound resource saturation. Impact is isolated to ts-order-service with no cascading failures to 8 other co-located services, which show 4-13x latency improvement in the same window.",
  "cause": "Correlated high-confidence signals indicate a performance/resource exhaustion failure, not a code deployment or security event. LOGS Agent (0.89) shows a clear isolated degradation post-1705935125: CPU mean 5.289 -> 37.52 (+609%), latency p50 0.01019 -> 0.03552 (3.48x), p90 0.03546 -> 0.08698 (2.45x), and disk IO 1.216e+06 -> 5.201e+04 (-95.7%) consistent with CPU starvation/busy-loop where the service is burning CPU and not performing IO. In contrast, 8 other services' p50/p90 latencies all decreased 4-13x (e.g., ts-user-service p90 0.3185 -> 0.02313), proving the anomaly is isolated. TOPOLOGY Agent (0.95) confirms pod 'ts-order-service' is the sole entry in noisy_neighbors on node-worker-01 with no dependencies, meaning it is the SOURCE of contention, not the victim. Zero ts-order-service error logs were present (12 sampled logs are all INFO Success from other services), indicating a silent saturation failure without logged exceptions. MONITORING (0.35) insufficient_data due to single data point is discounted, DEPLOYMENTS (0.35) Degraded status cannot be correlated to a commit due to null Git metadata (sha/commit_msg null), and SECURITY (0.8) rules out breach/RBAC/secret issues.",
  "recommendation": "1. Immediate: kubectl describe pod ts-order-service / kubectl get events --field-selector involvedObject.name=ts-order-service and kubectl top pod/node to confirm CPU throttling/OOMKilled/CrashLoop; restart/evict pod and if needed cordon node-worker-01. 2. Profile application: collect thread dump, CPU flamegraph/pprof and check for infinite loop, deadlock, or hot code path introduced around 2024-01-22 14:51:04 (manual Git history review required as deployment metadata is null). 3. Harden resources: set appropriate requests/limits (CPU/memory) and LimitRange, enable Horizontal Pod Autoscaler and CPU throttling alerts (e.g., container_cpu_cfs_throttled_seconds_total). 4. Isolate noisy neighbor: consider dedicated node pool/taints or pod anti-affinity for ts-order-service and add node-level CPU saturation alerts. 5. Add observability: ensure ts-order-service logs and multi-point CPU rate metrics are collected to avoid single-sample blind spots.",
  "severity": "HIGH",
  "confidence": 0.91,
  "evidence": [
    "TOPOLOGY (0.95): Pod 'ts-order-service' is sole noisy_neighbor on node-worker-01 with no dependencies -> source of resource contention, not victim",
    "LOGS (0.89): Isolated CPU-bound saturation post-1705935125: cpu 5.289->37.52 (+609%), p50 0.01019->0.03552 (3.48x), p90 0.03546->0.08698 (2.45x), diskio -95.7% while 8 other services p50/p90 decreased 4-13x",
    "LOGS (0.89): Zero ts-order-service log lines, 12 INFO Success logs from other services -> failure without exception, consistent with resource exhaustion",
    "MONITORING (0.35): Single data point (37.52) insufficient_data - discounted due to low confidence vs high-confidence correlated metrics",
    "DEPLOYMENTS (0.35): ts-order-service-deploy Degraded but sha:null/commit_msg:null -> cannot attribute to deployment regression, requires manual Git investigation",
    "SECURITY (0.8): No breaches, secret warnings, or RBAC alerts -> security ruled out as cause"
  ]
}
```

**🔗 CONNECTION → STEP 5** — `title`, `summary` and `cause` are passed to the claim extractor.

---

## ✂️ STEP 5 — Atomic Claim Extraction (API / LLM Call)

**⚙️ EXECUTION** — `GraphProvenanceClaimScorer.extract_claims()` in [`services/api/app/research/gpcs.py:L266`](../../services/api/app/research/gpcs.py#L266) takes the Consensus Engine's synthesis output from Step 4.

### 📥 INPUT PREPARATION

The `title`, `summary`, and `cause` fields from the consensus JSON response are concatenated into a single string `raw_text`:
> 💡 **Note:** `recommendation` is deliberately excluded from extraction because recommendations are prescriptive suggestions rather than evaluable factual assertions.

```python
raw_text = " ".join(
    str(analysis.get(key, ""))
    for key in ("title", "summary", "cause")
    if analysis.get(key)
)
```

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
CPU Saturation Noisy Neighbor Failure on ts-order-service Pod 'ts-order-service' on node 'node-worker-01' has Failed due to isolated CPU-bound resource saturation. Impact is isolated to ts-order-service with no cascading failures to 8 other co-located services, which show 4-13x latency improvement in the same window. Correlated high-confidence signals indicate a performance/resource exhaustion failure, not a code deployment or security event. LOGS Agent (0.89) shows a clear isolated degradation post-1705935125: CPU mean 5.289 -> 37.52 (+609%), latency p50 0.01019 -> 0.03552 (3.48x), p90 0.03546 -> 0.08698 (2.45x), and disk IO 1.216e+06 -> 5.201e+04 (-95.7%) consistent with CPU starvation/busy-loop where the service is burning CPU and not performing IO. In contrast, 8 other services' p50/p90 latencies all decreased 4-13x (e.g., ts-user-service p90 0.3185 -> 0.02313), proving the anomaly is isolated. TOPOLOGY Agent (0.95) confirms pod 'ts-order-service' is the sole entry in noisy_neighbors on node-worker-01 with no dependencies, meaning it is the SOURCE of contention, not the victim. Zero ts-order-service error logs were present (12 sampled logs are all INFO Success from other services), indicating a silent saturation failure without logged exceptions. MONITORING (0.35) insufficient_data due to single data point is discounted, DEPLOYMENTS (0.35) Degraded status cannot be correlated to a commit due to null Git metadata (sha/commit_msg null), and SECURITY (0.8) rules out breach/RBAC/secret issues.

Example output:
[{"claim_id": "claim-1", "text": "...", "claim_type": "state"}]
```

**📤 LLM JSON RESPONSE RETURNED (38 Extracted Atomic Claims):**

```json
[
  {
    "claim_id": "claim-1",
    "text": "Pod 'ts-order-service' is located on node 'node-worker-01'.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-2",
    "text": "Pod 'ts-order-service' has Failed state.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-3",
    "text": "Pod 'ts-order-service' failed due to isolated CPU-bound resource saturation.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-4",
    "text": "Failure is classified as CPU Saturation Noisy Neighbor Failure.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-5",
    "text": "Impact is isolated to ts-order-service.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-6",
    "text": "There were no cascading failures to 8 other co-located services.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-7",
    "text": "8 other co-located services show 4-13x latency improvement in the same window.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-8",
    "text": "Failure is a performance/resource exhaustion failure.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-9",
    "text": "Failure is not a code deployment event.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-10",
    "text": "Failure is not a security event.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-11",
    "text": "LOGS Agent reported with confidence 0.89.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-12",
    "text": "Isolated degradation occurred post-1705935125.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-13",
    "text": "CPU mean increased from 5.289 to 37.52 (+609%).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-14",
    "text": "Latency p50 increased from 0.01019 to 0.03552 (3.48x).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-15",
    "text": "Latency p90 increased from 0.03546 to 0.08698 (2.45x).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-16",
    "text": "Disk IO decreased from 1.216e+06 to 5.201e+04 (-95.7%).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-17",
    "text": "Disk IO decrease is consistent with CPU starvation/busy-loop.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-18",
    "text": "Service was burning CPU and not performing IO.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-19",
    "text": "8 other services' p50/p90 latencies all decreased 4-13x.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-20",
    "text": "ts-user-service p90 decreased from 0.3185 to 0.02313.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-21",
    "text": "Anomaly is isolated to ts-order-service.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-22",
    "text": "TOPOLOGY Agent reported with confidence 0.95.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-23",
    "text": "Pod 'ts-order-service' is the sole entry in noisy_neighbors on node-worker-01.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-24",
    "text": "Pod 'ts-order-service' has no dependencies.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-25",
    "text": "Pod 'ts-order-service' is the SOURCE of contention, not the victim.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-26",
    "text": "Zero ts-order-service error logs were present.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-27",
    "text": "12 sampled logs are all INFO Success from other services.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-28",
    "text": "Failure was a silent saturation failure without logged exceptions.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-29",
    "text": "MONITORING Agent reported insufficient_data with confidence 0.35 due to single data point.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-30",
    "text": "MONITORING insufficient_data signal is discounted.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-31",
    "text": "DEPLOYMENTS Agent reported Degraded status with confidence 0.35.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-32",
    "text": "DEPLOYMENTS Degraded status cannot be correlated to a commit due to null Git metadata.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-33",
    "text": "Git metadata sha is null.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-34",
    "text": "Git metadata commit_msg is null.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-35",
    "text": "SECURITY Agent with confidence 0.8 rules out breach/RBAC/secret issues.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-36",
    "text": "SECURITY rules out breach.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-37",
    "text": "SECURITY rules out RBAC issues.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-38",
    "text": "SECURITY rules out secret issues.",
    "claim_type": "state"
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

> 🔗 **Downstream Connection:** This exact list of **38 atomic claims** is passed forward to both **GPCS (Step 6)** for graph-provenance verification and **Ground-Truth Correctness Labelling (Step 8)** for deterministic evaluation against held-out ground truth.

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
- **$\text{proximity} = \frac{1}{1 + \text{min\_hop}(c_i, e)}$** (Graph hop distance from target pod `ts-order-service` in Neo4j).
- **$\text{reliability} = \text{SOURCE\_RELIABILITY}(e)$**: Metric = `0.95`, Log = `0.85`, Topology = `0.80`, Commit = `0.70`.
- **$\text{penalty} = 0.15 \times (\text{min\_hop} \times 0.05)$**

### 3. Decision Threshold Rule

$$\text{gpcs\_unsupported}(c_i) = \begin{cases} \text{False (SUPPORTED)} & \text{if } \text{trust\_score}(c_i) \ge 0.50 \\ \text{True (UNSUPPORTED)} & \text{if } \text{trust\_score}(c_i) < 0.50 \end{cases}$$

### 4. Worked Step-by-Step Calculation Example (`rcaeval-03-NONE`)

- **Claim $c_1$:** `"Pod 'ts-order-service' experienced resource pressure"`
- **Retrieved Evidence Node $e_1$:** Metric node `container_cpu_usage_seconds_total` on `ts-order-service`.
  - **Vector Cosine Similarity:** `0.7500`
  - **Graph Hop Distance:** `1 hop` (`ts-order-service` Pod -> Metric Node) $\implies \text{proximity} = \frac{1}{1 + 1} = 0.5000$
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

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-03-NONE`):**

```text
claims scored    : 38
GPCS unsupported : 29/38 = 76.3% (9 supported)
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

### 4. Worked Step-by-Step Calculation Example (`rcaeval-03-NONE`)
- **Primary Claim $c_1$:** `"ts-order-service experienced resource exhaustion"`
- **Generation $G_2$ Claims:** Contains $c_{2,4}$ `"ts-order-service resource utilization spiked"` $\implies \text{cosine\_sim} = 0.94 \ge 0.80$ (**Match 1**).
- **Generation $G_3$ Claims:** Contains $c_{3,2}$ `"resource pressure observed on ts-order-service"` $\implies \text{cosine\_sim} = 0.88 \ge 0.80$ (**Match 2**).

$$\text{recurrence}(c_1) = \frac{1 + 1}{2} = \mathbf{1.00}$$
- **Verdict:** `1.00 >= 0.50` $\implies$ **`SUPPORTED`** (`sc_unsupported = False`).

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-03-NONE`):**

```text
claims scored               : 38
Self-Consistency unsupported: 27/38 = 71.1% (11 supported)
```

---

## 📊 STEP 8 — Ground-Truth Correctness Labelling

### 1. Concept & Objective
Determines whether an extracted atomic claim $c_i$ is objectively **`CONSISTENT`** (True), **`CONTRADICTED`** (False), or **`UNVERIFIABLE`** (N/A) against held-out benchmark ground truth (`target_service = ts-order-service`, `fault = cpu_exhaustion`).

> ⚠️ **CRITICAL RULE:** **NO LLM CALLS & NO VERIFIER DEPENDENCY.** This step is 100% deterministic Python string and regex matching against held-out ground truth in `services/api/scripts/label_claim_correctness.py`. It operates completely independently of GPCS (Step 6) and Self-Consistency (Step 7).

---

### 🔒 Role of Held-Out Ground-Truth Claims

Each benchmark scenario contains 2 reference ground-truth claims (e.g., `"ts-order-service was affected by CPU resource exhaustion"`).

In this experiment, these reference claims are strictly **held out** (withheld from all prompts and databases):

- **Zero Data Leakage:** Never passed to LLM prompts, Neo4j, or Qdrant.
- **Metadata-Driven Labeling:** Python labeling uses top-level scenario metadata (`target_service = ts-order-service`, `root_cause = cpu`) directly, rather than reading the reference text.
- **Contamination Guardrail:** Serves as a reference check to verify that generated claims do not copy held-out benchmark text verbatim.

---

### 2. Python Deterministic Logic (`label_claim()`)

The core labelling logic is implemented in `services/api/scripts/label_claim_correctness.py`:

```python
def label_claim(
    claim_text: str,
    claim_type: str,
    scenario: dict[str, Any],
    services: set[str],
) -> tuple[str, str]:
    """Return (label, reason) for one claim.
    label is one of: consistent | contradicted | unverifiable.
    """
    if claim_type != "causal" and not CAUSAL_MARKERS.search(claim_text):
        return "unverifiable", "not a causal claim"

    fault = _fault_of(scenario)              # e.g., "cpu"
    target = scenario["target_service"]       # e.g., "ts-order-service"

    def mentioned_affirmatively(patterns: list[str]) -> bool:
        """True when a pattern matches outside a negation scope."""
        if NEGATION_NEAR.search(claim_text):
            return False
        scoped = NEGATED_PREFIX.sub(" ", claim_text)
        return any(re.search(pattern, scoped, re.I) for pattern in patterns)

    names_correct_mechanism = mentioned_affirmatively(MECHANISM_PATTERNS.get(fault, []))
    competing = [
        other for other, patterns in MECHANISM_PATTERNS.items()
        if other != fault and mentioned_affirmatively(patterns)
    ]
    blamed_foreign = [
        s for s in sorted(services)
        if s != target and re.search(FOREIGN_AS_CAUSE.format(service=re.escape(s)), claim_text, re.I)
    ]

    # Priority Decision Hierarchy:
    if names_correct_mechanism:
        return "consistent", f"names the injected mechanism ({fault})"
    if blamed_foreign:
        return "contradicted", f"blames {blamed_foreign[0]}, injected fault was on {target}"
    if competing:
        return "contradicted", f"names {competing[0]} as cause, injected fault was {fault}"

    return "unverifiable", "no mechanism or service identifiable"
```

---

### 3. Step-by-Step Code Tracing of 3 Claim Examples

To understand how the Python algorithm labels claims, we trace 3 distinct claim types under scenario `rcaeval-03` (`target_service = ts-order-service`, `fault = cpu`, `services = {ts-order-service, ts-user-service, ts-route-service}`):

#### 🟢 **Example 1: `CONSISTENT` Claim Trace**
- **Claim Text:** `"High CPU exhaustion caused ts-order-service to experience performance degradation."`
- **Claim Type:** `"causal"`
- **Trace:**
  1. `claim_type == "causal"` $\implies$ passes initial non-causal filter.
  2. `fault` extracted as `"cpu"`, `target` extracted as `"ts-order-service"`.
  3. `names_correct_mechanism` checks `MECHANISM_PATTERNS["cpu"]`, matching `r"cpu (?:saturation|exhaustion|...)"`. `NEGATION_NEAR` finds no negation terms $\implies$ returns `True`.
  4. Line 228 check `if names_correct_mechanism:` evaluates to `True`.
- **Output Label:** `("consistent", "names the injected mechanism (cpu)")`

#### 🔴 **Example 2: `CONTRADICTED` Claim Trace**
- **Claim Text:** `"The service failure was caused by memory exhaustion on ts-order-service."`
- **Claim Type:** `"causal"`
- **Trace:**
  1. `CAUSAL_MARKERS` matches `"caused by"`. Passes initial check.
  2. `fault` = `"cpu"`, `target` = `"ts-order-service"`.
  3. `names_correct_mechanism` checks `cpu` patterns $\implies$ No match (`False`).
  4. `blamed_foreign` checks foreign service names (`ts-user-service`, etc.) $\implies$ `[]`.
  5. `competing` checks other fault patterns (`mem`, `disk`, `delay`, `loss`, `socket`). `MECHANISM_PATTERNS["mem"]` matches `"memory exhaustion"` $\implies$ `competing = ["mem"]`.
  6. Line 237 check `if competing:` evaluates to `True`.
- **Output Label:** `("contradicted", "names mem as cause, injected fault was cpu")`

#### 🟡 **Example 3: `UNVERIFIABLE` Claim Trace**
- **Claim Text:** `"ts-order-service observed an increase in HTTP 500 response rates."`
- **Claim Type:** `"descriptive"`
- **Trace:**
  1. `claim_type != "causal"` and `CAUSAL_MARKERS.search()` finds no causal markers (e.g. *"caused by"*, *"led to"*).
  2. Line 197 check `if claim_type != "causal" and not CAUSAL_MARKERS.search(claim_text):` evaluates to `True`.
- **Output Label:** `("unverifiable", "not a causal claim")`

---

### 📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-03-NONE`)

```text
consistent=2   contradicted=0   unverifiable=36
EVALUABLE SUBSET: 2 of 38 claims (5.3%)
```

---

## 📈 STEP 9 — Head-to-Head Precision, Recall, & Contingency Evaluation (`rcaeval-03`)

### 1. Concept & Objective
Pairs the verifiers' unsupported flags (`UNSUPPORTED` = Positive Class) with the ground-truth correctness labels (`CONTRADICTED` = Positive Class) to build a 2×2 contingency matrix and evaluate verifier accuracy for scenario **`rcaeval-03`**.

### 🔗 How Ground-Truth Labels (`CONSISTENT` / `CONTRADICTED`) Feed Into Step 9
The evaluable claims labeled in Step 8 form the **ground-truth baseline columns** (`CONTRADICTED` vs `CONSISTENT`) in the 2×2 contingency matrix:
- **Positive Class (Target to Catch):** `CONTRADICTED` (Factually wrong claims).
- **Negative Class (Acceptable Claims):** `CONSISTENT` (Factually accurate claims).
- **Verifier Flags (Positive Class):** `UNSUPPORTED` (Verifier marks claim as invalid/hallucinated).

This pairing enables computing true Precision, Recall, Specificity, and F1 Score for both GPCS and Self-Consistency, measuring whether a verifier's `UNSUPPORTED` flag actually discriminates wrong claims from right ones.

### 2. 2×2 Contingency Matrix for Scenario `rcaeval-03` (NONE)

```text
                          DERIVED GROUND TRUTH (SCENARIO RCAEVAL-03)
                     CONTRADICTED (Wrong)    CONSISTENT (Right)
flagged UNSUPPORTED     True Positive (0)    False Positive (29)
flagged SUPPORTED       False Negative (0)    True Negative (9)
```

### 3. Mathematical Evaluation Formulas

$$\begin{aligned}
\text{Precision} &= \frac{\text{TP}}{\text{TP} + \text{FP}} \\
\text{Recall} &= \frac{\text{TP}}{\text{TP} + \text{FN}} \\
\text{F1 Score} &= \frac{2 \cdot \text{Precision} \cdot \text{Recall}}{\text{Precision} + \text{Recall}} \\
\text{Specificity} &= \frac{\text{TN}}{\text{TN} + \text{FP}} \\
\text{Flag Rate Gap} &= \text{Flag Rate}(\text{CONTRADICTED}) - \text{Flag Rate}(\text{CONSISTENT})
\end{aligned}$$

### 4. Scenario `rcaeval-03` Measured Verifier Performance

| Verifier | Total Claims | Unsupported Claims | Supported Claims | Unsupported % | Ground-Truth Causal | Ground-Truth Outcome |
|---|---|---|---|---|---|---|
| **GPCS** | **38** | **29** | **9** | **76.3%** | 2 (2 consistent, 0 contradicted) | Consistent Cause Identified |
| **Self-Consistency** | **38** | **27** | **11** | **71.1%** | 2 (2 consistent, 0 contradicted) | Consistent Cause Identified |

---

---

## 💡 Scenario `rcaeval-03` — findings, mapped to the Experiment 1 research questions

Measured for **rcaeval-03** (Train Ticket, `cpu_exhaustion`) under condition **`NONE`**.

| | This run |
|---|---|
| Claims extracted | 38 |
| GPCS unsupported | 29/38 = 76.3% |
| Self-consistency unsupported | 27/38 = 71.1% |
| Accepted by **both** verifiers | 6/38 = 15.8% |
| Ground-truth labelled | 2 of 38 (2 consistent, 0 contradicted) |
| Distinct GPCS trust values | 2 — [0.0, 0.708] |

**E1-RQ1 — pipeline executes reliably.** Supported. The run completed with no
fallback, timeout or refused connection, and produced paired GPCS and
self-consistency verdicts for all 38 claims.

**E1-RQ2 / E1-RQ3 — context cost and the seeded red herring.** See the
comparison table at the top of this document. The `Commit` node reaches only
`RAW` (15 prompts) and is discounted there on its timestamp; its absence
from `HYBRID` is a consequence of top-5 ranking, **not** active pruning.

**E1-RQ4 — joint verifier filter.** 6 of 38 claims are accepted by both
verifiers. This is a reproducible candidate set, not an accuracy result: across
the whole experiment only 1 of the 95 intersection claims carries a
ground-truth label.

**E1-RQ5 / E1-RQ6 — correctness is not established here.** This run names the injected mechanism.
Only 2 of 38 claims are adjudicable, so no precision, recall or flag-rate gap can
be computed for a single run.

### On GPCS versus self-consistency

GPCS flags **76.3%** of claims unsupported against self-consistency's
**71.1%** — a difference of **+5.3 percentage points**, at no
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
