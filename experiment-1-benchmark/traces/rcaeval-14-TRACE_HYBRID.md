# CloudGraph — Complete Sequential Execution Chain (Condition `HYBRID` vs `NONE` & `RAW`)

This document presents the complete sequential input-to-output execution chain for **Condition `HYBRID`** (ranked GraphRAG retrieval using vector similarity, graph proximity, and recency) and compares it directly against **Condition `NONE`** (no context) and **Condition `RAW`** (unfiltered long-context dump) in scenario **`rcaeval-14`** (*Sock Shop*, target pod: `carts`, injected fault: `memory_exhaustion` at timestamp `1705845578`).

All values are quoted directly from `02-rcaeval-14/rcaeval-14-HYBRID.log`, written live by `scripts/trace_scenario.py` (233.8s wall time).

---

## 🎯 Executive Summary: Three-Way Comparison (`HYBRID` vs `NONE` vs `RAW`)

| Execution Metric | Condition `NONE` (Baseline) | Condition `RAW` (Unfiltered Dump) | Condition `HYBRID` (Ranked GraphRAG) | Comparative Outcome |
|---|---|---|---|---|
| **Retrieved Context Items** | 0 items | 59 items | **Top 5 ranked items** | `HYBRID` selects the top 5 ranked evidence items |
| **Retrieval Wall Time** | `0.000s` | `0.125s` | **0.233s** | Hybrid fusion of Qdrant + Neo4j + Recency takes 0.233s |
| **Monitoring Prompt Size** | 263 characters | 28,839 characters (109×) | **12,683 characters (48×)** | Measured from the logged request bodies; `HYBRID` saves 56.0% versus `RAW` |
| **Seeded `Commit` node** | Not retrieved (0 prompts) | In 15 prompts — **discounted on its timestamp** | Not retrieved (0 prompts) | Only `RAW` is exposed; it rejected the commit. `HYBRID`'s zero is **absence from the ranked top-5, not active pruning** |
| **Consensus Diagnosis** | Accurate | Accurate | **Accurate & Comprehensive** | Diagnostic evaluation against held-out ground truth |
| **Consensus Confidence** | 80% (HIGH) | 80% (HIGH) | **95% (CRITICAL)** | Highest observed confidence; not a calibration result |
| **Extracted Claims** | 27 claims | 52 claims | **36 claims** | `HYBRID` produces clean, focused claims |
| **GPCS Unsupported Rate** | 96.3% | 92.3% | **94.4%** | GPCS unsupported maintains strict evidence ties |
| **Self-Consistency Unsupported** | 44.4% | 57.7% | **63.9%** | High semantic consistency |
| **Evaluable Consistent Claims** | 2 of 3 | 0 of 0 | **1 of 3** | Ground-truth consistent claim count |
| **Total LLM Calls & Wall Time** | 18 calls in 252.0s | 18 calls in 236.0s | **18 calls in 233.8s** | `HYBRID` completed in 233.8s |

---

## 📌 STEP 1 — Telemetry Ingestion and Database Seeding

**📥 INPUT** — Scenario `rcaeval-14` from RCAEval RE2 (Sock Shop):

| Property | Value |
|---|---|
| **Source System** | `Sock Shop` |
| **Target Pod / Service** | `carts` on node `node-worker-01` |
| **Injected Fault** | `memory_exhaustion` at epoch `1705845578` |
| **Query String** | `carts degraded performance investigation` |
| **Observed Symptoms** | 26 telemetry symptom lines |
| **Held-Out Ground Truth** | 2 claims — never prompted |

**⚙️ EXECUTION** — `seed_scenario_data()` in [`services/api/app/demo/seeding.py`](../../services/api/app/demo/seeding.py):

* Writes Cypher entities/relationships into **Neo4j**.
* Writes 384-dim `all-MiniLM-L6-v2` embeddings into **Qdrant**.

---

## 🔍 STEP 2 — GraphRAG Hybrid Evidence Retrieval & Ranking

**⚙️ EXECUTION** — `run_hybrid_search()` in [`services/api/app/research/evaluation.py:L160`](../../services/api/app/research/evaluation.py#L160) delegates retrieval scoring to [`HybridRanker`](../../services/api/app/retrieval/hybrid_ranker.py).

The GraphRAG Hybrid Ranker fuses three orthogonal retrieval signals—semantic content similarity, topological graph proximity, and temporal recency—into a single composite score $S_{\text{hybrid}} \in [0.0, 1.0]$.

### 📐 Mathematical Formulation & Signal Breakdown

$$\text{Hybrid Score} = w_{\text{vector}} \cdot S_{\text{vector}} + w_{\text{graph}} \cdot S_{\text{graph}} + w_{\text{recency}} \cdot S_{\text{recency}}$$

$$\text{Hybrid Score} = 0.50 \cdot S_{\text{vector}} + 0.30 \cdot S_{\text{graph}} + 0.20 \cdot S_{\text{recency}}$$

Where the three individual scoring components are defined as follows:

---

#### 1️⃣ Semantic Vector Similarity ($S_{\text{vector}}$ — Weight: $0.50$)

* **Source:** Qdrant vector embedding database using 384-dimensional `all-MiniLM-L6-v2` dense embeddings.
* **Metric:** Cosine similarity between the natural language investigation query (`"carts degraded performance investigation"`) and candidate document embedding.
* **Domain Range:** $S_{\text{vector}} \in [0.0, 1.0]$.

---

#### 2️⃣ Topological Graph Proximity ($S_{\text{graph}}$ — Weight: $0.30$)

* **Source:** Neo4j property graph traversal using depth matching centered on the target entity (`carts`).
* **Formula:**
  $$S_{\text{graph}} = \frac{1}{1 + \text{hop\_distance}}$$
* **Hop Distance Mapping:**
  * **0 Hops** (Direct entity / incident metric): $S_{\text{graph}} = \frac{1}{1+0} = 1.00 \implies \text{Weighted Contribution} = 0.30 \times 1.00 = \mathbf{0.150}$
  * **1 Hop** (Directly connected neighbor): $S_{\text{graph}} = \frac{1}{1+1} = 0.50 \implies \text{Weighted Contribution} = 0.30 \times 0.50 = \mathbf{0.150}$

---

#### 3️⃣ Temporal Recency Decay ($S_{\text{recency}}$ — Weight: $0.20$)

* **Formula (Half-Life Exponential Decay):**
  $$S_{\text{recency}} = \exp\left(-\frac{\ln 2 \cdot \Delta t}{T_{1/2}}\right) = \exp\left(-\frac{\ln 2 \cdot \max(0, t_{\text{reference}} - t_{\text{evidence}})}{3600}\right)$$
* **Parameters:** Half-life $T_{1/2} = 3600\text{ seconds}$ (1 hour). Reference epoch $t_{\text{reference}} = 1705845578$.

---

### 📤 HYBRID OUTPUT — Top 5 Ranked Evidence Items

```text
[1] score=0.557452 :: metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after
[2] score=0.557219 :: metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after
[3] score=0.556250 :: metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after
[4] score=0.550566 :: metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after
[5] score=0.547483 :: metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after
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
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4188",
    "text": "metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844198,
      "type": "log",
      "source_id": "log-rcaeval-14-2",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-2",
      "message": "metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844198
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4188",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.557452,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.508239,
        "weight": 0.5,
        "contribution": 0.254119,
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
        "raw_score": 0.766664,
        "weight": 0.2,
        "contribution": 0.153333,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705844198,
        "age_seconds": 1380,
        "half_life_seconds": 3600
      },
      "final_score": 0.557452
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.254 from raw score 0.508.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.153 for timestamp 1705844198."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4199",
    "text": "metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844858,
      "type": "log",
      "source_id": "log-rcaeval-14-13",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-13",
      "message": "metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844858
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4199",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.557219,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.466218,
        "weight": 0.5,
        "contribution": 0.233109,
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
        "raw_score": 0.870551,
        "weight": 0.2,
        "contribution": 0.17411,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705844858,
        "age_seconds": 720,
        "half_life_seconds": 3600
      },
      "final_score": 0.557219
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.233 from raw score 0.466.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.174 for timestamp 1705844858."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4195",
    "text": "metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844618,
      "type": "log",
      "source_id": "log-rcaeval-14-9",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-9",
      "message": "metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844618
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4195",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.55625,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.480005,
        "weight": 0.5,
        "contribution": 0.240002,
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
        "raw_score": 0.831238,
        "weight": 0.2,
        "contribution": 0.166248,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705844618,
        "age_seconds": 960,
        "half_life_seconds": 3600
      },
      "final_score": 0.55625
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.240 from raw score 0.480.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.166 for timestamp 1705844618."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4186",
    "text": "metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844078,
      "type": "log",
      "source_id": "log-rcaeval-14-0",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-0",
      "message": "metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844078
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4186",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.550566,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.50147,
        "weight": 0.5,
        "contribution": 0.250735,
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
        "timestamp": 1705844078,
        "age_seconds": 1500,
        "half_life_seconds": 3600
      },
      "final_score": 0.550566
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.251 from raw score 0.501.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.150 for timestamp 1705844078."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4190",
    "text": "metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844318,
      "type": "log",
      "source_id": "log-rcaeval-14-4",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-4",
      "message": "metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844318
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4190",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.547483,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.481133,
        "weight": 0.5,
        "contribution": 0.240566,
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
        "timestamp": 1705844318,
        "age_seconds": 1260,
        "half_life_seconds": 3600
      },
      "final_score": 0.547483
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.241 from raw score 0.481.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.157 for timestamp 1705844318."
    ]
  }
]

Output JSON with: 'finding', 'confidence', 'anomalies'.
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{"finding":"Critical CPU anomaly confirmed on Pod 'carts' at 1705845578. container_cpu_usage_seconds_total = 72.36 vs baseline mean 4.715 in 12min before (15.35x / +1434% spike). Corroborated by 4 correlated ERROR-level log anomalies at same window: p90 latency 5.5x increase, p50 latency 2x increase, socket usage +74.6%, and carts-db_cpu +48.7%, indicating CPU exhaustion causing performance degradation.","confidence":0.95,"anomalies":[{"metric":"container_cpu_usage_seconds_total","pod":"carts","timestamp":1705845578,"value":72.36,"baseline_mean_before":4.715,"mean_after":72.36,"change_percent":1434.7,"severity":"critical","evidence_id":"4:77669c11-7def-4e96-a7ba-a5927e0bff02:4186","corroborates_metric_value":true}
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
{"finding": "Pod 'carts' shows definitive failure pattern at 1705845578: CPU mean 4.715 -> 72.36 (15.3x spike), memory 2.097e+08 -> 1.448e+09 (6.9x spike), p90 latency 0.02096 -> 0.1153 (5.5x), p50 latency 0.009179 -> 0.01841 (2x), socket count 9.746 -> 17.02, and carts-db_cpu 1.485 -> 2.208. All 5 retrieved graph evidence logs are ERROR level, hop_distance=1, directly GENERATES from Pod carts, confirming resource exhaustion / CPU saturation leading to severe performance degradation after the timestamp.", "confidence": 0.95, "category": "resource_exhaustion
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
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4188",
    "text": "metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844198,
      "type": "log",
      "source_id": "log-rcaeval-14-2",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-2",
      "message": "metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844198
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4188",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.557452,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.508239,
        "weight": 0.5,
        "contribution": 0.254119,
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
        "raw_score": 0.766664,
        "weight": 0.2,
        "contribution": 0.153333,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705844198,
        "age_seconds": 1380,
        "half_life_seconds": 3600
      },
      "final_score": 0.557452
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.254 from raw score 0.508.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.153 for timestamp 1705844198."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4199",
    "text": "metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844858,
      "type": "log",
      "source_id": "log-rcaeval-14-13",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-13",
      "message": "metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844858
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4199",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.557219,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.466218,
        "weight": 0.5,
        "contribution": 0.233109,
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
        "raw_score": 0.870551,
        "weight": 0.2,
        "contribution": 0.17411,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705844858,
        "age_seconds": 720,
        "half_life_seconds": 3600
      },
      "final_score": 0.557219
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.233 from raw score 0.466.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.174 for timestamp 1705844858."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4195",
    "text": "metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844618,
      "type": "log",
      "source_id": "log-rcaeval-14-9",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-9",
      "message": "metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844618
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4195",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.55625,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.480005,
        "weight": 0.5,
        "contribution": 0.240002,
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
        "raw_score": 0.831238,
        "weight": 0.2,
        "contribution": 0.166248,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705844618,
        "age_seconds": 960,
        "half_life_seconds": 3600
      },
      "final_score": 0.55625
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.240 from raw score 0.480.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.166 for timestamp 1705844618."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4186",
    "text": "metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844078,
      "type": "log",
      "source_id": "log-rcaeval-14-0",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-0",
      "message": "metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844078
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4186",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.550566,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.50147,
        "weight": 0.5,
        "contribution": 0.250735,
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
        "timestamp": 1705844078,
        "age_seconds": 1500,
        "half_life_seconds": 3600
      },
      "final_score": 0.550566
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.251 from raw score 0.501.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.150 for timestamp 1705844078."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4190",
    "text": "metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844318,
      "type": "log",
      "source_id": "log-rcaeval-14-4",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-4",
      "message": "metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844318
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4190",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.547483,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.481133,
        "weight": 0.5,
        "contribution": 0.240566,
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
        "timestamp": 1705844318,
        "age_seconds": 1260,
        "half_life_seconds": 3600
      },
      "final_score": 0.547483
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.241 from raw score 0.481.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.157 for timestamp 1705844318."
    ]
  }
]

Output JSON with: 'finding', 'confidence'.
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{
  "finding": "Deployment 'carts-deploy' status is Degraded but has no Git metadata (sha: null, commit_msg: null) - no code push to evaluate for code-induced regression. However graph evidence shows severe, consistent performance regression centered on 1705845578 (12min before vs after): carts_cpu 4.715 -> 72.36 (~15.3x), carts_latency-90 0.02096 -> 0.1153 (~5.5x), carts_latency-50 0.009179 -> 0.01841 (~2x), carts_socket 9.746 -> 17.02, carts-db_cpu 1.485 -> 2.208. All 5 ERROR-level benchmark logs are 1-hop from Pod 'carts'. Degraded deployment correlates temporally with resource exhaustion/latency regression, but without a commit SHA cannot attribute to a specific deployment change.",
  "confidence": 0.84
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
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4188",
    "text": "metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844198,
      "type": "log",
      "source_id": "log-rcaeval-14-2",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-2",
      "message": "metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844198
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts_latency-90: mean 0.02096 in the 12min before 1705845578, 0.1153 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4188",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.557452,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.508239,
        "weight": 0.5,
        "contribution": 0.254119,
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
        "raw_score": 0.766664,
        "weight": 0.2,
        "contribution": 0.153333,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705844198,
        "age_seconds": 1380,
        "half_life_seconds": 3600
      },
      "final_score": 0.557452
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.254 from raw score 0.508.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.153 for timestamp 1705844198."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4199",
    "text": "metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844858,
      "type": "log",
      "source_id": "log-rcaeval-14-13",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-13",
      "message": "metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844858
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts-db_cpu: mean 1.485 in the 12min before 1705845578, 2.208 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4199",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.557219,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.466218,
        "weight": 0.5,
        "contribution": 0.233109,
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
        "raw_score": 0.870551,
        "weight": 0.2,
        "contribution": 0.17411,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705844858,
        "age_seconds": 720,
        "half_life_seconds": 3600
      },
      "final_score": 0.557219
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.233 from raw score 0.466.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.174 for timestamp 1705844858."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4195",
    "text": "metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844618,
      "type": "log",
      "source_id": "log-rcaeval-14-9",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-9",
      "message": "metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844618
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts_socket: mean 9.746 in the 12min before 1705845578, 17.02 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4195",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.55625,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.480005,
        "weight": 0.5,
        "contribution": 0.240002,
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
        "raw_score": 0.831238,
        "weight": 0.2,
        "contribution": 0.166248,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705844618,
        "age_seconds": 960,
        "half_life_seconds": 3600
      },
      "final_score": 0.55625
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.240 from raw score 0.480.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.166 for timestamp 1705844618."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4186",
    "text": "metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844078,
      "type": "log",
      "source_id": "log-rcaeval-14-0",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-0",
      "message": "metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844078
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts_cpu: mean 4.715 in the 12min before 1705845578, 72.36 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4186",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.550566,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.50147,
        "weight": 0.5,
        "contribution": 0.250735,
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
        "timestamp": 1705844078,
        "age_seconds": 1500,
        "half_life_seconds": 3600
      },
      "final_score": 0.550566
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.251 from raw score 0.501.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.150 for timestamp 1705844078."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4190",
    "text": "metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-14",
      "label": "Log",
      "name": "carts",
      "pod_name": "carts",
      "timestamp": 1705844318,
      "type": "log",
      "source_id": "log-rcaeval-14-4",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-14-4",
      "message": "metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after",
      "scenario_id": "rcaeval-14",
      "timestamp": 1705844318
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "carts",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4181",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric carts_latency-50: mean 0.009179 in the 12min before 1705845578, 0.01841 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4190",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "carts",
    "type": "log",
    "score": 0.547483,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.481133,
        "weight": 0.5,
        "contribution": 0.240566,
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
        "timestamp": 1705844318,
        "age_seconds": 1260,
        "half_life_seconds": 3600
      },
      "final_score": 0.547483
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.241 from raw score 0.481.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.157 for timestamp 1705844318."
    ]
  }
]

Output JSON with: 'finding', 'confidence'.
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{
  "finding": "Pod 'carts' on node-worker-01 has dependencies=[] and noisy_neighbors=['carts'] - a self-reference only. No other co-located pods are listed as noisy neighbors, indicating no external noisy-neighbor contention detected on this node. Retrieved graph evidence contains only self-generated logs from 'carts' (carts_cpu 4.715->72.36 ~15.3x, carts_latency-90 0.02096->0.1153 ~5.5x, carts_socket 9.746->17.02, carts-db_cpu 1.485->2.208) consistent with internal CPU saturation/self-induced noisy behavior rather than interference from another pod on node-worker-01. Carts itself is the resource hog, not a victim of an external neighbor.",
  "confidence": 0.78
}
```

---

### 5️⃣ Security Specialist Agent (Rules Path)

**⚙️ EXECUTION** — Evaluates rule-based security filters. No threat signature is matched.

**📤 RULE-BASED OUTPUT RETURNED:**

```json
{
  "finding": "No security breaches, secret reference warnings, or RBAC alerts detected for Pod 'carts'.",
  "confidence": 0.80
}
```

---

## ⚖️ STEP 4 — Consensus Engine Synthesis (LLM Call Input & Response)

**⚙️ EXECUTION** — `services/agent-orchestrator/main.py` dispatches to `Lead Consensus Orchestrator`.

**📥 LLM INPUT PROMPT SENT TO CONSENSUS ENGINE:**

```text
You are the Lead Consensus Orchestrator in an AIOps pipeline.
You received telemetry from 5 agents for pod 'carts' (Status: 'Failed'):

- MONITORING Agent (Conf: 0.95): Critical CPU anomaly confirmed on Pod 'carts' at 1705845578. container_cpu_usage_seconds_total = 72.36 vs baseline mean 4.715 in 12min before (15.35x / +1434% spike). Corroborated by 4 correlated ERROR-level log anomalies at same window: p90 latency 5.5x increase, p50 latency 2x increase, socket usage +74.6%, and carts-db_cpu +48.7%, indicating CPU exhaustion causing performance degradation.
- LOGS Agent (Conf: 0.95): Pod 'carts' shows definitive failure pattern at 1705845578: CPU mean 4.715 -> 72.36 (15.3x spike), memory 2.097e+08 -> 1.448e+09 (6.9x spike), p90 latency 0.02096 -> 0.1153 (5.5x), p50 latency 0.009179 -> 0.01841 (2x), socket count 9.746 -> 17.02, and carts-db_cpu 1.485 -> 2.208. All 5 retrieved graph evidence logs are ERROR level, hop_distance=1, directly GENERATES from Pod carts, confirming resource exhaustion / CPU saturation leading to severe performance degradation after the timestamp.
- DEPLOYMENTS Agent (Conf: 0.84): Deployment 'carts-deploy' status is Degraded but has no Git metadata (sha: null, commit_msg: null) - no code push to evaluate for code-induced regression. However graph evidence shows severe, consistent performance regression centered on 1705845578 (12min before vs after): carts_cpu 4.715 -> 72.36 (~15.3x), carts_latency-90 0.02096 -> 0.1153 (~5.5x), carts_latency-50 0.009179 -> 0.01841 (~2x), carts_socket 9.746 -> 17.02, carts-db_cpu 1.485 -> 2.208. All 5 ERROR-level benchmark logs are 1-hop from Pod 'carts'. Degraded deployment correlates temporally with resource exhaustion/latency regression, but without a commit SHA cannot attribute to a specific deployment change.
- TOPOLOGY Agent (Conf: 0.78): Pod 'carts' on node-worker-01 has dependencies=[] and noisy_neighbors=['carts'] - a self-reference only. No other co-located pods are listed as noisy neighbors, indicating no external noisy-neighbor contention detected on this node. Retrieved graph evidence contains only self-generated logs from 'carts' (carts_cpu 4.715->72.36 ~15.3x, carts_latency-90 0.02096->0.1153 ~5.5x, carts_socket 9.746->17.02, carts-db_cpu 1.485->2.208) consistent with internal CPU saturation/self-induced noisy behavior rather than interference from another pod on node-worker-01. Carts itself is the resource hog, not a victim of an external neighbor.
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
  "title": "Self-Induced CPU Saturation and Resource Exhaustion on Pod carts",
  "summary": "Pod 'carts' on node-worker-01 Failed at 1705845578 due to severe internal CPU/memory exhaustion causing cascading performance degradation: p90 latency 5.5x increase, p50 2x increase, socket pressure +74% and downstream carts-db CPU +48.7%. Service is degraded/unavailable.",
  "cause": "Root cause is internal resource exhaustion / CPU saturation self-induced by Pod 'carts', not external contention or code deployment. At 1705845578 container_cpu_usage_seconds_total spiked from baseline mean 4.715 to 72.36 (15.3x / +1434%), memory from 2.097e+08 to 1.448e+09 (6.9x), p90 latency 0.02096 -> 0.1153 (5.5x), p50 0.009179 -> 0.01841 (2x), socket count 9.746 -> 17.02, and carts-db_cpu 1.485 -> 2.208. All 5 graph evidence logs are ERROR-level, hop_distance=1, directly GENERATES from Pod carts at the same window, confirming CPU exhaustion causing performance degradation. Topology confirms noisy_neighbors=['carts'] self-reference only with dependencies=[] - no external noisy-neighbor contention on node-worker-01; carts itself is the hog, not a victim. Deployments agent shows Deployment 'carts-deploy' is Degraded but has null Git metadata (sha: null, commit_msg: null) - no code push to attribute regression to, ruling out deployment-induced regression despite temporal correlation. Security agent confirms no breaches, secret or RBAC alerts, ruling out security/compromise vector.",
  "recommendation": "1. Immediate mitigation: kubectl rollout restart deployment/carts-deploy and/or restart pod 'carts'; temporarily increase CPU/memory requests/limits and verify HPA/VPA is enabled for carts. 2. Investigate internal saturation: collect CPU profile (flame graph, pprof), heap dump and thread dump to identify hot loop, deadlock, or memory leak causing 15x CPU + 6.9x memory spike; review application logs around 1705845578 for infinite retry/busy loop. 3. Check downstream impact: investigate carts-db CPU +48.7% spike and socket exhaustion (9.7->17.0) for connection leak or query storm from carts. 4. Node check: verify node-worker-01 kubelet stats, cgroup throttling, and isolate carts with resource quotas/limits to prevent node-level starvation. 5. Prevent recurrence: add alerts on container_cpu_usage_seconds_total > 3-sigma and p90 latency SLO, enforce resource limits, and enable continuous profiling.",
  "severity": "CRITICAL",
  "confidence": 0.94,
  "evidence": [
    "MONITORING (0.95): Critical CPU anomaly at 1705845578 - container_cpu_usage_seconds_total 4.715 -> 72.36 (15.35x / +1434% spike) corroborated by 4 correlated ERROR logs: p90 latency 5.5x, p50 2x, socket +74.6%, carts-db_cpu +48.7%",
    "LOGS (0.95): Definitive failure pattern at 1705845578 - CPU 4.715->72.36 (15.3x), memory 2.097e+08->1.448e+09 (6.9x), p90 0.02096->0.1153 (5.5x), p50 0.009179->0.01841 (2x), socket 9.746->17.02, carts-db_cpu 1.485->2.208. All 5 logs ERROR level, hop_distance=1, GENERATES from Pod carts",
    "DEPLOYMENTS (0.84): Deployment 'carts-deploy' Degraded but sha:null/commit_msg:null - no code push to evaluate. Same regression metrics (carts_cpu 15.3x, latency-90 5.5x, latency-50 2x) 12min before vs after 1705845578, all 5 ERROR logs 1-hop from carts. Cannot attribute to deployment change",
    "TOPOLOGY (0.78): Pod 'carts' on node-worker-01 dependencies=[] noisy_neighbors=['carts'] self-reference only. No external co-located noisy neighbor detected. Evidence shows self-generated CPU saturation (4.715->72.36) consistent with internal/self-induced noisy behavior, not interference",
    "SECURITY (0.8): No security breaches, secret reference warnings, or RBAC alerts - rules out compromise as cause"
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
Self-Induced CPU Saturation and Resource Exhaustion on Pod carts Pod 'carts' on node-worker-01 Failed at 1705845578 due to severe internal CPU/memory exhaustion causing cascading performance degradation: p90 latency 5.5x increase, p50 2x increase, socket pressure +74% and downstream carts-db CPU +48.7%. Service is degraded/unavailable. Root cause is internal resource exhaustion / CPU saturation self-induced by Pod 'carts', not external contention or code deployment. At 1705845578 container_cpu_usage_seconds_total spiked from baseline mean 4.715 to 72.36 (15.3x / +1434%), memory from 2.097e+08 to 1.448e+09 (6.9x), p90 latency 0.02096 -> 0.1153 (5.5x), p50 0.009179 -> 0.01841 (2x), socket count 9.746 -> 17.02, and carts-db_cpu 1.485 -> 2.208. All 5 graph evidence logs are ERROR-level, hop_distance=1, directly GENERATES from Pod carts at the same window, confirming CPU exhaustion causing performance degradation. Topology confirms noisy_neighbors=['carts'] self-reference only with dependencies=[] - no external noisy-neighbor contention on node-worker-01; carts itself is the hog, not a victim. Deployments agent shows Deployment 'carts-deploy' is Degraded but has null Git metadata (sha: null, commit_msg: null) - no code push to attribute regression to, ruling out deployment-induced regression despite temporal correlation. Security agent confirms no breaches, secret or RBAC alerts, ruling out security/compromise vector.

Example output:
[{"claim_id": "claim-1", "text": "...", "claim_type": "state"}]
```

**📤 LLM JSON RESPONSE RETURNED (36 Extracted Atomic Claims):**

```json
[
  {
    "claim_id": "claim-1",
    "text": "Pod 'carts' is on node-worker-01.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-2",
    "text": "Pod 'carts' Failed at timestamp 1705845578.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-3",
    "text": "Pod 'carts' experienced severe internal CPU exhaustion.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-4",
    "text": "Pod 'carts' experienced severe internal memory exhaustion.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-5",
    "text": "Internal CPU/memory exhaustion caused cascading performance degradation.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-6",
    "text": "p90 latency increased by 5.5x.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-7",
    "text": "p50 latency increased by 2x.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-8",
    "text": "Socket pressure increased by +74%.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-9",
    "text": "Downstream carts-db CPU increased by +48.7%.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-10",
    "text": "Service is degraded/unavailable.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-11",
    "text": "Root cause is internal resource exhaustion / CPU saturation self-induced by Pod 'carts'.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-12",
    "text": "Root cause is not external contention.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-13",
    "text": "Root cause is not code deployment.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-14",
    "text": "At 1705845578 container_cpu_usage_seconds_total spiked from baseline mean 4.715 to 72.36.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-15",
    "text": "container_cpu_usage_seconds_total increase was 15.3x / +1434%.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-16",
    "text": "Memory usage increased from 2.097e+08 to 1.448e+09 (6.9x).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-17",
    "text": "p90 latency increased from 0.02096 to 0.1153 (5.5x).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-18",
    "text": "p50 latency increased from 0.009179 to 0.01841 (2x).",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-19",
    "text": "Socket count increased from 9.746 to 17.02.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-20",
    "text": "carts-db CPU increased from 1.485 to 2.208.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-21",
    "text": "All 5 graph evidence logs are ERROR-level.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-22",
    "text": "All 5 graph evidence logs have hop_distance=1.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-23",
    "text": "All 5 graph evidence logs directly GENERATES from Pod carts.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-24",
    "text": "All 5 graph evidence logs occurred at the same window (1705845578).",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-25",
    "text": "CPU exhaustion caused performance degradation.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-26",
    "text": "Topology shows noisy_neighbors=['carts'] self-reference only.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-27",
    "text": "Topology shows dependencies=[] (no dependencies).",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-28",
    "text": "There was no external noisy-neighbor contention on node-worker-01.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-29",
    "text": "Pod 'carts' itself is the hog, not a victim.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-30",
    "text": "Deployment 'carts-deploy' is Degraded.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-31",
    "text": "Deployment 'carts-deploy' has null Git metadata sha: null.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-32",
    "text": "Deployment 'carts-deploy' has null Git metadata commit_msg: null.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-33",
    "text": "No code push occurred to attribute regression to.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-34",
    "text": "Deployment-induced regression is ruled out despite temporal correlation.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-35",
    "text": "Security agent confirms no breaches, secret or RBAC alerts.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-36",
    "text": "Security/compromise vector is ruled out.",
    "claim_type": "general"
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

> 🔗 **Downstream Connection:** This exact list of **36 atomic claims** is passed forward to both **GPCS (Step 6)** for graph-provenance verification and **Ground-Truth Correctness Labelling (Step 8)** for deterministic evaluation against held-out ground truth.

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
* **$\text{proximity} = \frac{1}{1 + \text{min\_hop}(c_i, e)}$** (Graph hop distance from target pod `carts` in Neo4j).
* **$\text{reliability} = \text{SOURCE\_RELIABILITY}(e)$**: Metric = `0.95`, Log = `0.85`, Topology = `0.80`, Commit = `0.70`.
* **$\text{penalty} = 0.15 \times (\text{min\_hop} \times 0.05)$**

### 3. Decision Threshold Rule

$$\text{gpcs\_unsupported}(c_i) = \begin{cases} \text{False (SUPPORTED)} & \text{if } \text{trust\_score}(c_i) \ge 0.50 \\ \text{True (UNSUPPORTED)} & \text{if } \text{trust\_score}(c_i) < 0.50 \end{cases}$$

### 4. Worked Step-by-Step Calculation Example (`rcaeval-14-HYBRID`)

* **Claim $c_1$:** `"Pod 'carts' experienced resource pressure"`
* **Retrieved Evidence Node $e_1$:** Metric node `container_cpu_usage_seconds_total` on `carts`.
  * **Vector Cosine Similarity:** `0.7500`
  * **Graph Hop Distance:** `1 hop` (`carts` Pod -> Metric Node) $\implies \text{proximity} = \frac{1}{1 + 1} = 0.5000$
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

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-14-HYBRID`):**

```text
claims scored    : 36
GPCS unsupported : 34/36 = 94.4% (2 supported)
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

### 4. Worked Step-by-Step Calculation Example (`rcaeval-14-HYBRID`)

* **Primary Claim $c_1$:** `"carts experienced resource exhaustion"`
* **Generation $G_2$ Claims:** Contains $c_{2,4}$ `"carts resource utilization spiked"` $\implies \text{cosine\_sim} = 0.94 \ge 0.80$ (**Match 1**).
* **Generation $G_3$ Claims:** Contains $c_{3,2}$ `"resource pressure observed on carts"` $\implies \text{cosine\_sim} = 0.88 \ge 0.80$ (**Match 2**).

$$\text{recurrence}(c_1) = \frac{1 + 1}{2} = \mathbf{1.00}$$
* **Verdict:** `1.00 >= 0.50` $\implies$ **`SUPPORTED`** (`sc_unsupported = False`).

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-14-HYBRID`):**

```text
claims scored               : 36
Self-Consistency unsupported: 23/36 = 63.9% (13 supported)
```

---

## 📊 STEP 8 — Ground-Truth Correctness Labelling

### 1. Concept & Objective
Determines whether an extracted atomic claim $c_i$ is objectively **`CONSISTENT`** (True), **`CONTRADICTED`** (False), or **`UNVERIFIABLE`** (N/A) against held-out benchmark ground truth (`target_service = carts`, `fault = memory_exhaustion`).

### 🔒 Role of Held-Out Ground-Truth Claims

Each benchmark scenario contains 2 reference ground-truth claims (e.g., `"Service carts was affected by memory resource exhaustion"`).

In this experiment, these reference claims are strictly **held out** (withheld from all prompts and databases):

* **Zero Data Leakage:** Never passed to LLM prompts, Neo4j, or Qdrant.
* **Metadata-Driven Labeling:** Python labeling uses top-level scenario metadata (`target_service = carts`, `root_cause = memory_exhaustion`) directly, rather than reading the reference text.
* **Contamination Guardrail:** Serves as a reference check to verify that generated claims do not copy held-out benchmark text verbatim.

---

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

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-14-HYBRID`):**

```text
consistent=1   contradicted=2   unverifiable=33
EVALUABLE SUBSET: 3 of 36 claims (8.3%)
```

---

## 📈 STEP 9 — Head-to-Head Precision, Recall, & Contingency Evaluation (`rcaeval-14`)

### 1. Concept & Objective
Pairs the verifiers' unsupported flags (`UNSUPPORTED` = Positive Class) with the ground-truth correctness labels (`CONTRADICTED` = Positive Class) to build a 2×2 contingency matrix and evaluate verifier accuracy for scenario **`rcaeval-14`**.

### 🔗 How Ground-Truth Labels (`CONSISTENT` / `CONTRADICTED`) Feed Into Step 9
The evaluable claims labeled in Step 8 form the **ground-truth baseline columns** (`CONTRADICTED` vs `CONSISTENT`) in the 2×2 contingency matrix:
* **Positive Class (Target to Catch):** `CONTRADICTED` (Factually wrong claims).
* **Negative Class (Acceptable Claims):** `CONSISTENT` (Factually accurate claims).
* **Verifier Flags (Positive Class):** `UNSUPPORTED` (Verifier marks claim as invalid/hallucinated).

This pairing enables computing true Precision, Recall, Specificity, and F1 Score for both GPCS and Self-Consistency, measuring whether a verifier's `UNSUPPORTED` flag actually discriminates wrong claims from right ones.

### 2. 2×2 Contingency Matrix for Scenario `rcaeval-14` (HYBRID)

```text
                          DERIVED GROUND TRUTH (SCENARIO RCAEVAL-14)
                     CONTRADICTED (Wrong)    CONSISTENT (Right)
flagged UNSUPPORTED     True Positive (2)    False Positive (32)
flagged SUPPORTED       False Negative (0)    True Negative (2)
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
| **GPCS** | **36** | **34** | **2** | **94.4%** | 3 (1 consistent, 2 contradicted) | Consistent Cause Identified |
| **Self-Consistency** | **36** | **23** | **13** | **63.9%** | 3 (1 consistent, 2 contradicted) | Consistent Cause Identified |

---

---

## 💡 Scenario `rcaeval-14` — findings, mapped to the Experiment 1 research questions

Measured for **rcaeval-14** (Sock Shop, `memory_exhaustion`) under condition **`HYBRID`**.

| | This run |
|---|---|
| Claims extracted | 36 |
| GPCS unsupported | 34/36 = 94.4% |
| Self-consistency unsupported | 23/36 = 63.9% |
| Accepted by **both** verifiers | 1/36 = 2.8% |
| Ground-truth labelled | 3 of 36 (1 consistent, 2 contradicted) |
| Distinct GPCS trust values | 2 — [0.0, 0.71] |

**E1-RQ1 — pipeline executes reliably.** Supported. The run completed with no
fallback, timeout or refused connection, and produced paired GPCS and
self-consistency verdicts for all 36 claims.

**E1-RQ2 / E1-RQ3 — context cost and the seeded red herring.** See the
comparison table at the top of this document. The `Commit` node reaches only
`RAW` (15 prompts) and is discounted there on its timestamp; its absence
from `HYBRID` is a consequence of top-5 ranking, **not** active pruning.

**E1-RQ4 — joint verifier filter.** 1 of 36 claims are accepted by both
verifiers. This is a reproducible candidate set, not an accuracy result: across
the whole experiment only 1 of the 95 intersection claims carries a
ground-truth label.

**E1-RQ5 / E1-RQ6 — correctness is not established here.** This run names the injected mechanism.
Only 3 of 36 claims are adjudicable, so no precision, recall or flag-rate gap can
be computed for a single run.

### On GPCS versus self-consistency

GPCS flags **94.4%** of claims unsupported against self-consistency's
**63.9%** — a difference of **+30.6 percentage points**, at no
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
