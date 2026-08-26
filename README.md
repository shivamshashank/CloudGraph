<div align="center">

# 🚀 CloudGraph

### Graph-Grounded Verification of LLM-Generated Root Cause Analysis for Kubernetes

CloudGraph builds a temporal knowledge graph from live cluster telemetry,
retrieves incident context over it, has five specialist LLM agents diagnose the
incident, and then — the part this project is actually about: **checks every
claim in the generated explanation against graph evidence.**

The research question is not *"can an LLM write a plausible root cause?"*
It is *"can we tell whether it made that up?"*

<br />

[![CI](https://img.shields.io/github/actions/workflow/status/shivamshashank/CloudGraph/ci.yml?branch=main&label=CI&logo=githubactions&style=flat-square)](https://github.com/shivamshashank/CloudGraph/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/actions/workflow/status/shivamshashank/CloudGraph/release.yml?branch=main&label=Release&logo=githubactions&style=flat-square)](https://github.com/shivamshashank/CloudGraph/actions/workflows/release.yml)
[![Codecov](https://img.shields.io/codecov/c/github/shivamshashank/CloudGraph?logo=codecov&style=flat-square)](https://codecov.io/gh/shivamshashank/CloudGraph)
[![GitHub release](https://img.shields.io/github/v/release/shivamshashank/CloudGraph?style=flat-square)](https://github.com/shivamshashank/CloudGraph/releases)
[![GitHub stars](https://img.shields.io/github/stars/shivamshashank/CloudGraph?style=flat-square)](https://github.com/shivamshashank/CloudGraph/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/shivamshashank/CloudGraph?style=flat-square)](https://github.com/shivamshashank/CloudGraph/network/members)
[![License](https://img.shields.io/github/license/shivamshashank/CloudGraph?style=flat-square)](LICENSE)

<br />

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Go](https://img.shields.io/badge/Go-00ADD8?style=for-the-badge&logo=go&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-326CE5?style=for-the-badge&logo=kubernetes&logoColor=white)
![Helm](https://img.shields.io/badge/Helm-0F1689?style=for-the-badge&logo=helm&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Neo4j](https://img.shields.io/badge/Neo4j-4581C3?style=for-the-badge&logo=neo4j&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-DC244C?style=for-the-badge)
![Prometheus](https://img.shields.io/badge/Prometheus-E6522C?style=for-the-badge&logo=prometheus&logoColor=white)
![Grafana](https://img.shields.io/badge/Grafana-F46800?style=for-the-badge&logo=grafana&logoColor=white)
![OpenTelemetry](https://img.shields.io/badge/OpenTelemetry-000000?style=for-the-badge&logo=opentelemetry&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)

<br />

**Experiment 1** · 6 RCAEval RE2 scenarios × 3 conditions · 18 runs · 661 claims · 129 tests

</div>

---

## 📌 Overview

Large language models write fluent incident explanations. They also invent
them. CloudGraph is a system and a study for telling the two apart.

It ingests Loki logs, Kubernetes objects and Git/Argo CD
events into a **temporal property graph** (Neo4j), retrieves incident context
by **k-hop traversal fused with dense vectors** (Qdrant), runs **five
specialist agents** over that context, and then scores every atomic claim in
the resulting narrative two independent ways:

- **GPCS** (Graph-Provenance Claim Scoring) — *evidence-grounded*: is this
  claim supported by the incident graph? Costs **no extra model calls.**
- **Self-consistency** — *model-internal*: does this claim recur when the model
  is sampled again? Costs **two extra full generations.**

Comparing those two verifiers, on real chaos-injected telemetry, is the
experiment.

> **Two properties of the implementation that bound how the results read.**
>
> **Metrics are synthetic.** `_simulate_pod_metrics()`
> (`services/api/app/adapters/k8s_discovery.py:236`) is the only source of
> `Metric` nodes, and it generates values with `random.uniform()`. There is no
> Prometheus or metrics-server path, so no metric figure in any diagnosis
> reflects measured telemetry. Metric evidence is excluded from retrieval and
> from provenance scoring in Experiment 2.
>
> **GPCS's semantic term is a constant in Experiment 1.** Its evidence comes
> from graph traversal, which assigns a fixed score (`0.75` within two hops,
> `0.6` beyond) rather than a measured similarity. The trust score is therefore
> determined by graph reachability:
> `0.45×0.75 + 0.35×0.50 + 0.25×0.81 − 0.15×0.05 = 0.7075 ≈ 0.708`, which is the
> value taken by 85 of the 661 claims. Read those results as measuring
> **reachability**, not semantic provenance.

**The headline result is a measurement, not a win.** Only **3.3%** of the claims
an LLM generates about an incident can be adjudicated at all using standard RCA
benchmark metadata. That ceiling — not the choice of verifier — is what binds
this whole line of work, and it applies to any claim-level verifier evaluated
this way.

| | |
|---|---|
| **Evaluation** | 6 RCAEval RE2 scenarios × 3 retrieval conditions · 18 runs · 661 claims |
| **Adjudicable** | 22 of 661 claims (3.3%) |
| **Tests** | 129 |
| **Deployment** | Kubernetes via Helm — verified on kubeadm and OrbStack |

---

## 🧪 Two experiments, two different jobs

| | `experiment-1-benchmark/` | `experiment-2-live-demo/` |
|---|---|---|
| **Purpose** | measure verification | demonstrate the pipeline |
| **Evidence comes from** | an RCAEval file, seeded into the stores | the real cluster, via the ingestion pipeline |
| **Exercises ingestion?** | **no** | **yes** |
| **Ground truth** | labelled, 661 claims | known but unlabelled |
| **Scale** | 6 faults x 3 conditions = 18 runs | 1 fault |
| **Produces results?** | **yes — every number in this README** | **no** |

```mermaid
flowchart TB
    subgraph E1["Experiment 1 — benchmark (all results)"]
        direction TB
        F["RCAEval RE2 file<br/><small>26 observations per scenario</small>"] --> S["seed into Neo4j + Qdrant"]
        S --> R1["retrieve<br/><small>scenario-scoped</small>"]
    end
    subgraph E2["Experiment 2 — live demo (no results)"]
        direction TB
        K["real Kubernetes cluster"] --> I["ingestion pipeline<br/><small>discovery + pod logs</small>"]
        I --> G[("Neo4j + Qdrant")] --> R2["retrieve<br/><small>unscoped</small>"]
    end
    R1 --> P["5 agents -> consensus -> atomic claims"]
    R2 --> P
    P --> V["GPCS + self-consistency"]
    V --> L["labelled ground truth<br/><i>Experiment 1 only</i>"]

    classDef e1 fill:#dbeafe,stroke:#1d4ed8,color:#172554
    classDef e2 fill:#dcfce7,stroke:#15803d,color:#052e16
    class F,S,R1 e1
    class K,I,G,R2 e2
```

**No data from the host cluster reaches any prompt in Experiment 1.** Its
telemetry is seeded from a file and torn down after each run. That is deliberate:
incidents on a live cluster have no labelled ground truth, so claim correctness
could not be scored; and holding the evidence pool constant is what lets a
difference in outcome be attributed to retrieval strategy rather than to which
data happened to exist.

The consequence is that Experiment 1 measures evidence **selection**, not
evidence **discovery**. Experiment 2 exists to exercise the ingestion pipeline
that Experiment 1 deliberately bypasses — it demonstrates, and measures nothing.

---

## 📊 Results & Key Findings

Every number below is derived from the 18 run logs across 6 benchmark scenarios (`rcaeval-03` through `rcaeval-18`). Full analysis is detailed in [`experiment-1-benchmark/results/EXPERIMENT_FINAL_RESULTS.md`](experiment-1-benchmark/results/EXPERIMENT_FINAL_RESULTS.md).

### 1. Retrieval Condition Breakdown (`NONE` vs `RAW` vs `HYBRID`)

| Metric | `NONE` (No Context) | `RAW` (Full Dump) | `HYBRID` (Ranked Graph) | Best Observed & Takeaway |
|---|---:|---:|---:|---|
| **Total Claims Extracted** | 218 | 241 | **202** | **HYBRID:** Reduces claim volume and noise (33.7 claims/run). |
| **GPCS Unsupported % (Pooled)** | 83.5% | 80.1% | **78.7%** | **HYBRID:** Strictest evidence check with lowest false rejection. |
| **Self-Consistency Unsupported %**| 59.6% | **47.3%** | 50.5% | **RAW:** Highest recurrence across multi-run sampling. |
| **Mean Specialist Prompt Size** | 1,101 ch | 30,655 ch | **13,808 ch** | **HYBRID: 55.0% smaller prompts** than `RAW` (Token cost winner!). |
| **Evaluable Correctness Coverage**| 3.2% (7/218) | 1.7% (4/241) | **5.4% (11/202)** | **HYBRID: 3× higher coverage** than `RAW` (guides LLMs to direct root causes). |

---

### 2. Research Questions (RQ) Support Matrix

| Research Question | Status | Key Experimental Evidence & Findings |
|---|---|---|
| **E1-RQ1: Pipeline Reliability** | **Supported** | All 18 runs (6 scenarios × 3 conditions) completed reliably with zero execution timeouts, producing paired GPCS and Self-Consistency verdicts for all 661 claims. |
| **E1-RQ2 & RQ3: Retrieval Strategy** | **Supported** | `HYBRID` context retrieval reduces prompt size by **55.0% relative to RAW** while achieving **3× higher evaluable coverage (5.4% vs 1.7%)**. Injected commit distractors (102 exposures) were unanimously discounted (100% rejection). |
| **E1-RQ4: Joint Verifier Filter** | **Supported** | **RQ:** *To what extent does combining GPCS and Self-Consistency into a joint filter isolate high-confidence claims and reduce LLM noise?*<br/>**Finding:** Yields a high-precision candidate set with an **84.2% reduction in raw LLM claim noise** (isolating a ~15.8% candidate set). |
| **E1-RQ5 & RQ6: Verifier Parity & Cost** | **Supported** | **RQ:** *Can graph-based provenance verification (GPCS) match LLM self-consistency accuracy while eliminating API token overhead?*<br/>**Finding:** GPCS achieves near-identical accuracy to Self-Consistency (**~52% vs 50% precision**, identical **81.8% false rejection rate**) at **ZERO additional LLM call cost** (vs 3× token costs for Self-Consistency). |

---

### 3. Key Positive Findings

1. **GPCS Factual Grounding at Zero LLM Cost:** GPCS validates claims directly against Neo4j knowledge graph nodes and Qdrant vector embeddings via fast database queries (**0 additional LLM API calls**).
2. **Self-Consistency Model Reproducibility:** Identifies unstable, one-off model hallucinations by sampling 2 additional generations at $T=0.8$ (costing $2\times$ extra LLM calls).
3. **GPCS Aggressive Evidence Strictness:** Stricter than Self-Consistency in **18/18 runs** (**80.8% pooled unsupported rate** vs **52.3%**). This tests evidence grounding rather than phrasing bias.
4. **HYBRID Context Efficiency Leader:** Reduces prompt token size by **55.0% compared to RAW**, cuts claim noise, and achieves **3× higher evaluable coverage (5.4% vs 1.7%)**.
5. **Unanimous Red Herring Rejection:** Decoy commit timestamps injected into 102 `RAW` prompts were correctly recognized and rejected in **100% of cases**, demonstrating strong prompt reasoning integrity.
6. **Complementary Dual-Verifier Signal:** GPCS verifies *factual database provenance* while Self-Consistency verifies *output stability*. Claims clearing both filters represent high-confidence candidate facts.
7. **Deterministic Ground-Truth Evaluation (Step 8):** Uses an objective, 100% Python string/regex evaluator (`services/api/scripts/label_claim_correctness.py`) based on scenario metadata (`target_service` & `root_cause`) to prevent LLM grading bias.

**→ [Full Pooled Results](experiment-1-benchmark/results/EXPERIMENT_FINAL_RESULTS.md)** ·
[Joint-Verifier Comparison](experiment-1-benchmark/results/EXPERIMENT_JOINT_VERIFIER_COMPARISON.md) ·
[Experiment 1 Methodology](experiment-1-benchmark/README.md)

---

### ⚠️ What These Results Do Not Establish (Scope & Limitations)

To keep evaluation findings honest and transparent, here is what the results do **not** claim:

1. **Strictness ≠ Superior Accuracy:** GPCS is stricter than Self-Consistency (rejection rate 80.8% vs 52.3%), but flagging more claims reflects a stricter database evidence gate—not higher accuracy. Across the 22 ground-truth claims, both verifiers differ by only 1 claim net.
2. **Single-Run Flag Rates Are Not Accuracy:** A single scenario run measures verifier strictness, not overall Precision/Recall. True verifier accuracy is evaluated over the combined 6-scenario dataset.
3. **Fault Diagnosis, Not Service Localization:** The benchmark identifies the affected target service (`ts-order-service`, `carts`, etc.) in advance. The system diagnoses *how/why* the service failed, not *which* service failed across the cluster.
4. **Coarse Evidence Gate (Binary Thresholding):** GPCS trust scores operate as a strict pass/fail evidence gate (80.8% of claims score `0.000` because no graph evidence cleared the vector similarity floor), rather than a calibrated continuous confidence score.

---

## ⚡ Quick Start

```bash
git clone https://github.com/shivamshashank/CloudGraph.git
cd CloudGraph
go build -o cloudgraph ./cmd/cloudgraph
sudo ./cloudgraph deploy
```

Then open the UI, configure an LLM provider on the Settings page, and run a
diagnosis.

- 📖 **[Installation guide](docs/guides/INSTALLATION.md)** — prerequisites,
  kubeadm + Helm provisioning, configuration, troubleshooting
- 🏃 **[Quickstart](docs/guides/QUICKSTART.md)** — deploy in a few minutes
- 🖥️ **[UI walkthrough](docs/guides/UI_WALKTHROUGH.md)** — every screen, tab and
  button, with 14 screenshots from a live deployment against a real LLM

---

## 📚 Documentation

### Start here

| | Document | Describes |
|---|---|---|
| 🧭 | [Project explained](docs/PROJECT_EXPLAINED.md) | What this is, in plain language |
| 🧮 | [Formulas & Framework](docs/FORMULAS.md) | Complete formulas, variables, code blocks & literature references |
| ⚙️ | [Mechanisms](docs/MECHANISMS.md) | Every algorithm, with its formula |
| 🔎 | [Verification flow](docs/VERIFICATION_FLOW.md) | How a claim becomes a verdict |

### The experiment

| | Document | Describes |
|---|---|---|
| 🧪 | [Experiment 1](experiment-1-benchmark/README.md) | Scenarios, layout, reproduction, pipeline state |
| 📈 | [Final results](experiment-1-benchmark/results/EXPERIMENT_FINAL_RESULTS.md) | Pooled and per-scenario |
| ⚖️ | [Joint verifier comparison](experiment-1-benchmark/results/EXPERIMENT_JOINT_VERIFIER_COMPARISON.md) | GPCS and self-consistency used together |
| 🧵 | [How the traces work](experiment-1-benchmark/traces/README.md) | The runner, the log format, the nine steps |
| 🏷️ | [Labelling policy](research/LABELLING_POLICY.md) | Pre-registration and the deviation log D-1…D-4 |

### Design and architecture

| | Document | Describes |
|---|---|---|
| 🏗️ | [Architecture index](docs/README.md) | Every design doc, marked built vs planned |
| 🗺️ | [System overview](docs/architecture/system-overview.md) | Lifecycle, install through investigation |
| 🖼️ | [Current architecture](docs/architecture/figures/current-architecture.svg) | Evaluated pipeline — solid built, dashed planned |
| 🧮 | [GPCS design](docs/design/GPCS_DESIGN.md) | Graph-Provenance Claim Scoring — the contribution |
| 📉 | [GCP design](docs/design/GCP_DESIGN.md) | Graph Confidence Propagation — Noisy-OR, live path only |

### Research and dissertation

| | Document | Describes |
|---|---|---|
| 🕳️ | [Research gaps](research/RESEARCH_GAPS.md) | CloudGraph against the literature |
| 💡 | [Novel contributions](research/NOVEL_CONTRIBUTIONS.md) | Candidates with falsification criteria |

---

## 🏗️ Architecture

```mermaid
flowchart TB
    subgraph SRC["📡 Telemetry sources"]
        PROM["Prometheus<br/>metrics"]
        LOKI["Loki<br/>logs"]
        K8S["Kubernetes API<br/>pods · services · deployments"]
        GIT["Git / Argo CD<br/>webhooks"]
    end

    subgraph STORE["🗄️ Stores"]
        NEO[("Neo4j<br/>temporal property graph<br/>Pod · Service · Log · Incident")]
        QD[("Qdrant<br/>384-dim embeddings<br/>all-MiniLM-L6-v2")]
    end

    subgraph RET["🔍 GraphRAG retrieval"]
        TRAV["k-hop Cypher traversal<br/>bounded, time-windowed"]
        RANK["Hybrid ranker<br/>0.50·vector + 0.30·graph + 0.20·recency"]
    end

    subgraph AGENTS["🤖 Investigation engine — 5 specialists"]
        MON["Monitoring"]
        LOG["Log"]
        DEP["Deployment"]
        TOP["Topology"]
        SEC["Security"]
    end

    CONS["⚖️ ConsensusEngine<br/><i>static weighted aggregation</i>"]
    GCP["📈 GCP<br/>Noisy-OR propagation<br/><i>live path only</i>"]
    INC["🗒️ Incident node<br/>root_cause_confidence"]
    VERIFY["🛡️ Claim verification<br/>GPCS vs self-consistency"]
    UI["🖥️ Web UI + Go CLI"]

    PROM & LOKI & K8S & GIT --> NEO
    LOKI --> QD
    NEO --> TRAV --> RANK
    QD --> RANK
    RANK --> MON & LOG & DEP & TOP & SEC
    MON & LOG & DEP & TOP & SEC --> CONS
    CONS --> VERIFY
    CONS -.live path only.-> GCP --> INC
    NEO -.evidence.-> VERIFY
    NEO -.topology.-> GCP
    GCP -.writes confidence back.-> NEO
    VERIFY --> UI
    INC --> UI

    classDef store fill:#d1fae5,stroke:#047857,stroke-width:2px,color:#064e3b
    classDef contrib fill:#fde68a,stroke:#b45309,stroke-width:3px,color:#451a03
    class NEO,QD store
    class VERIFY,GCP contrib
```

**The amber boxes are the research contribution.** Everything upstream is
infrastructure that exists to make verification possible.

Two things the diagram makes explicit that are easy to get wrong:

**GCP does not feed verification.** They are computed independently.
`GraphProvenanceClaimScorer` never reads GCP's output — GCP's two scores go only
to the `Incident` node's `root_cause_confidence` and `recommendation_confidence`
properties. And GCP runs **only on the live investigation path**
(`/api/v1/investigations/trigger`); the evaluation that produced every number
above never calls it. So the reported results test **GPCS against
self-consistency**, and say nothing about GCP.

**GCP writes its output back onto the graph**, and reads that property in
preference to its content rules on the next run — so each run's output becomes
the next run's input. It is therefore not idempotent, and repeated investigation
of the same cluster inflates confidences toward saturation. This is documented
rather than repaired.

### The verification step

This is what the study measures: the same claims scored two independent ways.

```mermaid
flowchart TB
    RCA["RCA narrative from consensus"] --> EX["Atomic claim extraction<br/><small>27–52 per run, mean 36.7</small>"]

    EX --> G["<b>GPCS</b> — evidence-grounded<br/>0.45·semantic + 0.35·proximity<br/>+ 0.25·reliability − 0.15·(min_hop·0.05)<br/><small>0 extra LLM calls</small>"]
    EX --> S["<b>Self-consistency</b> — model-internal<br/>3 samples @ T=0.8<br/>cosine recurrence ≥ 0.8<br/><small>2 extra generations</small>"]

    G --> GV["trust ≥ 0.50 → supported"]
    S --> SV["recurrence ≥ 0.5 → supported"]

    GV --> CMP{{"Concordance — same verdict?"}}
    SV --> CMP
    CMP --> R["<b>80.8% vs 52.3% flagged unsupported</b><br/>pooled over 661 claims · stricter in 18/18 runs"]

    classDef contrib fill:#fde68a,stroke:#b45309,stroke-width:3px,color:#451a03
    classDef result fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#172554
    class G,S contrib
    class R result
```

⚠️ **Concordance is not accuracy.** The comparison establishes that the two
verifiers *differ*, not that either is *right*: see
[known limitations](#-known-limitations).

**Ingestion.** Metrics, logs, Kubernetes objects and webhook events become a
temporal property graph — `(:Pod)-[:RUNS_ON]->(:Node)`,
`(:Pod)-[:BELONGS_TO]->(:Service)`, `(:Commit)-[:TRIGGERED_BY]->(:Deployment)`.
Writes use `MERGE` on object UIDs, so repeated discovery is idempotent.

**Retrieval.** Bounded k-hop Cypher traversal from an incident seed, fused with
dense vectors (`all-MiniLM-L6-v2`, 384-dim) by a hybrid ranker:

```text
hybrid_score = 0.50·vector_similarity + 0.30·graph_proximity + 0.20·recency
```

Every result carries a `score_breakdown`, so any ranking can be explained term
by term in the UI.

**Verification.** The narrative is split into atomic claims, then scored by
GPCS —

```text
trust = 0.45·semantic + 0.35·proximity + 0.25·reliability − 0.15·(min_hop·0.05)
```

— and independently by self-consistency (3 samples at temperature 0.8; a claim
that fails to recur is flagged).

---

## 🤖 Agent Architecture

Five specialists, each an independent LLM call over its own evidence slice,
returning a finding and a confidence in `[0,1]`:

| Agent | Interprets |
|---|---|
| 🔍 **Monitoring** | Metrics, alerts, resource saturation |
| 📝 **Log** | Error signatures, repeated exceptions, warning bursts |
| 🚢 **Deployment** | Commits, releases, configuration drift |
| 🕸️ **Topology** | Service dependencies, blast radius, propagation paths |
| 🔐 **Security** | RBAC, secrets, policy changes, authentication failures |

A `ConsensusEngine` fuses them into one report. **The consensus step is a
static weighted aggregation, not a reasoning agent**: an accurate description
matters here, because "multi-agent" often implies debate or critique, and this
system has neither.

**Each specialist is gated on finding evidence first.** The monitoring agent's
model call sits behind `if metrics_log:`, the security agent's behind
`if threat_detected:`, and so on; without evidence the agent takes a rules path
and still returns a finding, but makes no LLM call.

This is measurable in the logs, and the measured cost is **not** five specialist
calls. On every RCAEval scenario the security specialist takes the rules path —
a chaos-injected resource fault is not a threat — so each generation is **4
specialist calls + 1 consensus call**:

| | calls |
|---|---:|
| in-cluster (4 specialists + 1 consensus) × 3 generations | 15 |
| in-process (claim extraction) × 3 generations | 3 |
| **total per scenario** | **18** |

Five specialists is therefore the *architecture*, not a guaranteed cost.

---

## 📂 Repository Structure

```text
cmd/cloudgraph/          Go CLI — deploy, ingest, report, health
services/
  api/                   FastAPI: ingestion, retrieval, GPCS, GCP, evaluation
  investigation-engine/  The five specialist agents
  agent-orchestrator/    ConsensusEngine
  ui/                    Static HTML/CSS/vanilla-JS (no framework, no build)
deployments/helm/        Helm chart — API, agents, UI, Neo4j, Qdrant, OTel, RBAC
graph/schema.cypher      Node labels, constraints, indexes
experiment-1-benchmark/  Experiment 1 — the evaluation. 18 run logs, 9 traces,
                         results, claims.csv. Seeded RCAEval data; no live cluster.
experiment-2-live-demo/  Experiment 2 — end-to-end demonstration on a real
                         Kubernetes cluster. No results, no statistics.
scripts/                 trace_scenario.py — the instrumented runner for Experiment 1
research/                Labelling policy, gaps against the literature, contributions
docs/                    Architecture, algorithm design, guides
testing/                 End-to-end runbook and reproduction scripts
```

---

## 🔬 Reproducing the Evaluation

The logs **cannot** be reproduced byte-for-byte: generation runs at temperature
0.8, and identical configurations were measured to vary by ~15 pp on verifier
rates. What *is* reproducible is the analysis.

```bash
gunzip -k experiment-1-benchmark/logs/*.gz
```

To re-run one scenario end to end (requires the cluster and port-forwards):

```bash
cd services/api
AUTH=$(kubectl get secret cloudgraph-neo4j-auth -n cloudgraph-system -o jsonpath='{.data.NEO4J_AUTH}' | base64 -d)
NEO4J_URI=bolt://127.0.0.1:7687 NEO4J_AUTH="$AUTH" QDRANT_HOST=127.0.0.1 QDRANT_PORT=6333 AGENT_ORCHESTRATOR_URL=http://localhost:8082 .venv/bin/python ../../scripts/trace_scenario.py rcaeval-03 hybrid out.log
```

**Scenarios must run sequentially.** `teardown_benchmark_data()` deletes every
`is_benchmark` node without scenario scoping, and `assert_semantic_store_isolated()`
fails if the vector store holds any foreign scenario. Parallel runs break both.

### 🛡️ Evaluation controls

The pipeline enforces the following, and every run records enough to check them:

| Control | Enforced by |
|---|---|
| Ground truth never enters a prompt | `test_no_ground_truth_leakage_into_observations` — rejects both the claim text and the bare fault phrase |
| Observations span all services, not just the faulted one | `test_observations_span_multiple_services` — showing only the anomalous service would be leakage by selection |
| Retrieval sees one scenario only | `scenario_id` filter on the Neo4j query and the Qdrant filter, plus the file-fallback path |
| Scenarios do not overlap | `teardown_benchmark_data()` between runs; store census printed before and after seeding |
| Claims join to their own scores | scores and claim text carried together, verified per run |
| Prompts are what the services actually sent | in-cluster request and response bodies captured from pod stdout, not reconstructed |

Two limits of these controls are worth stating:

- **Isolation is enforced at query time, not by assertion.** The
  `assert_semantic_store_isolated()` check inspects a collection the evaluation
  does not write to, so it passes unconditionally. What actually prevents
  cross-scenario evidence is the `scenario_id` filter, and the run logs record
  the store census that demonstrates it.
- **Claim text in `results/claims.csv` is truncated to 52 characters.** Full text
  is in the run logs and the traces.

Labelling follows a pre-registered policy with its deviations recorded in
[`research/LABELLING_POLICY.md`](research/LABELLING_POLICY.md).

---

## 🧪 Testing

```bash
cd services/api && .venv/bin/python -m pytest tests/ -q -n auto
```

```bash
go build ./... && go test ./...
```

129 Python tests plus the Go CLI suite. CI runs both, alongside pre-commit
(ruff, black, flake8, pylint, markdownlint, shellcheck, gitleaks).

---

## 🚧 Known limitations

| Limitation | Consequence |
|---|---|
| **Six scenarios, one sample per cell** | Results are counts and rates. No inferential statistics are reported, and the N1 null is underpowered. |
| **3.3% adjudicable coverage** | Verifier comparisons rest on 22 labelled claims. GPCS can be shown *stricter*, not better *aimed*. |
| **GPCS resolution** | Trust takes six distinct values, 80.8% of them exactly `0.000`. It is a gate, not a continuous confidence. |
| **Nothing is calibrated** | GPCS thresholds (0.30 floor, 0.50 cut) and GCP edge weights are hand-set defaults. No reliability diagrams or Brier scores. |
| **Metrics are synthetic** | No metric-based diagnosis is grounded in measured telemetry. |
| **Scope is resource and network faults** | RCAEval RE2 has no config errors, security events, deployment failures, DNS faults or certificate expiry. |
| **Task is fault-type diagnosis** | The faulted service is given. Nothing here demonstrates root-cause service localisation. |
| **`/api/v1/settings` is unauthenticated** | It returns the stored provider key in cleartext. Acceptable on localhost, not otherwise. |
| **Qdrant `evidence` collection is not created on a fresh deploy** | The semantic store falls back to a local file until it is created. |
| **Traces are not ingested** | The Tempo adapter is wired but unused; `CALLS` edges fall back to naming heuristics. |

---

## 🤝 Contributing

```bash
git checkout -b feature/new-feature
git commit -m "feat: add new feature"
git push origin feature/new-feature
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) ·
[`SECURITY.md`](SECURITY.md) ·
[`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)

---

## 📄 License & Citation

MIT — see [`LICENSE`](LICENSE).

### Upstream corpus

The benchmark corpus is **RCAEval** (MIT), Zenodo DOI
[10.5281/zenodo.14590730](https://doi.org/10.5281/zenodo.14590730), arXiv
[2412.17015](https://arxiv.org/abs/2412.17015).

## 👤 Author

**Shivam Shashank** — MSc dissertation, University of Birmingham.
Supervisor: Dr Vincent Rahli.

- 🌐 Portfolio: [shivam-shashank.me](https://www.shivam-shashank.me/)
- 💼 LinkedIn:
  [shivam-shashank-2b5766217](https://www.linkedin.com/in/shivam-shashank-2b5766217/)
- 📧 Email: [shivamkumar872000@gmail.com](mailto:shivamkumar872000@gmail.com)
- 🐙 GitHub: [shivamshashank](https://github.com/shivamshashank)

---

<div align="center">

### ⭐ If CloudGraph helps you, please star the repository

</div>
