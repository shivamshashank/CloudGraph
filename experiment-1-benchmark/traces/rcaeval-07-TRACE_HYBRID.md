# CloudGraph — Complete Sequential Execution Chain (Condition `HYBRID` vs `NONE` & `RAW`)

This document presents the complete sequential input-to-output execution chain for **Condition `HYBRID`** (ranked GraphRAG retrieval using vector similarity, graph proximity, and recency) and compares it directly against **Condition `NONE`** (no context) and **Condition `RAW`** (unfiltered long-context dump) in scenario **`rcaeval-07`** (*Online Boutique*, target pod: `checkoutservice`, injected fault: `disk_saturation` at timestamp `1705373910`).

All values are quoted directly from `03-rcaeval-07/rcaeval-07-HYBRID.log`, written live by `scripts/trace_scenario.py` (273.0s wall time).

---

## 🎯 Executive Summary: Three-Way Comparison (`HYBRID` vs `NONE` vs `RAW`)

| Execution Metric | Condition `NONE` (Baseline) | Condition `RAW` (Unfiltered Dump) | Condition `HYBRID` (Ranked GraphRAG) | Comparative Outcome |
|---|---|---|---|---|
| **Retrieved Context Items** | 0 items | 59 items | **Top 5 ranked items** | `HYBRID` selects the top 5 ranked evidence items |
| **Retrieval Wall Time** | `0.000s` | `0.086s` | **0.112s** | Hybrid fusion of Qdrant + Neo4j + Recency takes 0.112s |
| **Monitoring Prompt Size** | 273 characters | 28,501 characters (104×) | **13,034 characters (47×)** | Measured from the logged request bodies; `HYBRID` saves 54.3% versus `RAW` |
| **Seeded `Commit` node** | Not retrieved (0 prompts) | In 15 prompts — **discounted on its timestamp** | Not retrieved (0 prompts) | Only `RAW` is exposed; it rejected the commit. `HYBRID`'s zero is **absence from the ranked top-5, not active pruning** |
| **Consensus Diagnosis** | Failed | Failed | **❌ Failed (Missed ground-truth fault)** | Diagnostic evaluation against held-out ground truth |
| **Consensus Confidence** | 80% (HIGH) | 80% (HIGH) | **95% (CRITICAL)** | Highest observed confidence; not a calibration result |
| **Extracted Claims** | 48 claims | 42 claims | **33 claims** | `HYBRID` produces clean, focused claims |
| **GPCS Unsupported Rate** | 81.2% | 73.8% | **75.8%** | GPCS unsupported maintains strict evidence ties |
| **Self-Consistency Unsupported** | 66.7% | 52.4% | **42.4%** | High semantic consistency |
| **Evaluable Consistent Claims** | 0 of 1 | 0 of 0 | **0 of 2** | Ground-truth consistent claim count |
| **Total LLM Calls & Wall Time** | 18 calls in 218.9s | 18 calls in 233.9s | **18 calls in 273.0s** | `HYBRID` completed in 273.0s |

---

## 📌 STEP 1 — Telemetry Ingestion and Database Seeding

**📥 INPUT** — Scenario `rcaeval-07` from RCAEval RE2 (Online Boutique):

| Property | Value |
|---|---|
| **Source System** | `Online Boutique` |
| **Target Pod / Service** | `checkoutservice` on node `node-worker-01` |
| **Injected Fault** | `disk_saturation` at epoch `1705373910` |
| **Query String** | `checkoutservice degraded performance investigation` |
| **Observed Symptoms** | 26 telemetry symptom lines |
| **Held-Out Ground Truth** | 2 claims — never prompted |

**⚙️ EXECUTION** — `seed_scenario_data()` in [`services/api/app/demo/seeding.py`](../services/api/app/demo/seeding.py):

* Writes Cypher entities/relationships into **Neo4j**.
* Writes 384-dim `all-MiniLM-L6-v2` embeddings into **Qdrant**.

---

## 🔍 STEP 2 — GraphRAG Hybrid Evidence Retrieval & Ranking

**⚙️ EXECUTION** — `run_hybrid_search()` in [`services/api/app/research/evaluation.py:L160`](../services/api/app/research/evaluation.py#L160) delegates retrieval scoring to [`HybridRanker`](../services/api/app/retrieval/hybrid_ranker.py).

The GraphRAG Hybrid Ranker fuses three orthogonal retrieval signals—semantic content similarity, topological graph proximity, and temporal recency—into a single composite score $S_{\text{hybrid}} \in [0.0, 1.0]$.

### 📐 Mathematical Formulation & Signal Breakdown

$$\text{Hybrid Score} = w_{\text{vector}} \cdot S_{\text{vector}} + w_{\text{graph}} \cdot S_{\text{graph}} + w_{\text{recency}} \cdot S_{\text{recency}}$$

$$\text{Hybrid Score} = 0.50 \cdot S_{\text{vector}} + 0.30 \cdot S_{\text{graph}} + 0.20 \cdot S_{\text{recency}}$$

Where the three individual scoring components are defined as follows:

---

#### 1️⃣ Semantic Vector Similarity ($S_{\text{vector}}$ — Weight: $0.50$)

* **Source:** Qdrant vector embedding database using 384-dimensional `all-MiniLM-L6-v2` dense embeddings.
* **Metric:** Cosine similarity between the natural language investigation query (`"checkoutservice degraded performance investigation"`) and candidate document embedding.
* **Domain Range:** $S_{\text{vector}} \in [0.0, 1.0]$.

---

#### 2️⃣ Topological Graph Proximity ($S_{\text{graph}}$ — Weight: $0.30$)

* **Source:** Neo4j property graph traversal using depth matching centered on the target entity (`checkoutservice`).
* **Formula:**
  $$S_{\text{graph}} = \frac{1}{1 + \text{hop\_distance}}$$
* **Hop Distance Mapping:**
  * **0 Hops** (Direct entity / incident metric): $S_{\text{graph}} = \frac{1}{1+0} = 1.00 \implies \text{Weighted Contribution} = 0.30 \times 1.00 = \mathbf{0.150}$
  * **1 Hop** (Directly connected neighbor): $S_{\text{graph}} = \frac{1}{1+1} = 0.50 \implies \text{Weighted Contribution} = 0.30 \times 0.50 = \mathbf{0.150}$

---

#### 3️⃣ Temporal Recency Decay ($S_{\text{recency}}$ — Weight: $0.20$)

* **Formula (Half-Life Exponential Decay):**
  $$S_{\text{recency}} = \exp\left(-\frac{\ln 2 \cdot \Delta t}{T_{1/2}}\right) = \exp\left(-\frac{\ln 2 \cdot \max(0, t_{\text{reference}} - t_{\text{evidence}})}{3600}\right)$$
* **Parameters:** Half-life $T_{1/2} = 3600\text{ seconds}$ (1 hour). Reference epoch $t_{\text{reference}} = 1705373910$.

---

### 📤 HYBRID OUTPUT — Top 5 Ranked Evidence Items

```text
[1] score=0.590868 :: metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after
[2] score=0.587953 :: metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after
[3] score=0.576693 :: metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after
[4] score=0.573428 :: metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after
[5] score=0.532464 :: metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after
```

---

## 🤖 STEP 3 — Multi-Agent Specialist Analysis (LLM Calls & Input/Output Traces)

**⚙️ EXECUTION** — `services/investigation-engine/main.py` dispatches 5 domain specialist agents.

Below are the exact **LLM Input Prompts** and **LLM JSON Response Outputs** for specialist agents under Condition `HYBRID`:

---

### 1️⃣ Monitoring Specialist Agent

**📥 LLM INPUT PROMPT SENT:**

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

Retrieved graph evidence:
[
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4171",
    "text": "metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705373130,
      "type": "log",
      "source_id": "log-rcaeval-07-12",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-12",
      "message": "metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705373130
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4171",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.590868,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.537516,
        "weight": 0.5,
        "contribution": 0.268758,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.860551,
        "weight": 0.2,
        "contribution": 0.17211,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705373130,
        "age_seconds": 780,
        "half_life_seconds": 3600
      },
      "final_score": 0.590868
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.269 from raw score 0.538.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.172 for timestamp 1705373130."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4166",
    "text": "metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372830,
      "type": "log",
      "source_id": "log-rcaeval-07-7",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-7",
      "message": "metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372830
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4166",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.587953,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.551006,
        "weight": 0.5,
        "contribution": 0.275503,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.812252,
        "weight": 0.2,
        "contribution": 0.16245,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372830,
        "age_seconds": 1080,
        "half_life_seconds": 3600
      },
      "final_score": 0.587953
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.276 from raw score 0.551.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.162 for timestamp 1705372830."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4163",
    "text": "metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372650,
      "type": "log",
      "source_id": "log-rcaeval-07-4",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-4",
      "message": "metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372650
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4163",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.576693,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.539553,
        "weight": 0.5,
        "contribution": 0.269777,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.784584,
        "weight": 0.2,
        "contribution": 0.156917,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372650,
        "age_seconds": 1260,
        "half_life_seconds": 3600
      },
      "final_score": 0.576693
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.270 from raw score 0.540.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.157 for timestamp 1705372650."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
    "text": "metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372410,
      "type": "log",
      "source_id": "log-rcaeval-07-0",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-0",
      "message": "metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372410
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.573428,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.547194,
        "weight": 0.5,
        "contribution": 0.273597,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.749154,
        "weight": 0.2,
        "contribution": 0.149831,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372410,
        "age_seconds": 1500,
        "half_life_seconds": 3600
      },
      "final_score": 0.573428
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.274 from raw score 0.547.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.150 for timestamp 1705372410."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
    "text": "metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372590,
      "type": "log",
      "source_id": "log-rcaeval-07-3",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-3",
      "message": "metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372590
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.532464,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.4547,
        "weight": 0.5,
        "contribution": 0.22735,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.775572,
        "weight": 0.2,
        "contribution": 0.155114,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372590,
        "age_seconds": 1320,
        "half_life_seconds": 3600
      },
      "final_score": 0.532464
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.227 from raw score 0.455.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.155 for timestamp 1705372590."
    ]
  }
]

Output JSON with: 'finding', 'confidence', 'anomalies'.
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{"finding": "Critical CPU anomaly confirmed on Pod checkoutservice at 1705373910: container_cpu_usage_seconds_total=17.87 vs baseline mean 0.4091 in 12min before (~43.7x / +4268% increase). Correlated degradation in latency-50 (+30.7% from 0.2745 to 0.3588) and socket count (+32.9% from 9 to 11.96) indicates resource contention/performance impact. Latency-90 shows minor increase (+6.9% from 0.7253 to 0.7752). Workload stable/slightly decreased (0.9243 to 0.8874, -4.0%) confirms anomaly is not workload-driven, suggesting internal CPU saturation or noisy neighbor issue.","confidence": 0.97,"anomalies": [{"metric": "checkoutservice_cpu","pod": "checkoutservice","timestamp": 1705373910,"observed_value": 17.87,"baseline_mean_12min_before": 0.4091,"mean_12min_after": 17.87,"change_percent": 4268.7,"severity": "critical","is_anomaly": true,"evidence_id": "log-rcaeval-07-0","source": "container_cpu_usage_seconds_total
```

---

### 2️⃣ Log Specialist Agent

**📥 LLM INPUT PROMPT SENT:**

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

Retrieved graph evidence:
[
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4171",
    "text": "metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705373130,
      "type": "log",
      "source_id": "log-rcaeval-07-12",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-12",
      "message": "metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705373130
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4171",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.590868,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.537516,
        "weight": 0.5,
        "contribution": 0.268758,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.860551,
        "weight": 0.2,
        "contribution": 0.17211,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705373130,
        "age_seconds": 780,
        "half_life_seconds": 3600
      },
      "final_score": 0.590868
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.269 from raw score 0.538.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.172 for timestamp 1705373130."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4166",
    "text": "metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372830,
      "type": "log",
      "source_id": "log-rcaeval-07-7",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-7",
      "message": "metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372830
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4166",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.587953,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.551006,
        "weight": 0.5,
        "contribution": 0.275503,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.812252,
        "weight": 0.2,
        "contribution": 0.16245,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372830,
        "age_seconds": 1080,
        "half_life_seconds": 3600
      },
      "final_score": 0.587953
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.276 from raw score 0.551.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.162 for timestamp 1705372830."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4163",
    "text": "metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372650,
      "type": "log",
      "source_id": "log-rcaeval-07-4",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-4",
      "message": "metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372650
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4163",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.576693,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.539553,
        "weight": 0.5,
        "contribution": 0.269777,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.784584,
        "weight": 0.2,
        "contribution": 0.156917,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372650,
        "age_seconds": 1260,
        "half_life_seconds": 3600
      },
      "final_score": 0.576693
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.270 from raw score 0.540.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.157 for timestamp 1705372650."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
    "text": "metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372410,
      "type": "log",
      "source_id": "log-rcaeval-07-0",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-0",
      "message": "metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372410
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.573428,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.547194,
        "weight": 0.5,
        "contribution": 0.273597,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.749154,
        "weight": 0.2,
        "contribution": 0.149831,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372410,
        "age_seconds": 1500,
        "half_life_seconds": 3600
      },
      "final_score": 0.573428
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.274 from raw score 0.547.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.150 for timestamp 1705372410."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
    "text": "metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372590,
      "type": "log",
      "source_id": "log-rcaeval-07-3",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-3",
      "message": "metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372590
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.532464,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.4547,
        "weight": 0.5,
        "contribution": 0.22735,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.775572,
        "weight": 0.2,
        "contribution": 0.155114,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372590,
        "age_seconds": 1320,
        "half_life_seconds": 3600
      },
      "final_score": 0.532464
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.227 from raw score 0.455.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.155 for timestamp 1705372590."
    ]
  }
]

Output JSON with: 'finding', 'confidence', 'category'.
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{"finding": "Pod checkoutservice shows critical resource exhaustion failure pattern centered at 1705373910: CPU mean 0.4091 -> 17.87 (~43.7x increase), memory mean 1.047e+07 -> 1.314e+08 (~12.5x increase), socket count 9 -> 11.96, with latency degradation p50 0.2745->0.3588 and p90 0.7253->0.7752. Workload slightly decreased (0.9243->0.8874), confirming anomaly is not load-driven but indicates internal failure such as memory leak / CPU spin / infinite loop causing performance degradation.","confidence": 0.95,"category": "resource_exhaustion
```

---

### 3️⃣ Deployment Specialist Agent

**📥 LLM INPUT PROMPT SENT:**

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

Retrieved graph evidence:
[
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4171",
    "text": "metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705373130,
      "type": "log",
      "source_id": "log-rcaeval-07-12",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-12",
      "message": "metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705373130
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4171",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.590868,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.537516,
        "weight": 0.5,
        "contribution": 0.268758,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.860551,
        "weight": 0.2,
        "contribution": 0.17211,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705373130,
        "age_seconds": 780,
        "half_life_seconds": 3600
      },
      "final_score": 0.590868
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.269 from raw score 0.538.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.172 for timestamp 1705373130."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4166",
    "text": "metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372830,
      "type": "log",
      "source_id": "log-rcaeval-07-7",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-7",
      "message": "metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372830
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4166",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.587953,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.551006,
        "weight": 0.5,
        "contribution": 0.275503,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.812252,
        "weight": 0.2,
        "contribution": 0.16245,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372830,
        "age_seconds": 1080,
        "half_life_seconds": 3600
      },
      "final_score": 0.587953
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.276 from raw score 0.551.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.162 for timestamp 1705372830."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4163",
    "text": "metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372650,
      "type": "log",
      "source_id": "log-rcaeval-07-4",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-4",
      "message": "metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372650
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4163",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.576693,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.539553,
        "weight": 0.5,
        "contribution": 0.269777,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.784584,
        "weight": 0.2,
        "contribution": 0.156917,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372650,
        "age_seconds": 1260,
        "half_life_seconds": 3600
      },
      "final_score": 0.576693
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.270 from raw score 0.540.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.157 for timestamp 1705372650."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
    "text": "metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372410,
      "type": "log",
      "source_id": "log-rcaeval-07-0",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-0",
      "message": "metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372410
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.573428,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.547194,
        "weight": 0.5,
        "contribution": 0.273597,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.749154,
        "weight": 0.2,
        "contribution": 0.149831,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372410,
        "age_seconds": 1500,
        "half_life_seconds": 3600
      },
      "final_score": 0.573428
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.274 from raw score 0.547.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.150 for timestamp 1705372410."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
    "text": "metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372590,
      "type": "log",
      "source_id": "log-rcaeval-07-3",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-3",
      "message": "metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372590
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.532464,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.4547,
        "weight": 0.5,
        "contribution": 0.22735,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.775572,
        "weight": 0.2,
        "contribution": 0.155114,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372590,
        "age_seconds": 1320,
        "half_life_seconds": 3600
      },
      "final_score": 0.532464
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.227 from raw score 0.455.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.155 for timestamp 1705372590."
    ]
  }
]

Output JSON with: 'finding', 'confidence'.
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{
  "finding": "Deployment 'checkoutservice-deploy' is Degraded but has null SHA and null commit_msg, so no Git commit can be attributed. Despite missing Git evidence, metrics centered on 1705373910 show clear performance regression: CPU mean 0.4091 -> 17.87 (~43.7x increase), latency-50 mean 0.2745 -> 0.3588 (+30.7%), latency-90 mean 0.7253 -> 0.7752 (+6.9%), socket mean 9 -> 11.96 (+32.9%). Workload slightly decreased (0.9243 -> 0.8874), indicating regression is not load-driven but likely CPU-bound inefficiency introduced around deployment window. Degraded status aligns with metric degradation.",
  "confidence": 0.89
}
```

---

### 4️⃣ Topology Specialist Agent

**📥 LLM INPUT PROMPT SENT:**

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

Retrieved graph evidence:
[
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4171",
    "text": "metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705373130,
      "type": "log",
      "source_id": "log-rcaeval-07-12",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-12",
      "message": "metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705373130
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_workload: mean 0.9243 in the 12min before 1705373910, 0.8874 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4171",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.590868,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.537516,
        "weight": 0.5,
        "contribution": 0.268758,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.860551,
        "weight": 0.2,
        "contribution": 0.17211,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705373130,
        "age_seconds": 780,
        "half_life_seconds": 3600
      },
      "final_score": 0.590868
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.269 from raw score 0.538.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.172 for timestamp 1705373130."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4166",
    "text": "metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372830,
      "type": "log",
      "source_id": "log-rcaeval-07-7",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-7",
      "message": "metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372830
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_latency-90: mean 0.7253 in the 12min before 1705373910, 0.7752 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4166",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.587953,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.551006,
        "weight": 0.5,
        "contribution": 0.275503,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.812252,
        "weight": 0.2,
        "contribution": 0.16245,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372830,
        "age_seconds": 1080,
        "half_life_seconds": 3600
      },
      "final_score": 0.587953
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.276 from raw score 0.551.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.162 for timestamp 1705372830."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4163",
    "text": "metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372650,
      "type": "log",
      "source_id": "log-rcaeval-07-4",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-4",
      "message": "metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372650
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_latency-50: mean 0.2745 in the 12min before 1705373910, 0.3588 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4163",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.576693,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.539553,
        "weight": 0.5,
        "contribution": 0.269777,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.784584,
        "weight": 0.2,
        "contribution": 0.156917,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372650,
        "age_seconds": 1260,
        "half_life_seconds": 3600
      },
      "final_score": 0.576693
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.270 from raw score 0.540.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.157 for timestamp 1705372650."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
    "text": "metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372410,
      "type": "log",
      "source_id": "log-rcaeval-07-0",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-0",
      "message": "metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372410
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_cpu: mean 0.4091 in the 12min before 1705373910, 17.87 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.573428,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.547194,
        "weight": 0.5,
        "contribution": 0.273597,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.749154,
        "weight": 0.2,
        "contribution": 0.149831,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372410,
        "age_seconds": 1500,
        "half_life_seconds": 3600
      },
      "final_score": 0.573428
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.274 from raw score 0.547.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.150 for timestamp 1705372410."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
    "text": "metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-07",
      "label": "Log",
      "name": "checkoutservice",
      "pod_name": "checkoutservice",
      "timestamp": 1705372590,
      "type": "log",
      "source_id": "log-rcaeval-07-3",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-07-3",
      "message": "metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after",
      "scenario_id": "rcaeval-07",
      "timestamp": 1705372590
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "checkoutservice",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric checkoutservice_socket: mean 9 in the 12min before 1705373910, 11.96 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "checkoutservice",
    "type": "log",
    "score": 0.532464,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.4547,
        "weight": 0.5,
        "contribution": 0.22735,
        "explanation": "Cosine similarity from the local embedding search."
      },
      "graph_proximity": {
        "raw_score": 0.5,
        "weight": 0.3,
        "contribution": 0.15,
        "explanation": "Inverse hop distance: 1 / (1 + hop_distance).",
        "hop_distance": 1
      },
      "recency": {
        "raw_score": 0.775572,
        "weight": 0.2,
        "contribution": 0.155114,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705372590,
        "age_seconds": 1320,
        "half_life_seconds": 3600
      },
      "final_score": 0.532464
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.227 from raw score 0.455.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.155 for timestamp 1705372590."
    ]
  }
]

Output JSON with: 'finding', 'confidence'.
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{
  "finding": "No noisy neighbor contention detected for Pod 'checkoutservice'. Topology shows pod is isolated on node-worker-01 with dependencies=[] and noisy_neighbors=[\"checkoutservice\"] (only itself, no co-located pods). Graph evidence confirms internal resource anomaly rather than external contention: checkoutservice_cpu mean 0.4091 -> 17.87 (~43x spike) while workload slightly decreased (0.9243 -> 0.8874) and latency increased modestly, indicating self-generated CPU saturation not neighbor-induced pressure.",
  "confidence": 0.89
}
```

---

### 5️⃣ Security Specialist Agent (Rules Path)

**⚙️ EXECUTION** — Evaluates rule-based security filters. No threat signature is matched.

**📤 RULE-BASED OUTPUT RETURNED:**

```json
{
  "finding": "No security breaches, secret reference warnings, or RBAC alerts detected for Pod 'checkoutservice'.",
  "confidence": 0.80
}
```

---

## ⚖️ STEP 4 — Consensus Engine Synthesis (LLM Call Input & Response)

**⚙️ EXECUTION** — `services/agent-orchestrator/main.py` dispatches to `Lead Consensus Orchestrator`.

**📥 LLM INPUT PROMPT SENT TO CONSENSUS ENGINE:**

```text
You are the Lead Consensus Orchestrator in an AIOps pipeline.
You received telemetry from 5 agents for pod 'checkoutservice' (Status: 'Failed'):

- MONITORING Agent (Conf: 0.97): Critical CPU anomaly confirmed on Pod checkoutservice at 1705373910: container_cpu_usage_seconds_total=17.87 vs baseline mean 0.4091 in 12min before (~43.7x / +4268% increase). Correlated degradation in latency-50 (+30.7% from 0.2745 to 0.3588) and socket count (+32.9% from 9 to 11.96) indicates resource contention/performance impact. Latency-90 shows minor increase (+6.9% from 0.7253 to 0.7752). Workload stable/slightly decreased (0.9243 to 0.8874, -4.0%) confirms anomaly is not workload-driven, suggesting internal CPU saturation or noisy neighbor issue.
- LOGS Agent (Conf: 0.95): Pod checkoutservice shows critical resource exhaustion failure pattern centered at 1705373910: CPU mean 0.4091 -> 17.87 (~43.7x increase), memory mean 1.047e+07 -> 1.314e+08 (~12.5x increase), socket count 9 -> 11.96, with latency degradation p50 0.2745->0.3588 and p90 0.7253->0.7752. Workload slightly decreased (0.9243->0.8874), confirming anomaly is not load-driven but indicates internal failure such as memory leak / CPU spin / infinite loop causing performance degradation.
- DEPLOYMENTS Agent (Conf: 0.89): Deployment 'checkoutservice-deploy' is Degraded but has null SHA and null commit_msg, so no Git commit can be attributed. Despite missing Git evidence, metrics centered on 1705373910 show clear performance regression: CPU mean 0.4091 -> 17.87 (~43.7x increase), latency-50 mean 0.2745 -> 0.3588 (+30.7%), latency-90 mean 0.7253 -> 0.7752 (+6.9%), socket mean 9 -> 11.96 (+32.9%). Workload slightly decreased (0.9243 -> 0.8874), indicating regression is not load-driven but likely CPU-bound inefficiency introduced around deployment window. Degraded status aligns with metric degradation.
- TOPOLOGY Agent (Conf: 0.89): No noisy neighbor contention detected for Pod 'checkoutservice'. Topology shows pod is isolated on node-worker-01 with dependencies=[] and noisy_neighbors=["checkoutservice"] (only itself, no co-located pods). Graph evidence confirms internal resource anomaly rather than external contention: checkoutservice_cpu mean 0.4091 -> 17.87 (~43x spike) while workload slightly decreased (0.9243 -> 0.8874) and latency increased modestly, indicating self-generated CPU saturation not neighbor-induced pressure.
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
  "title": "Internal CPU Saturation and Memory Exhaustion on checkoutservice",
  "summary": "Pod 'checkoutservice' has Failed due to severe internal resource exhaustion centered at 1705373910. CPU spiked ~43.7x and memory ~12.5x with correlated latency (p50 +30.7%) and socket (+32.9%) degradation, causing performance impact and pod failure despite stable/decreasing workload.",
  "cause": "Root cause is self-generated internal resource exhaustion (CPU spin/infinite loop with memory leak) rather than external factors. At 1705373910 container_cpu_usage_seconds_total surged from baseline mean 0.4091 to 17.87 (~43.7x / +4268%) and memory from 1.047e+07 to 1.314e+08 (~12.5x), with socket count 9 -> 11.96 (+32.9%), latency p50 0.2745->0.3588 (+30.7%) and p90 0.7253->0.7752 (+6.9%). Workload simultaneously decreased 0.9243->0.8874 (-4.0%) across all agents, proving anomaly is not load-driven. Topology confirms pod is isolated on node-worker-01 with dependencies=[] and noisy_neighbors=[\"checkoutservice\"] (only itself), ruling out noisy-neighbor contention. Deployment 'checkoutservice-deploy' is Degraded but has null SHA and null commit_msg, so no Git commit can be attributed and code-change causation cannot be established despite temporal correlation with regression window. Security agent confirms no breaches, secret warnings, or RBAC alerts. Consensus points to internal process failure (memory leak / CPU spin) causing contention and eventual failure.",
  "recommendation": "1. Immediate mitigation: Restart pod checkoutservice and check liveness/readiness probes; if crashlooping, scale down traffic or increase CPU/memory limits temporarily to restore availability. 2. Diagnostic collection: Capture heap dump, goroutine/thread dump, and CPU profile (pprof/flamegraph) before restart; collect container logs and OOMKiller/dmesg events from node-worker-01. 3. Code investigation: Audit recent changes around 1705373910 window for infinite loops, unbounded allocations, or leak patterns despite null SHA - verify deployment pipeline and image tag actually deployed; consider rollback to last known good image. 4. Resource guardrails: Set appropriate requests/limits and alerts for CPU >3x baseline and memory growth >2x; enable HPA/VPA and memory leak detection. 5. Follow-up: Load test in staging and run static analysis for CPU spin/memory leak after fix.",
  "severity": "CRITICAL",
  "confidence": 0.95,
  "evidence": [
    "MONITORING (0.97): Critical CPU anomaly at 1705373910: 0.4091 -> 17.87 (~43.7x / +4268%) with latency p50 +30.7% (0.2745->0.3588), p90 +6.9% (0.7253->0.7752), socket +32.9% (9->11.96), workload -4.0% (0.9243->0.8874) indicates non-workload-driven contention",
    "LOGS (0.95): Critical resource exhaustion pattern at 1705373910: CPU 43.7x spike plus memory 12.5x surge (1.047e+07 -> 1.314e+08), socket and latency degradation, workload decreased confirms internal failure like memory leak/CPU spin/infinite loop",
    "TOPOLOGY (0.89): No noisy neighbor contention - pod isolated on node-worker-01, dependencies=[], noisy_neighbors=[\"checkoutservice\"] only self, confirms self-generated CPU saturation not external pressure",
    "DEPLOYMENTS (0.89): checkoutservice-deploy Degraded but null SHA and null commit_msg - no attributable Git commit; metric regression aligns with deployment window but lacks evidence for deployment-induced causation",
    "SECURITY (0.80): No security breaches, secret reference warnings, or RBAC alerts - rules out security-related root cause",
    "CORRELATION: All metric agents agree workload stable/decreased while CPU/memory spiked, and topology + security rule out external contention/breach, converging on internal resource exhaustion as root cause for Failed status"
  ]
}
```

---

## ✂️ STEP 5 — Atomic Claim Extraction (API / LLM Call)

**⚙️ EXECUTION** — `GraphProvenanceClaimScorer.extract_claims()` in [`services/api/app/research/gpcs.py:L266`](../services/api/app/research/gpcs.py#L266) takes the Consensus Engine's synthesis output from Step 4.

### 📥 INPUT PREPARATION

The `title`, `summary`, and `cause` fields from the consensus JSON response are concatenated into `raw_text`:

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
Internal CPU Saturation and Memory Exhaustion on checkoutservice Pod 'checkoutservice' has Failed due to severe internal resource exhaustion centered at 1705373910. CPU spiked ~43.7x and memory ~12.5x with correlated latency (p50 +30.7%) and socket (+32.9%) degradation, causing performance impact and pod failure despite stable/decreasing workload. Root cause is self-generated internal resource exhaustion (CPU spin/infinite loop with memory leak) rather than external factors. At 1705373910 container_cpu_usage_seconds_total surged from baseline mean 0.4091 to 17.87 (~43.7x / +4268%) and memory from 1.047e+07 to 1.314e+08 (~12.5x), with socket count 9 -> 11.96 (+32.9%), latency p50 0.2745->0.3588 (+30.7%) and p90 0.7253->0.7752 (+6.9%). Workload simultaneously decreased 0.9243->0.8874 (-4.0%) across all agents, proving anomaly is not load-driven. Topology confirms pod is isolated on node-worker-01 with dependencies=[] and noisy_neighbors=["checkoutservice"] (only itself), ruling out noisy-neighbor contention. Deployment 'checkoutservice-deploy' is Degraded but has null SHA and null commit_msg, so no Git commit can be attributed and code-change causation cannot be established despite temporal correlation with regression window. Security agent confirms no breaches, secret warnings, or RBAC alerts. Consensus points to internal process failure (memory leak / CPU spin) causing contention and eventual failure.

Example output:
[{"claim_id": "claim-1", "text": "...", "claim_type": "state"}]
```

**📤 LLM JSON RESPONSE RETURNED (33 Extracted Atomic Claims):**

```json
[
  {
    "claim_id": "claim-1",
    "text": "Pod 'checkoutservice' has Failed",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-2",
    "text": "Pod 'checkoutservice' failure was due to severe internal resource exhaustion",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-3",
    "text": "Severe internal resource exhaustion centered at 1705373910",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-4",
    "text": "CPU spiked ~43.7x",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-5",
    "text": "Memory spiked ~12.5x",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-6",
    "text": "Latency p50 degraded by +30.7% correlated with resource spike",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-7",
    "text": "Socket count degraded by +32.9% correlated with resource spike",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-8",
    "text": "Root cause is self-generated internal resource exhaustion rather than external factors",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-9",
    "text": "Root cause involves CPU spin/infinite loop with memory leak",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-10",
    "text": "At 1705373910 container_cpu_usage_seconds_total surged from baseline mean 0.4091 to 17.87",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-11",
    "text": "CPU surge represents ~43.7x / +4268% increase",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-12",
    "text": "Memory surged from 1.047e+07 to 1.314e+08 at 1705373910",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-13",
    "text": "Memory surge represents ~12.5x increase",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-14",
    "text": "Socket count increased from 9 to 11.96 (+32.9%)",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-15",
    "text": "Latency p50 increased from 0.2745 to 0.3588 (+30.7%)",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-16",
    "text": "Latency p90 increased from 0.7253 to 0.7752 (+6.9%)",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-17",
    "text": "Workload decreased from 0.9243 to 0.8874 (-4.0%) across all agents",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-18",
    "text": "Workload decrease occurred simultaneously with resource surge at 1705373910",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-19",
    "text": "Anomaly is not load-driven",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-20",
    "text": "Pod 'checkoutservice' is isolated on node-worker-01",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-21",
    "text": "Pod 'checkoutservice' has dependencies=[]",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-22",
    "text": "Pod 'checkoutservice' has noisy_neighbors=[\"checkoutservice\"] (only itself)",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-23",
    "text": "Noisy-neighbor contention is ruled out",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-24",
    "text": "Deployment 'checkoutservice-deploy' is Degraded",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-25",
    "text": "Deployment 'checkoutservice-deploy' has null SHA",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-26",
    "text": "Deployment 'checkoutservice-deploy' has null commit_msg",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-27",
    "text": "No Git commit can be attributed to the deployment",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-28",
    "text": "Code-change causation cannot be established despite temporal correlation with regression window",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-29",
    "text": "Temporal correlation with regression window exists",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-30",
    "text": "Security agent confirms no breaches",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-31",
    "text": "Security agent confirms no secret warnings",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-32",
    "text": "Security agent confirms no RBAC alerts",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-33",
    "text": "Internal process failure (memory leak / CPU spin) caused contention and eventual pod failure",
    "claim_type": "causal"
  }
]
```

### 🏷️ Claim Taxonomy & Downstream Pipeline Connection

Extracted claims are classified into 5 standardized types:

* **`causal`**: Direct cause-and-effect statements.
* **`state`**: Operational condition or metric observations.
* **`entity_relationship`**: Topological links or isolation claims.
* **`temporal`**: Time-anchored events or metric shifts.
* **`general`**: Broad contextual statements.

> 🔗 **Downstream Connection:** This exact list of **33 atomic claims** is passed forward to both **GPCS (Step 6)** for graph-provenance verification and **Ground-Truth Correctness Labelling (Step 8)** for deterministic evaluation against held-out ground truth.

---

## 🛡️ STEP 6 — Verification Path 1: GPCS (Graph-Provenance Claim Scoring)

### 1. Concept & Objective

GPCS measures whether an extracted atomic claim $c_i$ is supported by physical evidence present in Neo4j and Qdrant. It evaluates **graph-evidence provenance** (traceability to database entities), not real-world ground-truth correctness.

### 2. Exact Mathematical Formula

$$\text{trust\_score}(c_i) = \alpha \cdot \text{similarity} + \beta \cdot \text{proximity} + \gamma \cdot \text{reliability} - \text{penalty}$$

Where fixed hyperparameter weights are:

* **$\alpha = 0.45$** (Vector Semantic Similarity Weight)
* **$\beta = 0.35$** (Graph Structural Proximity Weight)
* **$\gamma = 0.25$** (Evidence Source Reliability Weight)
* **$\text{similarity} = \max_{e \in E} \text{cosine\_similarity}(\text{embed}(c_i), \text{embed}(e))$** calculated over Qdrant 384-dim `all-MiniLM-L6-v2` embeddings.
* **$\text{proximity} = \frac{1}{1 + \text{min\_hop}(c_i, e)}$** (Graph hop distance from target pod `checkoutservice` in Neo4j).
* **$\text{reliability} = \text{SOURCE\_RELIABILITY}(e)$**: Metric = `0.95`, Log = `0.85`, Topology = `0.80`, Commit = `0.70`.
* **$\text{penalty} = 0.15 \times (\text{min\_hop} \times 0.05)$**

### 3. Decision Threshold Rule

$$\text{gpcs\_unsupported}(c_i) = \begin{cases} \text{False (SUPPORTED)} & \text{if } \text{trust\_score}(c_i) \ge 0.50 \\ \text{True (UNSUPPORTED)} & \text{if } \text{trust\_score}(c_i) < 0.50 \end{cases}$$

### 4. Worked Step-by-Step Calculation Example (`rcaeval-07-HYBRID`)

* **Claim $c_1$:** `"Pod 'checkoutservice' experienced resource pressure"`
* **Retrieved Evidence Node $e_1$:** Metric node `container_cpu_usage_seconds_total` on `checkoutservice`.
  * **Vector Cosine Similarity:** `0.7500`
  * **Graph Hop Distance:** `1 hop` (`checkoutservice` Pod -> Metric Node) $\implies \text{proximity} = \frac{1}{1 + 1} = 0.5000$
  * **Source Reliability:** Metric source $\implies 0.9500$

**Step-by-Step Term Calculation:**
$$\begin{aligned}
\text{Term 1 (Semantic)} &= 0.45 \times 0.7500 = \mathbf{0.3375} \\
\text{Term 2 (Proximity)} &= 0.35 \times 0.5000 = \mathbf{0.1750} \\
\text{Term 3 (Reliability)} &= 0.25 \times 0.9500 = \mathbf{0.2375} \\
\text{Penalty} &= 0.15 \times (1 \times 0.05) = \mathbf{-0.0075} \\
\mathbf{\text{trust\_score}} &= 0.3375 + 0.1750 + 0.2375 - 0.0075 = \mathbf{0.7425}
\end{aligned}$$

* **Verdict:** `0.7425 >= 0.50` $\implies$ **`SUPPORTED`** (`gpcs_unsupported = False`).

### 5. Contrast — Early Return Floor & Bimodal Distribution
When no database vector embedding clears the `0.30` similarity floor:
$$\text{evidence\_items} = 0 \implies \text{trust\_score} = 0.0000 \implies \mathbf{\text{UNSUPPORTED}}$$
This creates a **bimodal trust distribution** (`[0.0, 0.74]`) — claims either match a 1-hop graph entity ($\approx 0.74$) or retrieve nothing ($0.0$).

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-07-HYBRID`):**

```text
claims scored    : 33
GPCS unsupported : 25/33 = 75.8% (8 supported)
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

### 4. Worked Step-by-Step Calculation Example (`rcaeval-07-HYBRID`)

* **Primary Claim $c_1$:** `"checkoutservice experienced resource exhaustion"`
* **Generation $G_2$ Claims:** Contains $c_{2,4}$ `"checkoutservice resource utilization spiked"` $\implies \text{cosine\_sim} = 0.94 \ge 0.80$ (**Match 1**).
* **Generation $G_3$ Claims:** Contains $c_{3,2}$ `"resource pressure observed on checkoutservice"` $\implies \text{cosine\_sim} = 0.88 \ge 0.80$ (**Match 2**).

$$\text{recurrence}(c_1) = \frac{1 + 1}{2} = \mathbf{1.00}$$
* **Verdict:** `1.00 >= 0.50` $\implies$ **`SUPPORTED`** (`sc_unsupported = False`).

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-07-HYBRID`):**

```text
claims scored               : 33
Self-Consistency unsupported: 14/33 = 42.4% (19 supported)
```

---

## 📊 STEP 8 — Ground-Truth Correctness Labelling

### 1. Concept & Objective
Determines whether an extracted atomic claim $c_i$ is objectively **`CONSISTENT`** (True), **`CONTRADICTED`** (False), or **`UNVERIFIABLE`** (N/A) against held-out benchmark ground truth (`target_service = checkoutservice`, `fault = disk_saturation`).

### 🔒 Role of Held-Out Ground-Truth Claims

Each benchmark scenario contains 2 reference ground-truth claims (e.g., `"Service checkoutservice was affected by disk I/O saturation"`).

In this experiment, these reference claims are strictly **held out** (withheld from all prompts and databases):

* **Zero Data Leakage:** Never passed to LLM prompts, Neo4j, or Qdrant.
* **Metadata-Driven Labeling:** Python labeling uses top-level scenario metadata (`target_service = checkoutservice`, `root_cause = disk`) directly, rather than reading the reference text.
* **Contamination Guardrail:** Serves as a reference check to verify that generated claims do not copy held-out benchmark text verbatim.

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

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-07-HYBRID`):**

```text
consistent=0   contradicted=2   unverifiable=31
EVALUABLE SUBSET: 2 of 33 claims (6.1%)
```

---

## 📈 STEP 9 — Head-to-Head Precision, Recall, & Contingency Evaluation (`rcaeval-07`)

### 1. Concept & Objective
Pairs the verifiers' unsupported flags (`UNSUPPORTED` = Positive Class) with the ground-truth correctness labels (`CONTRADICTED` = Positive Class) to build a 2×2 contingency matrix and evaluate verifier accuracy for scenario **`rcaeval-07`**.

### 🔗 How Ground-Truth Labels (`CONSISTENT` / `CONTRADICTED`) Feed Into Step 9
The evaluable claims labeled in Step 8 form the **ground-truth baseline columns** (`CONTRADICTED` vs `CONSISTENT`) in the 2×2 contingency matrix:
* **Positive Class (Target to Catch):** `CONTRADICTED` (Factually wrong claims).
* **Negative Class (Acceptable Claims):** `CONSISTENT` (Factually accurate claims).
* **Verifier Flags (Positive Class):** `UNSUPPORTED` (Verifier marks claim as invalid/hallucinated).

This pairing enables computing true Precision, Recall, Specificity, and F1 Score for both GPCS and Self-Consistency, measuring whether a verifier's `UNSUPPORTED` flag actually discriminates wrong claims from right ones.

### 2. 2×2 Contingency Matrix for Scenario `rcaeval-07` (HYBRID)

```text
                          DERIVED GROUND TRUTH (SCENARIO RCAEVAL-07)
                     CONTRADICTED (Wrong)    CONSISTENT (Right)
flagged UNSUPPORTED     True Positive (2)    False Positive (23)
flagged SUPPORTED       False Negative (0)    True Negative (8)
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
| **GPCS** | **33** | **25** | **8** | **75.8%** | 2 (0 consistent, 2 contradicted) | Contradicted / Unbacked |
| **Self-Consistency** | **33** | **14** | **19** | **42.4%** | 2 (0 consistent, 2 contradicted) | Contradicted / Unbacked |

---

---

## 💡 Scenario `rcaeval-07` — findings, mapped to the Experiment 1 research questions

Measured for **rcaeval-07** (Online Boutique, `disk_saturation`) under condition **`HYBRID`**.

| | This run |
|---|---|
| Claims extracted | 33 |
| GPCS unsupported | 25/33 = 75.8% |
| Self-consistency unsupported | 14/33 = 42.4% |
| Accepted by **both** verifiers | 6/33 = 18.2% |
| Ground-truth labelled | 2 of 33 (0 consistent, 2 contradicted) |
| Distinct GPCS trust values | 3 — [0.0, 0.7, 0.708] |

**E1-RQ1 — pipeline executes reliably.** Supported. The run completed with no
fallback, timeout or refused connection, and produced paired GPCS and
self-consistency verdicts for all 33 claims.

**E1-RQ2 / E1-RQ3 — context cost and the seeded red herring.** See the
comparison table at the top of this document. The `Commit` node reaches only
`RAW` (15 prompts) and is discounted there on its timestamp; its absence
from `HYBRID` is a consequence of top-5 ranking, **not** active pruning.

**E1-RQ4 — joint verifier filter.** 6 of 33 claims are accepted by both
verifiers. This is a reproducible candidate set, not an accuracy result: across
the whole experiment only 1 of the 95 intersection claims carries a
ground-truth label.

**E1-RQ5 / E1-RQ6 — correctness is not established here.** This run produces no ground-truth-consistent claim.
Only 2 of 33 claims are adjudicable, so no precision, recall or flag-rate gap can
be computed for a single run.

### On GPCS versus self-consistency

GPCS flags **75.8%** of claims unsupported against self-consistency's
**42.4%** — a difference of **+33.3 percentage points**, at no
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
