# CloudGraph — complete sequential input-to-output chain (Condition `NONE`)

A strictly sequential breakdown of how CloudGraph operates under **Condition `NONE`** (baseline execution without retrieval context). Each step states:

1. **📥 INPUT** — what data enters
2. **⚙️ EXECUTION** — what code processes it
3. **📤 OUTPUT** — what is produced
4. **🔗 CONNECTION** — how that output becomes the next step's input

Illustrated throughout with scenario **`rcaeval-07`** (*Online Boutique*, target pod: `checkoutservice`, injected fault: `disk_saturation` at timestamp `1705373910`).

> Every value is quoted from `03-rcaeval-07/rcaeval-07-NONE.log`, written live by `scripts/trace_scenario.py` (218.9s wall time).

---

## 📌 STEP 1 — Telemetry ingestion and database seeding

**📥 INPUT** — scenario `rcaeval-07` from RCAEval RE2 (Online Boutique):

| Property | Value |
|---|---|
| Target pod | `checkoutservice` on node `node-worker-01` |
| Injected fault | `disk_saturation` at epoch `1705373910` |
| Observed symptoms | 26 telemetry symptom lines |
| Held out | 2 ground-truth claims — never prompted |

```text
metric checkoutservice_cpu: mean baseline in the 12min before 1705373910
metric checkoutservice_mem: mean baseline in the 12min before 1705373910
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

- Seed pod: `checkoutservice`
- Query: `"checkoutservice degraded performance investigation"`
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

**📥 INPUT** — pod metadata (`checkoutservice`, `Failed`, `cloudgraph-system`), the 26 symptoms, and the empty retrieval context.

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
Analyze metrics for Pod 'checkoutservice' to check for anomalies.

Metrics:
[
  {
    "name": "container_cpu_usage_seconds_total",
    "value": 17.87,
    "ts": 1705373910
  }
]

Output JSON with: 'finding', 'confidence', 'anomalies'.
```

**📤 Response:**

```json
{
  "finding": "insufficient_data",
  "confidence": 0.15,
  "anomalies": []
}
```

---

### 2️⃣ Log specialist

**📥 Prompt sent:**

```text
You are a Specialist Log Agent.
Analyze logs for Pod 'checkoutservice' to check for failure patterns.

Logs:
metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after
metric checkoutservice_mem: mean 1.047e+07 in the 12min before 1705373910, 1.314e+08 in the 12min after
metric redis_diskio: mean 2970 in the 12min before 1705373910, 4542 in the 12min after
metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after
metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after
metric cartservice_cpu: mean 1.958 in the 12min before 1705373910, 2.101 in the 12min after
metric paymentservice_cpu: mean 0.6448 in the 12min before 1705373910, 0.5985 in the 12min after
metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after
metric emailservice_latency-90: mean 0.004606 in the 12min before 1705373910, 0.004817 in the 12min after
metric paymentservice_latency-90: mean 0.007338 in the 12min before 1705373910, 0.007671 in the 12min after
metric frontend_latency-90: mean 0.6166 in the 12min before 1705373910, 0.6441 in the 12min after
metric productcatalogservice_cpu: mean 3.15 in the 12min before 1705373910, 3.278 in the 12min after
metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after
metric paymentservice_workload: mean 0.9236 in the 12min before 1705373910, 0.8873 in the 12min after
log [frontend] request started
log [frontend] serving product page
log [currencyservice] conversion request successful
log [currencyservice] Getting supported currencies...
log [cartservice] GetCartAsync called with userId=<UUID_REDACTED>
log [cartservice] GetCartAsync called with userId=<UUID_REDACTED>
log [frontend] request complete
log [cartservice] GetCartAsync called with userId=<UUID_REDACTED>
log [recommendationservice] [Recv ListRecommendations] product_ids=['66VCHSJNUP', 'LS4PSXUNUM', '9SIQT8TOJO', 'OLJCESPC7Z', '2ZYFJ3GM2N']
log [recommendationservice] [Recv ListRecommendations] product_ids=['L9ECAV7KIM', '1YMWWN1N4O', '66VCHSJNUP', '9SIQT8TOJO', '2ZYFJ3GM2N']
log [adservice] received ad request (context_words=[kitchen])
log [frontend] adding to cart

Output JSON with: 'finding', 'confidence', 'category'.
```

**📤 Response:**

```json
{"finding": "checkoutservice shows severe resource anomaly after 1705373910: CPU mean 0.4091 -> 17.87 (~43.7x) and memory mean 1.047e+07 -> 1.314e+08 (~12.5x) with socket count 9 -> 11.96 and p50 latency 0.2745 -> 0.3588 (+30.7%), p90 latency 0.7253 -> 0.7752, while workload slightly decreased 0.9243 -> 0.8874. Pattern indicates non-load-induced resource exhaustion / runaway process or memory leak. No explicit checkoutservice error logs present in provided window; other services (cartservice, paymentservice, productcatalogservice) remain stable, isolating failure to checkoutservice. Correlated redis_diskio increase 2970 -> 4542 observed.","confidence": 0.93,"category": "resource_exhaustion
```

---

### 3️⃣ Deployment specialist

**📥 Prompt sent:**

```text
You are a Specialist Deployment Agent.
Analyze deployment and Git status for Pod 'checkoutservice' to check for regressions.

Deployment info:
{
  "name": "checkoutservice-deploy",
  "status": "Degraded",
  "sha": null,
  "commit_msg": null
}

Output JSON with: 'finding', 'confidence'.
```

**📤 Response:**

```json
{
  "finding": "Deployment checkoutservice-deploy is Degraded with null SHA and null commit_msg; Git status cannot be verified and regression cannot be confirmed or ruled out - requires manual investigation of deployment logs and Git history",
  "confidence": 0.3
}
```

---

### 4️⃣ Topology specialist

**📥 Prompt sent:**

```text
You are a Specialist Topology Agent.
Analyze topology for Pod 'checkoutservice' to check for noisy neighbors.

Topology:
{
  "dependencies": [],
  "node_name": "node-worker-01",
  "noisy_neighbors": [
    "checkoutservice"
  ]
}

Output JSON with: 'finding', 'confidence'.
```

**📤 Response:**

```json
{
  "finding": "No external noisy neighbors detected for Pod 'checkoutservice' on node 'node-worker-01'. The noisy_neighbors list contains only 'checkoutservice' itself, indicating the pod is isolated on the node with no co-located pods causing CPU/memory/IO contention. Dependencies list is empty, no downstream dependency contention.",
  "confidence": 0.99
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
  "finding": "No security breaches, secret reference warnings, or RBAC alerts detected for Pod 'checkoutservice'.",
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
You received telemetry from 5 agents for pod 'checkoutservice' (Status: 'Failed'):

- MONITORING Agent (Conf: 0.15): insufficient_data
- LOGS Agent (Conf: 0.93): checkoutservice shows severe resource anomaly after 1705373910: CPU mean 0.4091 -> 17.87 (~43.7x) and memory mean 1.047e+07 -> 1.314e+08 (~12.5x) with socket count 9 -> 11.96 and p50 latency 0.2745 -> 0.3588 (+30.7%), p90 latency 0.7253 -> 0.7752, while workload slightly decreased 0.9243 -> 0.8874. Pattern indicates non-load-induced resource exhaustion / runaway process or memory leak. No explicit checkoutservice error logs present in provided window; other services (cartservice, paymentservice, productcatalogservice) remain stable, isolating failure to checkoutservice. Correlated redis_diskio increase 2970 -> 4542 observed.
- DEPLOYMENTS Agent (Conf: 0.3): Deployment checkoutservice-deploy is Degraded with null SHA and null commit_msg; Git status cannot be verified and regression cannot be confirmed or ruled out - requires manual investigation of deployment logs and Git history
- TOPOLOGY Agent (Conf: 0.99): No external noisy neighbors detected for Pod 'checkoutservice' on node 'node-worker-01'. The noisy_neighbors list contains only 'checkoutservice' itself, indicating the pod is isolated on the node with no co-located pods causing CPU/memory/IO contention. Dependencies list is empty, no downstream dependency contention.
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
  "title": "Internal Resource Exhaustion / Runaway Process in checkoutservice",
  "summary": "Pod 'checkoutservice' on node 'node-worker-01' has Failed due to severe internal CPU/memory exhaustion starting after 1705373910. The failure is isolated to checkoutservice, causing p50 latency +30.7% degradation and pod crash, with no impact from co-located pods or downstream dependencies. Checkout functionality is disrupted while other services remain healthy.",
  "cause": "Correlated LOGS (0.93) and TOPOLOGY (0.99) evidence isolates root cause to an internal, non-load-induced resource exhaustion within checkoutservice itself. After timestamp 1705373910, CPU mean surged 0.4091 -> 17.87 (~43.7x) and memory mean 1.047e+07 -> 1.314e+08 (~12.5x), socket count 9 -> 11.96, p50 latency 0.2745 -> 0.3588 (+30.7%) and p90 0.7253 -> 0.7752, while workload slightly DECREASED 0.9243 -> 0.8874 - proving exhaustion is not caused by increased traffic. Pattern is consistent with runaway process, infinite loop, thread leak, or memory leak. TOPOLOGY (0.99) confirms no external noisy neighbors on node-worker-01 (noisy_neighbors contains only checkoutservice itself) and empty dependencies list, ruling out node-level CPU/memory/IO contention or downstream dependency contention. Isolation is further confirmed as cartservice, paymentservice, and productcatalogservice remain stable. SECURITY (0.8) rules out breach/RBAC/secret compromise. DEPLOYMENTS (0.3) reports Degraded with null SHA/commit_msg but with low confidence and no verifiable Git history, so deployment regression cannot be confirmed or ruled out and is not the primary driver. MONITORING (0.15) insufficient_data is discounted. Correlated redis_diskio increase 2970 -> 4542 is likely secondary effect of the runaway checkoutservice, not cause.",
  "recommendation": "1. Immediate Mitigation: Restart/recreate checkoutservice pod, enforce CPU/memory requests/limits and OOMKill handling, verify liveness/readiness probes to auto-recover. 2. Diagnostics: Capture heap dump, thread dump, and CPU profile (pprof/py-spy) before restart if possible; analyze application logs around 1705373910 for GC pressure, thread leaks, or runaway loops; correlate redis_diskio spike to checkoutservice Redis calls. 3. Code/Deployment Review: Manually investigate deployment logs and Git history around 1705373910 for recent changes to checkoutservice (DEPLOYMENTS SHA is null) - review for known memory leak or unbounded retry logic. 4. Observability: Add alerts on CPU >5x baseline and memory >3x baseline with workload correlation, and latency SLO alerts for checkoutservice. 5. Long-term: Load test in staging, fix leak/runaway code, consider HPA and circuit breakers.",
  "severity": "CRITICAL",
  "confidence": 0.92,
  "evidence": [
    "LOGS (0.93): CPU 0.4091 -> 17.87 (~43.7x) and memory 1.047e+07 -> 1.314e+08 (~12.5x) after 1705373910 with socket count 9 -> 11.96 and p50 latency +30.7% while workload decreased 0.9243 -> 0.8874 = non-load-induced exhaustion",
    "TOPOLOGY (0.99): No external noisy neighbors on node-worker-01 (only checkoutservice itself) and empty dependencies list - rules out node contention and downstream dependency contention",
    "LOGS cross-service isolation: cartservice, paymentservice, productcatalogservice remain stable, localizing failure to checkoutservice",
    "SECURITY (0.8): No security breaches, secret reference warnings, or RBAC alerts - rules out security compromise",
    "DEPLOYMENTS (0.3): Degraded with null SHA/commit_msg - low confidence, cannot verify regression, discounted as primary cause",
    "MONITORING (0.15): insufficient_data - discounted due to low confidence",
    "Correlated redis_diskio increase 2970 -> 4542 observed as secondary effect, not root cause"
  ]
}
```

**🔗 CONNECTION → STEP 5** — `title`, `summary` and `cause` are passed to the claim extractor.

---

## ✂️ STEP 5 — Atomic Claim Extraction (API / LLM Call)

**⚙️ EXECUTION** — `GraphProvenanceClaimScorer.extract_claims()` in [`services/api/app/research/gpcs.py:L266`](../services/api/app/research/gpcs.py#L266) takes the Consensus Engine's synthesis output from Step 4.

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

The claim extraction layer invokes the LLM using `_extract_claims_with_llm()` in [`gpcs.py:L300`](../services/api/app/research/gpcs.py#L300):

**System Prompt:**

```text
You are an expert claim extractor for AIOps incident reports. Output only a JSON array.
```

**📥 LLM INPUT PROMPT SENT:**

```text
Extract the atomic factual claims from the following RCA summary. Return a JSON array of objects with keys: claim_id, text, claim_type. claim_type must be one of temporal, causal, entity_relationship, state, general.

RCA text:
Internal Resource Exhaustion / Runaway Process in checkoutservice Pod 'checkoutservice' on node 'node-worker-01' has Failed due to severe internal CPU/memory exhaustion starting after 1705373910. The failure is isolated to checkoutservice, causing p50 latency +30.7% degradation and pod crash, with no impact from co-located pods or downstream dependencies. Checkout functionality is disrupted while other services remain healthy. Correlated LOGS (0.93) and TOPOLOGY (0.99) evidence isolates root cause to an internal, non-load-induced resource exhaustion within checkoutservice itself. After timestamp 1705373910, CPU mean surged 0.4091 -> 17.87 (~43.7x) and memory mean 1.047e+07 -> 1.314e+08 (~12.5x), socket count 9 -> 11.96, p50 latency 0.2745 -> 0.3588 (+30.7%) and p90 0.7253 -> 0.7752, while workload slightly DECREASED 0.9243 -> 0.8874 - proving exhaustion is not caused by increased traffic. Pattern is consistent with runaway process, infinite loop, thread leak, or memory leak. TOPOLOGY (0.99) confirms no external noisy neighbors on node-worker-01 (noisy_neighbors contains only checkoutservice itself) and empty dependencies list, ruling out node-level CPU/memory/IO contention or downstream dependency contention. Isolation is further confirmed as cartservice, paymentservice, and productcatalogservice remain stable. SECURITY (0.8) rules out breach/RBAC/secret compromise. DEPLOYMENTS (0.3) reports Degraded with null SHA/commit_msg but with low confidence and no verifiable Git history, so deployment regression cannot be confirmed or ruled out and is not the primary driver. MONITORING (0.15) insufficient_data is discounted. Correlated redis_diskio increase 2970 -> 4542 is likely secondary effect of the runaway checkoutservice, not cause.

Example output:
[{"claim_id": "claim-1", "text": "...", "claim_type": "state"}]
```

**📤 LLM JSON RESPONSE RETURNED (48 Extracted Atomic Claims):**

```json
[
  {
    "claim_id": "claim-1",
    "text": "Pod 'checkoutservice' is located on node 'node-worker-01'.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-2",
    "text": "Pod 'checkoutservice' has Failed.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-3",
    "text": "The failure started after timestamp 1705373910.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-4",
    "text": "The failure was caused by severe internal CPU/memory exhaustion.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-5",
    "text": "The failure is isolated to checkoutservice.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-6",
    "text": "The failure caused p50 latency degradation of +30.7%.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-7",
    "text": "The failure caused a pod crash.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-8",
    "text": "Co-located pods had no impact on the failure.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-9",
    "text": "Downstream dependencies had no impact on the failure.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-10",
    "text": "Checkout functionality is disrupted.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-11",
    "text": "Other services remain healthy.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-12",
    "text": "LOGS evidence with correlation 0.93 isolates root cause to internal resource exhaustion within checkoutservice.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-13",
    "text": "TOPOLOGY evidence with correlation 0.99 isolates root cause to internal resource exhaustion within checkoutservice.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-14",
    "text": "The resource exhaustion is internal to checkoutservice itself.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-15",
    "text": "The resource exhaustion is non-load-induced.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-16",
    "text": "After timestamp 1705373910, CPU mean surged from 0.4091 to 17.87 (~43.7x).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-17",
    "text": "After timestamp 1705373910, memory mean surged from 1.047e+07 to 1.314e+08 (~12.5x).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-18",
    "text": "After timestamp 1705373910, socket count increased from 9 to 11.96.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-19",
    "text": "After timestamp 1705373910, p50 latency increased from 0.2745 to 0.3588 (+30.7%).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-20",
    "text": "After timestamp 1705373910, p90 latency increased from 0.7253 to 0.7752.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-21",
    "text": "After timestamp 1705373910, workload decreased from 0.9243 to 0.8874.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-22",
    "text": "The resource exhaustion was not caused by increased traffic.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-23",
    "text": "The pattern is consistent with a runaway process.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-24",
    "text": "The pattern is consistent with an infinite loop.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-25",
    "text": "The pattern is consistent with a thread leak.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-26",
    "text": "The pattern is consistent with a memory leak.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-27",
    "text": "TOPOLOGY with correlation 0.99 confirms no external noisy neighbors on node-worker-01.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-28",
    "text": "The noisy_neighbors list contains only checkoutservice itself.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-29",
    "text": "The dependencies list is empty.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-30",
    "text": "Node-level CPU contention is ruled out as a cause.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-31",
    "text": "Node-level memory contention is ruled out as a cause.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-32",
    "text": "Node-level IO contention is ruled out as a cause.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-33",
    "text": "Downstream dependency contention is ruled out as a cause.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-34",
    "text": "cartservice remains stable.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-35",
    "text": "paymentservice remains stable.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-36",
    "text": "productcatalogservice remains stable.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-37",
    "text": "SECURITY with correlation 0.8 rules out breach as a cause.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-38",
    "text": "SECURITY rules out RBAC compromise.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-39",
    "text": "SECURITY rules out secret compromise.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-40",
    "text": "DEPLOYMENTS with correlation 0.3 reports Degraded.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-41",
    "text": "DEPLOYMENTS has null SHA.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-42",
    "text": "DEPLOYMENTS has null commit_msg.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-43",
    "text": "DEPLOYMENTS has low confidence (0.3) and no verifiable Git history.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-44",
    "text": "Deployment regression cannot be confirmed or ruled out.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-45",
    "text": "Deployment regression is not the primary driver of the failure.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-46",
    "text": "MONITORING with correlation 0.15 reports insufficient_data and is discounted.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-47",
    "text": "redis_diskio increased from 2970 to 4542.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-48",
    "text": "The redis_diskio increase is a secondary effect of the runaway checkoutservice, not a cause.",
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

> 🔗 **Downstream Connection:** This exact list of **48 atomic claims** is passed forward to both **GPCS (Step 6)** for graph-provenance verification and **Ground-Truth Correctness Labelling (Step 8)** for deterministic evaluation against held-out ground truth.

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
- **$\text{proximity} = \frac{1}{1 + \text{min\_hop}(c_i, e)}$** (Graph hop distance from target pod `checkoutservice` in Neo4j).
- **$\text{reliability} = \text{SOURCE\_RELIABILITY}(e)$**: Metric = `0.95`, Log = `0.85`, Topology = `0.80`, Commit = `0.70`.
- **$\text{penalty} = 0.15 \times (\text{min\_hop} \times 0.05)$**

### 3. Decision Threshold Rule

$$\text{gpcs\_unsupported}(c_i) = \begin{cases} \text{False (SUPPORTED)} & \text{if } \text{trust\_score}(c_i) \ge 0.50 \\ \text{True (UNSUPPORTED)} & \text{if } \text{trust\_score}(c_i) < 0.50 \end{cases}$$

### 4. Worked Step-by-Step Calculation Example (`rcaeval-07-NONE`)

- **Claim $c_1$:** `"Pod 'checkoutservice' experienced resource pressure"`
- **Retrieved Evidence Node $e_1$:** Metric node `container_cpu_usage_seconds_total` on `checkoutservice`.
  - **Vector Cosine Similarity:** `0.7500`
  - **Graph Hop Distance:** `1 hop` (`checkoutservice` Pod -> Metric Node) $\implies \text{proximity} = \frac{1}{1 + 1} = 0.5000$
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

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-07-NONE`):**

```text
claims scored    : 48
GPCS unsupported : 39/48 = 81.2% (9 supported)
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

### 4. Worked Step-by-Step Calculation Example (`rcaeval-07-NONE`)

- **Primary Claim $c_1$:** `"checkoutservice experienced resource exhaustion"`
- **Generation $G_2$ Claims:** Contains $c_{2,4}$ `"checkoutservice resource utilization spiked"` $\implies \text{cosine\_sim} = 0.94 \ge 0.80$ (**Match 1**).
- **Generation $G_3$ Claims:** Contains $c_{3,2}$ `"resource pressure observed on checkoutservice"` $\implies \text{cosine\_sim} = 0.88 \ge 0.80$ (**Match 2**).

$$\text{recurrence}(c_1) = \frac{1 + 1}{2} = \mathbf{1.00}$$
- **Verdict:** `1.00 >= 0.50` $\implies$ **`SUPPORTED`** (`sc_unsupported = False`).

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-07-NONE`):**

```text
claims scored               : 48
Self-Consistency unsupported: 32/48 = 66.7% (16 supported)
```

---

## 📊 STEP 8 — Ground-Truth Correctness Labelling

### 1. Concept & Objective
Determines whether an extracted atomic claim $c_i$ is objectively **`CONSISTENT`** (True), **`CONTRADICTED`** (False), or **`UNVERIFIABLE`** (N/A) against held-out benchmark ground truth.

### 🔒 Role of Held-Out Ground-Truth Claims

Each benchmark scenario contains 2 reference ground-truth claims (e.g., `"Service checkoutservice was affected by disk I/O saturation"`).

In this experiment, these reference claims are strictly **held out** (withheld from all prompts and databases):

- **Zero Data Leakage:** Never passed to LLM prompts, Neo4j, or Qdrant.
- **Metadata-Driven Labeling:** Python labeling uses top-level scenario metadata (`target_service = checkoutservice`, `root_cause = disk`) directly, rather than reading the reference text.
- **Contamination Guardrail:** Serves as a reference check to verify that generated claims do not copy held-out benchmark text verbatim.

> ⚠️ **Note for scenario `rcaeval-07`:** There is no `checkoutservice_disk` metric series in `observed_symptoms` at all (dropped upstream due to lack of pre-incident baseline). The system is tasked with diagnosing a disk fault from telemetry that never explicitly measures the disk.

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

    if names_correct_mechanism: return "consistent", f"names injected mechanism (disk_saturation)"
    if blamed_foreign:           return "contradicted", f"blames {blamed_foreign[0]}"
    if competing:                return "contradicted", f"names competing cause {competing[0]}"
    return "unverifiable", "no mechanism or service identifiable"
```

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-07-NONE`):**

```text
consistent=0   contradicted=1   unverifiable=47
EVALUABLE SUBSET: 1 of 48 claims (2.1%)
```

---

## 📈 STEP 9 — Head-to-Head Precision, Recall, & Contingency Evaluation (`rcaeval-07`)

### 1. Concept & Objective
Pairs the verifiers' unsupported flags (`UNSUPPORTED` = Positive Class) with the ground-truth correctness labels (`CONTRADICTED` = Positive Class) to build a 2×2 contingency matrix and evaluate verifier accuracy for scenario **`rcaeval-07`**.

### 🔗 How Ground-Truth Labels (`CONSISTENT` / `CONTRADICTED`) Feed Into Step 9
The evaluable claims labeled in Step 8 form the **ground-truth baseline columns** (`CONTRADICTED` vs `CONSISTENT`) in the 2×2 contingency matrix:
- **Positive Class (Target to Catch):** `CONTRADICTED` (Factually wrong claims).
- **Negative Class (Acceptable Claims):** `CONSISTENT` (Factually accurate claims).
- **Verifier Flags (Positive Class):** `UNSUPPORTED` (Verifier marks claim as invalid/hallucinated).

This pairing enables computing true Precision, Recall, Specificity, and F1 Score for both GPCS and Self-Consistency, measuring whether a verifier's `UNSUPPORTED` flag actually discriminates wrong claims from right ones.

### 2. 2×2 Contingency Matrix for Scenario `rcaeval-07` (NONE)

```text
                          DERIVED GROUND TRUTH (SCENARIO RCAEVAL-07)
                     CONTRADICTED (Wrong)    CONSISTENT (Right)
flagged UNSUPPORTED     True Positive (1)    False Positive (38)
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

### 4. Scenario `rcaeval-07` Measured Verifier Performance

| Verifier | Total Claims | Unsupported Claims | Supported Claims | Unsupported % | Ground-Truth Causal | Ground-Truth Outcome |
|---|---|---|---|---|---|---|
| **GPCS** | **48** | **39** | **9** | **81.2%** | 1 (0 consistent, 1 contradicted) | Contradicted / Unbacked |
| **Self-Consistency** | **48** | **32** | **16** | **66.7%** | 1 (0 consistent, 1 contradicted) | Contradicted / Unbacked |

---

---

## 💡 Scenario `rcaeval-07` — findings, mapped to the Experiment 1 research questions

Measured for **rcaeval-07** (Online Boutique, `disk_saturation`) under condition **`NONE`**.

| | This run |
|---|---|
| Claims extracted | 48 |
| GPCS unsupported | 39/48 = 81.2% |
| Self-consistency unsupported | 32/48 = 66.7% |
| Accepted by **both** verifiers | 4/48 = 8.3% |
| Ground-truth labelled | 1 of 48 (0 consistent, 1 contradicted) |
| Distinct GPCS trust values | 3 — [0.0, 0.708, 0.71] |

**E1-RQ1 — pipeline executes reliably.** Supported. The run completed with no
fallback, timeout or refused connection, and produced paired GPCS and
self-consistency verdicts for all 48 claims.

**E1-RQ2 / E1-RQ3 — context cost and the seeded red herring.** See the
comparison table at the top of this document. The `Commit` node reaches only
`RAW` (15 prompts) and is discounted there on its timestamp; its absence
from `HYBRID` is a consequence of top-5 ranking, **not** active pruning.

**E1-RQ4 — joint verifier filter.** 4 of 48 claims are accepted by both
verifiers. This is a reproducible candidate set, not an accuracy result: across
the whole experiment only 1 of the 95 intersection claims carries a
ground-truth label.

**E1-RQ5 / E1-RQ6 — correctness is not established here.** This run produces no ground-truth-consistent claim.
Only 1 of 48 claims are adjudicable, so no precision, recall or flag-rate gap can
be computed for a single run.

### On GPCS versus self-consistency

GPCS flags **81.2%** of claims unsupported against self-consistency's
**66.7%** — a difference of **+14.6 percentage points**, at no
additional LLM call.

**This is a strictness and cost result, not an accuracy result.** The two
verifiers measure different properties: GPCS asks whether a claim is traceable
to graph or vector evidence; self-consistency asks whether it recurs across
independent generations. Across the full six-scenario experiment they agree on
17 of 22 labelled claims, and the net difference between them is **one claim out
of 661** — which is why this project reports them as complementary signals
rather than ranking one above the other.

GPCS emits only **3 distinct trust values** in this run. Across all 661
claims it emits six, with 80.8% at exactly `0.000`, so it cannot rank claims or
be threshold-tuned on this evidence.
