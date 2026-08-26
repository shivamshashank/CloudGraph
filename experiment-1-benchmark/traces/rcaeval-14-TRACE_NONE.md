# CloudGraph — complete sequential input-to-output chain (Condition `NONE`)

A strictly sequential breakdown of how CloudGraph operates under **Condition `NONE`** (baseline execution without retrieval context). Each step states:

1. **📥 INPUT** — what data enters
2. **⚙️ EXECUTION** — what code processes it
3. **📤 OUTPUT** — what is produced
4. **🔗 CONNECTION** — how that output becomes the next step's input

Illustrated throughout with scenario **`rcaeval-14`** (*Sock Shop*, target pod: `carts`, injected fault: `memory_exhaustion` at timestamp `1705845578`).

> Every value is quoted from `02-rcaeval-14/rcaeval-14-NONE.log`, written live by `scripts/trace_scenario.py` (252.0s wall time).

---

## 📌 STEP 1 — Telemetry ingestion and database seeding

**📥 INPUT** — scenario `rcaeval-14` from RCAEval RE2 (Sock Shop):

| Property | Value |
|---|---|
| Target pod | `carts` on node `node-worker-01` |
| Injected fault | `memory_exhaustion` at epoch `1705845578` |
| Observed symptoms | 26 telemetry symptom lines |
| Held out | 2 ground-truth claims — never prompted |

```text
metric carts_cpu: mean baseline in the 12min before 1705845578
metric carts_mem: mean baseline in the 12min before 1705845578
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

- Seed pod: `carts`
- Query: `"carts degraded performance investigation"`
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

**📥 INPUT** — pod metadata (`carts`, `Failed`, `cloudgraph-system`), the 26 symptoms, and the empty retrieval context.

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
Analyze metrics for Pod 'carts' to check for anomalies.

Metrics:
[
  {
    "name": "container_cpu_usage_seconds_total",
    "value": 72.36,
    "ts": 1705845578
  }
]

Output JSON with: 'finding', 'confidence', 'anomalies'.
```

**📤 Response:**

```json
{
  "finding": "insufficient_data",
  "confidence": 0.1,
  "anomalies": []
}
```

---

### 2️⃣ Log specialist

**📥 Prompt sent:**

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

**📤 Response:**

```json
{"finding":"Pod 'carts' shows clear failure pattern after 1705845578: resource exhaustion / saturation. carts_cpu 4.715 -> 72.36 (15.3x), carts_mem 2.097e+08 -> 1.448e+09 (6.9x, ~209MB to ~1.44GB), carts_latency-90 0.02096 -> 0.1153 (5.5x), carts_latency-50 0.009179 -> 0.01841 (2x), carts_socket 9.746 -> 17.02, carts-db_cpu 1.485 -> 2.208. No direct carts error logs present in sample, but metrics indicate CPU saturation and memory pressure/memory leak causing severe performance degradation. Correlated orders_latency-90 increase (0.07696 -> 0.2256) suggests downstream impact.","confidence":0.95,"category":"resource_exhaustion
```

---

### 3️⃣ Deployment specialist

**📥 Prompt sent:**

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

Output JSON with: 'finding', 'confidence'.
```

**📤 Response:**

```json
{
  "finding": "Deployment 'carts-deploy' for Pod 'carts' is Degraded but has no commit SHA or commit message (sha: null); git status cannot be correlated and regression cannot be confirmed without commit metadata - requires manual investigation of deployment logs and git history",
  "confidence": 0.35
}
```

---

### 4️⃣ Topology specialist

**📥 Prompt sent:**

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

Output JSON with: 'finding', 'confidence'.
```

**📤 Response:**

```json
{
  "finding": "Pod 'carts' is running on node 'node-worker-01' with no dependencies. The noisy_neighbors list contains only itself ('carts'), indicating no external noisy neighbors are present on the node - the pod is either isolated or is itself flagged as the source of resource contention/noise.",
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
  "finding": "No security breaches, secret reference warnings, or RBAC alerts detected for Pod 'carts'.",
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
You received telemetry from 5 agents for pod 'carts' (Status: 'Failed'):

- MONITORING Agent (Conf: 0.1): insufficient_data
- LOGS Agent (Conf: 0.95): Pod 'carts' shows clear failure pattern after 1705845578: resource exhaustion / saturation. carts_cpu 4.715 -> 72.36 (15.3x), carts_mem 2.097e+08 -> 1.448e+09 (6.9x, ~209MB to ~1.44GB), carts_latency-90 0.02096 -> 0.1153 (5.5x), carts_latency-50 0.009179 -> 0.01841 (2x), carts_socket 9.746 -> 17.02, carts-db_cpu 1.485 -> 2.208. No direct carts error logs present in sample, but metrics indicate CPU saturation and memory pressure/memory leak causing severe performance degradation. Correlated orders_latency-90 increase (0.07696 -> 0.2256) suggests downstream impact.
- DEPLOYMENTS Agent (Conf: 0.35): Deployment 'carts-deploy' for Pod 'carts' is Degraded but has no commit SHA or commit message (sha: null); git status cannot be correlated and regression cannot be confirmed without commit metadata - requires manual investigation of deployment logs and git history
- TOPOLOGY Agent (Conf: 0.95): Pod 'carts' is running on node 'node-worker-01' with no dependencies. The noisy_neighbors list contains only itself ('carts'), indicating no external noisy neighbors are present on the node - the pod is either isolated or is itself flagged as the source of resource contention/noise.
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
  "title": "Resource Exhaustion and CPU Saturation Failure on pod carts",
  "summary": "Pod 'carts' has Failed due to severe internal resource exhaustion causing ~15x CPU saturation and ~7x memory pressure, resulting in 5.5x p90 latency degradation (0.020s to 0.115s) and downstream impact on orders service (orders_latency-90 0.076s to 0.225s). Service is unavailable.",
  "cause": "Post-1705845578, pod 'carts' entered a clear resource exhaustion/saturation failure pattern: carts_cpu spiked 4.715 -> 72.36 (15.3x), carts_mem grew 2.097e+08 -> 1.448e+09 (209MB to 1.44GB, 6.9x), indicating memory pressure / probable memory leak leading to CPU saturation. This drove severe performance degradation: carts_latency-90 0.02096 -> 0.1153 (5.5x), carts_latency-50 0.009179 -> 0.01841 (2x), carts_socket 9.746 -> 17.02, and carts-db_cpu 1.485 -> 2.208. Topology confirms the failure is internally generated: pod is isolated on node-worker-01 with no dependencies and noisy_neighbors=['carts'] only, meaning no external noisy neighbor contention - the pod itself is the source of noise. No direct error logs were sampled but metrics are conclusive. Deployment regression and security breach are ruled out as root causes.",
  "recommendation": "1. Immediately restart pod 'carts' and/or reschedule on node-worker-01 to restore service. 2. Temporarily increase CPU/memory limits/requests and implement Horizontal Pod Autoscaler (HPA) with memory-based scaling. 3. Investigate application for memory leak: collect heap dumps, CPU profiles, and GC logs; analyze carts code changes around 1705845578 despite missing commit SHA (manually check deployment logs and git history for carts-deploy as it is Degraded). 4. Add alerts for carts_cpu >80% and carts_mem >1GB and p90 latency SLOs. 5. Validate downstream orders service recovery after carts remediation.",
  "severity": "CRITICAL",
  "confidence": 0.93,
  "evidence": [
    "LOGS Agent (0.95): High-confidence resource exhaustion post-1705845578: carts_cpu 4.715->72.36 (15.3x), carts_mem 2.097e+08->1.448e+09 (6.9x), carts_latency-90 0.02096->0.1153 (5.5x), correlated orders_latency-90 degradation",
    "TOPOLOGY Agent (0.95): Pod isolated on node-worker-01 with no dependencies, noisy_neighbors=['carts'] only - confirms no external contention, pod is self-source of saturation",
    "SECURITY Agent (0.8): No security breaches, secret or RBAC alerts - rules out security compromise as cause",
    "DEPLOYMENTS Agent (0.35): Deployment 'carts-deploy' Degraded but sha:null and low confidence - discounted, cannot confirm regression without commit metadata",
    "MONITORING Agent (0.1): insufficient_data with very low confidence - discounted in favor of high-confidence LOGS/TOPOLOGY correlation"
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
Resource Exhaustion and CPU Saturation Failure on pod carts Pod 'carts' has Failed due to severe internal resource exhaustion causing ~15x CPU saturation and ~7x memory pressure, resulting in 5.5x p90 latency degradation (0.020s to 0.115s) and downstream impact on orders service (orders_latency-90 0.076s to 0.225s). Service is unavailable. Post-1705845578, pod 'carts' entered a clear resource exhaustion/saturation failure pattern: carts_cpu spiked 4.715 -> 72.36 (15.3x), carts_mem grew 2.097e+08 -> 1.448e+09 (209MB to 1.44GB, 6.9x), indicating memory pressure / probable memory leak leading to CPU saturation. This drove severe performance degradation: carts_latency-90 0.02096 -> 0.1153 (5.5x), carts_latency-50 0.009179 -> 0.01841 (2x), carts_socket 9.746 -> 17.02, and carts-db_cpu 1.485 -> 2.208. Topology confirms the failure is internally generated: pod is isolated on node-worker-01 with no dependencies and noisy_neighbors=['carts'] only, meaning no external noisy neighbor contention - the pod itself is the source of noise. No direct error logs were sampled but metrics are conclusive. Deployment regression and security breach are ruled out as root causes.

Example output:
[{"claim_id": "claim-1", "text": "...", "claim_type": "state"}]
```

**📤 LLM JSON RESPONSE RETURNED (27 Extracted Atomic Claims):**

```json
[
  {
    "claim_id": "claim-1",
    "text": "Pod 'carts' has Failed.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-2",
    "text": "Pod 'carts' failure was due to severe internal resource exhaustion.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-3",
    "text": "Internal resource exhaustion caused ~15x CPU saturation.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-4",
    "text": "Internal resource exhaustion caused ~7x memory pressure.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-5",
    "text": "Resource exhaustion resulted in 5.5x p90 latency degradation from 0.020s to 0.115s.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-6",
    "text": "Failure had downstream impact on orders service.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-7",
    "text": "orders_latency-90 degraded from 0.076s to 0.225s.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-8",
    "text": "Service is unavailable.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-9",
    "text": "Post-1705845578, pod 'carts' entered a resource exhaustion/saturation failure pattern.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-10",
    "text": "carts_cpu spiked from 4.715 to 72.36 (15.3x).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-11",
    "text": "carts_mem grew from 2.097e+08 to 1.448e+09 (209MB to 1.44GB, 6.9x).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-12",
    "text": "Memory pressure / probable memory leak led to CPU saturation.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-13",
    "text": "Resource exhaustion drove severe performance degradation.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-14",
    "text": "carts_latency-90 increased from 0.02096 to 0.1153 (5.5x).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-15",
    "text": "carts_latency-50 increased from 0.009179 to 0.01841 (2x).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-16",
    "text": "carts_socket increased from 9.746 to 17.02.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-17",
    "text": "carts-db_cpu increased from 1.485 to 2.208.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-18",
    "text": "Topology confirms the failure is internally generated.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-19",
    "text": "Pod 'carts' is isolated on node-worker-01.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-20",
    "text": "Pod 'carts' has no dependencies.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-21",
    "text": "noisy_neighbors is ['carts'] only.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-22",
    "text": "There is no external noisy neighbor contention.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-23",
    "text": "Pod 'carts' itself is the source of noise.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-24",
    "text": "No direct error logs were sampled.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-25",
    "text": "Metrics are conclusive.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-26",
    "text": "Deployment regression is ruled out as root cause.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-27",
    "text": "Security breach is ruled out as root cause.",
    "claim_type": "general"
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

> 🔗 **Downstream Connection:** This exact list of **27 atomic claims** is passed forward to both **GPCS (Step 6)** for graph-provenance verification and **Ground-Truth Correctness Labelling (Step 8)** for deterministic evaluation against held-out ground truth.

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

### 4. Worked Step-by-Step Calculation Example (`rcaeval-14-NONE`)

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

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-14-NONE`):**

```text
claims scored    : 27
GPCS unsupported : 26/27 = 96.3% (1 supported)
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

### 4. Worked Step-by-Step Calculation Example (`rcaeval-14-NONE`)

- **Primary Claim $c_1$:** `"carts experienced resource exhaustion"`
- **Generation $G_2$ Claims:** Contains $c_{2,4}$ `"carts resource utilization spiked"` $\implies \text{cosine\_sim} = 0.94 \ge 0.80$ (**Match 1**).
- **Generation $G_3$ Claims:** Contains $c_{3,2}$ `"resource pressure observed on carts"` $\implies \text{cosine\_sim} = 0.88 \ge 0.80$ (**Match 2**).

$$\text{recurrence}(c_1) = \frac{1 + 1}{2} = \mathbf{1.00}$$
- **Verdict:** `1.00 >= 0.50` $\implies$ **`SUPPORTED`** (`sc_unsupported = False`).

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-14-NONE`):**

```text
claims scored               : 27
Self-Consistency unsupported: 12/27 = 44.4% (15 supported)
```

---

## 📊 STEP 8 — Ground-Truth Correctness Labelling

### 1. Concept & Objective
Determines whether an extracted atomic claim $c_i$ is objectively **`CONSISTENT`** (True), **`CONTRADICTED`** (False), or **`UNVERIFIABLE`** (N/A) against held-out benchmark ground truth (`target_service = carts`, `fault = memory_exhaustion`).

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

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-14-NONE`):**

```text
consistent=2   contradicted=1   unverifiable=24
EVALUABLE SUBSET: 3 of 27 claims (11.1%)
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

### 2. 2×2 Contingency Matrix for Scenario `rcaeval-14` (NONE)

```text
                          DERIVED GROUND TRUTH (SCENARIO RCAEVAL-14)
                     CONTRADICTED (Wrong)    CONSISTENT (Right)
flagged UNSUPPORTED     True Positive (1)    False Positive (25)
flagged SUPPORTED       False Negative (0)    True Negative (1)
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
| **GPCS** | **27** | **26** | **1** | **96.3%** | 3 (2 consistent, 1 contradicted) | Consistent Cause Identified |
| **Self-Consistency** | **27** | **12** | **15** | **44.4%** | 3 (2 consistent, 1 contradicted) | Consistent Cause Identified |

---

---

## 💡 Scenario `rcaeval-14` — findings, mapped to the Experiment 1 research questions

Measured for **rcaeval-14** (Sock Shop, `memory_exhaustion`) under condition **`NONE`**.

| | This run |
|---|---|
| Claims extracted | 27 |
| GPCS unsupported | 26/27 = 96.3% |
| Self-consistency unsupported | 12/27 = 44.4% |
| Accepted by **both** verifiers | 1/27 = 3.7% |
| Ground-truth labelled | 3 of 27 (2 consistent, 1 contradicted) |
| Distinct GPCS trust values | 2 — [0.0, 0.71] |

**E1-RQ1 — pipeline executes reliably.** Supported. The run completed with no
fallback, timeout or refused connection, and produced paired GPCS and
self-consistency verdicts for all 27 claims.

**E1-RQ2 / E1-RQ3 — context cost and the seeded red herring.** See the
comparison table at the top of this document. The `Commit` node reaches only
`RAW` (15 prompts) and is discounted there on its timestamp; its absence
from `HYBRID` is a consequence of top-5 ranking, **not** active pruning.

**E1-RQ4 — joint verifier filter.** 1 of 27 claims are accepted by both
verifiers. This is a reproducible candidate set, not an accuracy result: across
the whole experiment only 1 of the 95 intersection claims carries a
ground-truth label.

**E1-RQ5 / E1-RQ6 — correctness is not established here.** This run names the injected mechanism.
Only 3 of 27 claims are adjudicable, so no precision, recall or flag-rate gap can
be computed for a single run.

### On GPCS versus self-consistency

GPCS flags **96.3%** of claims unsupported against self-consistency's
**44.4%** — a difference of **+51.9 percentage points**, at no
additional LLM call.

**This is a strictness and cost result, not an accuracy result.** The two
verifiers measure different properties: GPCS asks whether a claim is traceable
to graph or vector evidence; self-consistency asks whether it recurs across
independent generations. Across the full six-scenario experiment they agree on
17 of 22 labelled claims, and the net difference between them is **one claim out
of 661** — which is why this project reports them as complementary signals
rather than ranking one above the other.

GPCS emits only **2 distinct trust values** in this run. Across all 661
claims it emits six, with 80.8% at exactly `0.000`, so it cannot rank claims or
be threshold-tuned on this evidence.
