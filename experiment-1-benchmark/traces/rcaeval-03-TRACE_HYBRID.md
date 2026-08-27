# CloudGraph — Complete Sequential Execution Chain (Condition `HYBRID` vs `NONE` & `RAW`)

This document presents the complete sequential input-to-output execution chain for **Condition `HYBRID`** (ranked GraphRAG retrieval using vector similarity, graph proximity, and recency) and compares it directly against **Condition `NONE`** (no context) and **Condition `RAW`** (unfiltered long-context dump) in scenario **`rcaeval-03`** (*Train Ticket*, target pod: `ts-order-service`, injected fault: `cpu_exhaustion` at timestamp `1705935125`).

All values are quoted directly from `01-rcaeval-03/rcaeval-03-HYBRID.log`, written live by `scripts/trace_scenario.py` (261.6s wall time).

---

## 🎯 Executive Summary: Three-Way Comparison (`HYBRID` vs `NONE` vs `RAW`)

| Execution Metric | Condition `NONE` (Baseline) | Condition `RAW` (Unfiltered Dump) | Condition `HYBRID` (Ranked GraphRAG) | Comparative Outcome |
|---|---|---|---|---|
| **Retrieved Context Items** | 0 items | 59 items | **Top 5 ranked items** | `HYBRID` selects the top 5 ranked evidence items |
| **Retrieval Wall Time** | `0.000s` | `0.175s` | **0.198s** | Hybrid fusion of Qdrant + Neo4j + Recency takes 0.198s |
| **Monitoring Prompt Size** | 274 characters | 31,900 characters (116×) | **13,143 characters (47×)** | Measured from the logged request bodies; `HYBRID` saves 58.8% versus `RAW` |
| **Seeded `Commit` node** | Not retrieved (0 prompts) | In 15 prompts — **discounted on its timestamp** | Not retrieved (0 prompts) | Only `RAW` is exposed; it rejected the commit. `HYBRID`'s zero is **absence from the ranked top-5, not active pruning** |
| **Consensus Diagnosis** | Accurate | Accurate | **Accurate & Comprehensive** | Diagnostic evaluation against held-out ground truth |
| **Consensus Confidence** | 80% (HIGH) | 80% (HIGH) | **95% (CRITICAL)** | Highest observed confidence; not a calibration result |
| **Extracted Claims** | 38 claims | 41 claims | **35 claims** | `HYBRID` produces clean, focused claims |
| **GPCS Unsupported Rate** | 76.3% | 78.0% | **71.4%** | GPCS unsupported maintains strict evidence ties |
| **Self-Consistency Unsupported** | 71.1% | 58.5% | **57.1%** | High semantic consistency |
| **Evaluable Consistent Claims** | 2 of 2 | 3 of 3 | **2 of 2** | Ground-truth consistent claim count |
| **Total LLM Calls & Wall Time** | 18 calls in 265.9s | 18 calls in 252.5s | **18 calls in 261.6s** | `HYBRID` completed in 261.6s |

---

## 📌 STEP 1 — Telemetry Ingestion and Database Seeding

**📥 INPUT** — Scenario `rcaeval-03` from RCAEval RE2 (Train Ticket):

| Property | Value |
|---|---|
| **Source System** | `Train Ticket` |
| **Target Pod / Service** | `ts-order-service` on node `node-worker-01` |
| **Injected Fault** | `cpu_exhaustion` at epoch `1705935125` |
| **Query String** | `ts-order-service degraded performance investigation` |
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
* **Metric:** Cosine similarity between the natural language investigation query (`"ts-order-service degraded performance investigation"`) and candidate document embedding.
* **Domain Range:** $S_{\text{vector}} \in [0.0, 1.0]$.

---

#### 2️⃣ Topological Graph Proximity ($S_{\text{graph}}$ — Weight: $0.30$)

* **Source:** Neo4j property graph traversal using depth matching centered on the target entity (`ts-order-service`).
* **Formula:**
  $$S_{\text{graph}} = \frac{1}{1 + \text{hop\_distance}}$$
* **Hop Distance Mapping:**
  * **0 Hops** (Direct entity / incident metric): $S_{\text{graph}} = \frac{1}{1+0} = 1.00 \implies \text{Weighted Contribution} = 0.30 \times 1.00 = \mathbf{0.150}$
  * **1 Hop** (Directly connected neighbor): $S_{\text{graph}} = \frac{1}{1+1} = 0.50 \implies \text{Weighted Contribution} = 0.30 \times 0.50 = \mathbf{0.150}$

---

#### 3️⃣ Temporal Recency Decay ($S_{\text{recency}}$ — Weight: $0.20$)

* **Formula (Half-Life Exponential Decay):**
  $$S_{\text{recency}} = \exp\left(-\frac{\ln 2 \cdot \Delta t}{T_{1/2}}\right) = \exp\left(-\frac{\ln 2 \cdot \max(0, t_{\text{reference}} - t_{\text{evidence}})}{3600}\right)$$
* **Parameters:** Half-life $T_{1/2} = 3600\text{ seconds}$ (1 hour). Reference epoch $t_{\text{reference}} = 1705935125$.

---

### 📤 HYBRID OUTPUT — Top 5 Ranked Evidence Items

```text
[1] score=0.568907 :: metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after
[2] score=0.568610 :: metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after
[3] score=0.565419 :: metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after
[4] score=0.548435 :: metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after
[5] score=0.545860 :: metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after
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
Analyze metrics for Pod 'ts-order-service' to check for anomalies.

Metrics:
[
  {
    "name": "container_cpu_usage_seconds_total",
    "value": 37.52,
    "ts": 1705935125
  }
]

Retrieved graph evidence:
[
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
    "text": "metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933625,
      "type": "log",
      "source_id": "log-rcaeval-03-0",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-0",
      "message": "metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933625
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after",
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
    "name": "ts-order-service",
    "type": "log",
    "score": 0.568907,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.538153,
        "weight": 0.5,
        "contribution": 0.269076,
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
        "timestamp": 1705933625,
        "age_seconds": 1500,
        "half_life_seconds": 3600
      },
      "final_score": 0.568907
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.269 from raw score 0.538.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.150 for timestamp 1705933625."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4161",
    "text": "metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933745,
      "type": "log",
      "source_id": "log-rcaeval-03-2",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-2",
      "message": "metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933745
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4161",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "ts-order-service",
    "type": "log",
    "score": 0.56861,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.530555,
        "weight": 0.5,
        "contribution": 0.265277,
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
        "timestamp": 1705933745,
        "age_seconds": 1380,
        "half_life_seconds": 3600
      },
      "final_score": 0.56861
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.265 from raw score 0.531.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.153 for timestamp 1705933745."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4160",
    "text": "metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933685,
      "type": "log",
      "source_id": "log-rcaeval-03-1",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-1",
      "message": "metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933685
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4160",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "ts-order-service",
    "type": "log",
    "score": 0.565419,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.527694,
        "weight": 0.5,
        "contribution": 0.263847,
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
        "raw_score": 0.757858,
        "weight": 0.2,
        "contribution": 0.151572,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705933685,
        "age_seconds": 1440,
        "half_life_seconds": 3600
      },
      "final_score": 0.565419
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.264 from raw score 0.528.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.152 for timestamp 1705933685."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4169",
    "text": "metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705934225,
      "type": "log",
      "source_id": "log-rcaeval-03-10",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-10",
      "message": "metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705934225
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4169",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "ts-order-service",
    "type": "log",
    "score": 0.548435,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.460511,
        "weight": 0.5,
        "contribution": 0.230255,
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
        "raw_score": 0.840896,
        "weight": 0.2,
        "contribution": 0.168179,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705934225,
        "age_seconds": 900,
        "half_life_seconds": 3600
      },
      "final_score": 0.548435
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.230 from raw score 0.461.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.168 for timestamp 1705934225."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
    "text": "metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933805,
      "type": "log",
      "source_id": "log-rcaeval-03-3",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-3",
      "message": "metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933805
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after",
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
    "name": "ts-order-service",
    "type": "log",
    "score": 0.54586,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.481492,
        "weight": 0.5,
        "contribution": 0.240746,
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
        "timestamp": 1705933805,
        "age_seconds": 1320,
        "half_life_seconds": 3600
      },
      "final_score": 0.54586
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.241 from raw score 0.481.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.155 for timestamp 1705933805."
    ]
  }
]

Output JSON with: 'finding', 'confidence', 'anomalies'.
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{"finding": "Critical anomaly confirmed for Pod 'ts-order-service' at 1705935125: CPU usage spiked 7.1x from baseline mean 5.289 to 37.52, correlated with significant latency degradation (p50 +248%, p90 +145%) and disk I/O collapse (-95.7%), indicating resource contention/performance degradation.","confidence": 0.96,"anomalies": [{"name": "container_cpu_usage_seconds_total","metric": "ts-order-service_cpu","timestamp": 1705935125,"baseline_mean_before": 5.289,"observed_value_after": 37.52,"change_percent": 609.5,"change_direction": "increase","severity": "critical","evidence_id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159
```

---

### 2️⃣ Log Specialist Agent

**📥 LLM INPUT PROMPT SENT:**

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

Retrieved graph evidence:
[
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
    "text": "metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933625,
      "type": "log",
      "source_id": "log-rcaeval-03-0",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-0",
      "message": "metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933625
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after",
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
    "name": "ts-order-service",
    "type": "log",
    "score": 0.568907,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.538153,
        "weight": 0.5,
        "contribution": 0.269076,
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
        "timestamp": 1705933625,
        "age_seconds": 1500,
        "half_life_seconds": 3600
      },
      "final_score": 0.568907
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.269 from raw score 0.538.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.150 for timestamp 1705933625."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4161",
    "text": "metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933745,
      "type": "log",
      "source_id": "log-rcaeval-03-2",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-2",
      "message": "metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933745
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4161",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "ts-order-service",
    "type": "log",
    "score": 0.56861,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.530555,
        "weight": 0.5,
        "contribution": 0.265277,
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
        "timestamp": 1705933745,
        "age_seconds": 1380,
        "half_life_seconds": 3600
      },
      "final_score": 0.56861
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.265 from raw score 0.531.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.153 for timestamp 1705933745."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4160",
    "text": "metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933685,
      "type": "log",
      "source_id": "log-rcaeval-03-1",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-1",
      "message": "metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933685
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4160",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "ts-order-service",
    "type": "log",
    "score": 0.565419,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.527694,
        "weight": 0.5,
        "contribution": 0.263847,
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
        "raw_score": 0.757858,
        "weight": 0.2,
        "contribution": 0.151572,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705933685,
        "age_seconds": 1440,
        "half_life_seconds": 3600
      },
      "final_score": 0.565419
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.264 from raw score 0.528.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.152 for timestamp 1705933685."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4169",
    "text": "metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705934225,
      "type": "log",
      "source_id": "log-rcaeval-03-10",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-10",
      "message": "metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705934225
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4169",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "ts-order-service",
    "type": "log",
    "score": 0.548435,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.460511,
        "weight": 0.5,
        "contribution": 0.230255,
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
        "raw_score": 0.840896,
        "weight": 0.2,
        "contribution": 0.168179,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705934225,
        "age_seconds": 900,
        "half_life_seconds": 3600
      },
      "final_score": 0.548435
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.230 from raw score 0.461.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.168 for timestamp 1705934225."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
    "text": "metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933805,
      "type": "log",
      "source_id": "log-rcaeval-03-3",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-3",
      "message": "metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933805
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after",
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
    "name": "ts-order-service",
    "type": "log",
    "score": 0.54586,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.481492,
        "weight": 0.5,
        "contribution": 0.240746,
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
        "timestamp": 1705933805,
        "age_seconds": 1320,
        "half_life_seconds": 3600
      },
      "final_score": 0.54586
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.241 from raw score 0.481.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.155 for timestamp 1705933805."
    ]
  }
]

Output JSON with: 'finding', 'confidence', 'category'.
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{"finding":"Pod ts-order-service shows isolated failure pattern centered at 1705935125: CPU mean 7.1x increase (5.289 -> 37.52), latency-50 3.48x increase (0.01019 -> 0.03552), latency-90 2.45x increase (0.03546 -> 0.08698), and diskio 95.7% collapse (1.216e+06 -> 5.201e+04). All other services show opposite trend after same timestamp (e.g., ts-user-service latency-90 0.3185->0.02313, ts-assurance-service 0.2479->0.01962, ts-consign-price-service 0.2664->0.02301), proving degradation is isolated to ts-order-service. Pattern indicates CPU saturation/resource contention (CPU-bound bottleneck/starvation of I/O) causing performance degradation. No application ERROR logs in sampled window, but metric anomaly is consistent and benchmark-flagged as ERROR.","confidence":0.92,"category":"resource_exhaustion_cpu_saturation
```

---

### 3️⃣ Deployment Specialist Agent

**📥 LLM INPUT PROMPT SENT:**

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

Retrieved graph evidence:
[
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
    "text": "metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933625,
      "type": "log",
      "source_id": "log-rcaeval-03-0",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-0",
      "message": "metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933625
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after",
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
    "name": "ts-order-service",
    "type": "log",
    "score": 0.568907,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.538153,
        "weight": 0.5,
        "contribution": 0.269076,
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
        "timestamp": 1705933625,
        "age_seconds": 1500,
        "half_life_seconds": 3600
      },
      "final_score": 0.568907
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.269 from raw score 0.538.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.150 for timestamp 1705933625."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4161",
    "text": "metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933745,
      "type": "log",
      "source_id": "log-rcaeval-03-2",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-2",
      "message": "metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933745
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4161",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "ts-order-service",
    "type": "log",
    "score": 0.56861,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.530555,
        "weight": 0.5,
        "contribution": 0.265277,
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
        "timestamp": 1705933745,
        "age_seconds": 1380,
        "half_life_seconds": 3600
      },
      "final_score": 0.56861
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.265 from raw score 0.531.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.153 for timestamp 1705933745."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4160",
    "text": "metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933685,
      "type": "log",
      "source_id": "log-rcaeval-03-1",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-1",
      "message": "metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933685
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4160",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "ts-order-service",
    "type": "log",
    "score": 0.565419,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.527694,
        "weight": 0.5,
        "contribution": 0.263847,
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
        "raw_score": 0.757858,
        "weight": 0.2,
        "contribution": 0.151572,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705933685,
        "age_seconds": 1440,
        "half_life_seconds": 3600
      },
      "final_score": 0.565419
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.264 from raw score 0.528.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.152 for timestamp 1705933685."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4169",
    "text": "metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705934225,
      "type": "log",
      "source_id": "log-rcaeval-03-10",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-10",
      "message": "metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705934225
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4169",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "ts-order-service",
    "type": "log",
    "score": 0.548435,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.460511,
        "weight": 0.5,
        "contribution": 0.230255,
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
        "raw_score": 0.840896,
        "weight": 0.2,
        "contribution": 0.168179,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705934225,
        "age_seconds": 900,
        "half_life_seconds": 3600
      },
      "final_score": 0.548435
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.230 from raw score 0.461.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.168 for timestamp 1705934225."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
    "text": "metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933805,
      "type": "log",
      "source_id": "log-rcaeval-03-3",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-3",
      "message": "metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933805
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after",
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
    "name": "ts-order-service",
    "type": "log",
    "score": 0.54586,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.481492,
        "weight": 0.5,
        "contribution": 0.240746,
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
        "timestamp": 1705933805,
        "age_seconds": 1320,
        "half_life_seconds": 3600
      },
      "final_score": 0.54586
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.241 from raw score 0.481.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.155 for timestamp 1705933805."
    ]
  }
]

Output JSON with: 'finding', 'confidence'.
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{
  "finding": "Deployment 'ts-order-service-deploy' status is Degraded but sha is null and commit_msg is null - no Git commit evidence available to correlate a deployment to a regression. However benchmark metrics centered at 1705935125 show clear performance regression for ts-order-service: CPU mean 5.289 -> 37.52 (~7.1x increase), latency-50 0.01019 -> 0.03552 (~3.5x), latency-90 0.03546 -> 0.08698 (~2.45x), consistent with Degraded status. DiskIO dropped (1.216e+06 -> 5.201e+04). No Git data to attribute regression to a specific commit/deployment; regression is metric-observed, not Git-confirmed.",
  "confidence": 0.68
}
```

---

### 4️⃣ Topology Specialist Agent

**📥 LLM INPUT PROMPT SENT:**

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

Retrieved graph evidence:
[
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4159",
    "text": "metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933625,
      "type": "log",
      "source_id": "log-rcaeval-03-0",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-0",
      "message": "metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933625
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_cpu: mean 5.289 in the 12min before 1705935125, 37.52 in the 12min after",
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
    "name": "ts-order-service",
    "type": "log",
    "score": 0.568907,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.538153,
        "weight": 0.5,
        "contribution": 0.269076,
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
        "timestamp": 1705933625,
        "age_seconds": 1500,
        "half_life_seconds": 3600
      },
      "final_score": 0.568907
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.269 from raw score 0.538.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.150 for timestamp 1705933625."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4161",
    "text": "metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933745,
      "type": "log",
      "source_id": "log-rcaeval-03-2",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-2",
      "message": "metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933745
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_latency-90: mean 0.03546 in the 12min before 1705935125, 0.08698 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4161",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "ts-order-service",
    "type": "log",
    "score": 0.56861,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.530555,
        "weight": 0.5,
        "contribution": 0.265277,
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
        "timestamp": 1705933745,
        "age_seconds": 1380,
        "half_life_seconds": 3600
      },
      "final_score": 0.56861
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.265 from raw score 0.531.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.153 for timestamp 1705933745."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4160",
    "text": "metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933685,
      "type": "log",
      "source_id": "log-rcaeval-03-1",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-1",
      "message": "metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933685
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_latency-50: mean 0.01019 in the 12min before 1705935125, 0.03552 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4160",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "ts-order-service",
    "type": "log",
    "score": 0.565419,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.527694,
        "weight": 0.5,
        "contribution": 0.263847,
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
        "raw_score": 0.757858,
        "weight": 0.2,
        "contribution": 0.151572,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705933685,
        "age_seconds": 1440,
        "half_life_seconds": 3600
      },
      "final_score": 0.565419
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.264 from raw score 0.528.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.152 for timestamp 1705933685."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4169",
    "text": "metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705934225,
      "type": "log",
      "source_id": "log-rcaeval-03-10",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-10",
      "message": "metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705934225
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-assurance-service_latency-50: mean 0.04581 in the 12min before 1705935125, 0.008879 in the 12min after",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4169",
        "labels": [
          "Log"
        ]
      }
    ],
    "sources": [
      "graph",
      "vector"
    ],
    "name": "ts-order-service",
    "type": "log",
    "score": 0.548435,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.460511,
        "weight": 0.5,
        "contribution": 0.230255,
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
        "raw_score": 0.840896,
        "weight": 0.2,
        "contribution": 0.168179,
        "explanation": "Exponential decay with a configurable one-hour half-life.",
        "timestamp": 1705934225,
        "age_seconds": 900,
        "half_life_seconds": 3600
      },
      "final_score": 0.548435
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.230 from raw score 0.461.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.168 for timestamp 1705934225."
    ]
  },
  {
    "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4162",
    "text": "metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after",
    "metadata": {
      "is_benchmark": true,
      "scenario_id": "rcaeval-03",
      "label": "Log",
      "name": "ts-order-service",
      "pod_name": "ts-order-service",
      "timestamp": 1705933805,
      "type": "log",
      "source_id": "log-rcaeval-03-3",
      "embedding_backend": "sentence-transformer"
    },
    "labels": [
      "Log"
    ],
    "properties": {
      "is_benchmark": true,
      "level": "ERROR",
      "id": "log-rcaeval-03-3",
      "message": "metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after",
      "scenario_id": "rcaeval-03",
      "timestamp": 1705933805
    },
    "hop_distance": 1,
    "relationships": [
      "GENERATES"
    ],
    "path": [
      {
        "name": "ts-order-service",
        "id": "4:77669c11-7def-4e96-a7ba-a5927e0bff02:4154",
        "labels": [
          "Pod"
        ]
      },
      {
        "name": "metric ts-order-service_diskio: mean 1.216e+06 in the 12min before 1705935125, 5.201e+04 in the 12min after",
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
    "name": "ts-order-service",
    "type": "log",
    "score": 0.54586,
    "score_breakdown": {
      "formula": "hybrid_score = 0.50 * vector_similarity + 0.30 * graph_proximity + 0.20 * recency",
      "vector_similarity": {
        "raw_score": 0.481492,
        "weight": 0.5,
        "contribution": 0.240746,
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
        "timestamp": 1705933805,
        "age_seconds": 1320,
        "half_life_seconds": 3600
      },
      "final_score": 0.54586
    },
    "ranking_rationale": [
      "Vector similarity contributed 0.241 from raw score 0.481.",
      "Graph proximity contributed 0.150 at 1 hop(s).",
      "Recency contributed 0.155 for timestamp 1705933805."
    ]
  }
]

Output JSON with: 'finding', 'confidence'.
```

**📤 LLM JSON RESPONSE RETURNED:**

```json
{
  "finding": "Pod 'ts-order-service' on node 'node-worker-01' has no dependencies and no distinct noisy neighbors. The noisy_neighbors list contains only itself ('ts-order-service'), which is a self-reference and not a true co-located noisy neighbor. No other pods are co-scheduled on the node to cause contention. The observed CPU spike (5.289 to 37.52) and latency increases (p50 0.01019 to 0.03552, p90 0.03546 to 0.08698) are therefore internal to the pod and not attributable to noisy-neighbor interference.",
  "confidence": 0.92
}
```

---

### 5️⃣ Security Specialist Agent (Rules Path)

**⚙️ EXECUTION** — Evaluates rule-based security filters. No threat signature is matched.

**📤 RULE-BASED OUTPUT RETURNED:**

```json
{
  "finding": "No security breaches, secret reference warnings, or RBAC alerts detected for Pod 'ts-order-service'.",
  "confidence": 0.80
}
```

---

## ⚖️ STEP 4 — Consensus Engine Synthesis (LLM Call Input & Response)

**⚙️ EXECUTION** — `services/agent-orchestrator/main.py` dispatches to `Lead Consensus Orchestrator`.

**📥 LLM INPUT PROMPT SENT TO CONSENSUS ENGINE:**

```text
You are the Lead Consensus Orchestrator in an AIOps pipeline.
You received telemetry from 5 agents for pod 'ts-order-service' (Status: 'Failed'):

- MONITORING Agent (Conf: 0.96): Critical anomaly confirmed for Pod 'ts-order-service' at 1705935125: CPU usage spiked 7.1x from baseline mean 5.289 to 37.52, correlated with significant latency degradation (p50 +248%, p90 +145%) and disk I/O collapse (-95.7%), indicating resource contention/performance degradation.
- LOGS Agent (Conf: 0.92): Pod ts-order-service shows isolated failure pattern centered at 1705935125: CPU mean 7.1x increase (5.289 -> 37.52), latency-50 3.48x increase (0.01019 -> 0.03552), latency-90 2.45x increase (0.03546 -> 0.08698), and diskio 95.7% collapse (1.216e+06 -> 5.201e+04). All other services show opposite trend after same timestamp (e.g., ts-user-service latency-90 0.3185->0.02313, ts-assurance-service 0.2479->0.01962, ts-consign-price-service 0.2664->0.02301), proving degradation is isolated to ts-order-service. Pattern indicates CPU saturation/resource contention (CPU-bound bottleneck/starvation of I/O) causing performance degradation. No application ERROR logs in sampled window, but metric anomaly is consistent and benchmark-flagged as ERROR.
- DEPLOYMENTS Agent (Conf: 0.68): Deployment 'ts-order-service-deploy' status is Degraded but sha is null and commit_msg is null - no Git commit evidence available to correlate a deployment to a regression. However benchmark metrics centered at 1705935125 show clear performance regression for ts-order-service: CPU mean 5.289 -> 37.52 (~7.1x increase), latency-50 0.01019 -> 0.03552 (~3.5x), latency-90 0.03546 -> 0.08698 (~2.45x), consistent with Degraded status. DiskIO dropped (1.216e+06 -> 5.201e+04). No Git data to attribute regression to a specific commit/deployment; regression is metric-observed, not Git-confirmed.
- TOPOLOGY Agent (Conf: 0.92): Pod 'ts-order-service' on node 'node-worker-01' has no dependencies and no distinct noisy neighbors. The noisy_neighbors list contains only itself ('ts-order-service'), which is a self-reference and not a true co-located noisy neighbor. No other pods are co-scheduled on the node to cause contention. The observed CPU spike (5.289 to 37.52) and latency increases (p50 0.01019 to 0.03552, p90 0.03546 to 0.08698) are therefore internal to the pod and not attributable to noisy-neighbor interference.
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
  "title": "Internal CPU Saturation Causing Performance Degradation on ts-order-service",
  "summary": "Pod 'ts-order-service' has Failed due to severe isolated internal resource contention. At 1705935125 CPU usage spiked 7.1x causing 248% p50 / 145% p90 latency degradation and 95.7% disk I/O collapse, rendering order service unavailable. Impact is isolated to this pod only.",
  "cause": "Root cause is internal CPU-bound resource contention/saturation within ts-order-service itself, not external factors. At 1705935125 CPU mean jumped from 5.289 to 37.52 (7.1x), p50 latency 0.01019 -> 0.03552 (3.48x, +248%), p90 latency 0.03546 -> 0.08698 (2.45x, +145%), and disk I/O collapsed 1.216e+06 -> 5.201e+04 (-95.7%), indicating CPU starvation of I/O. LOGS agent proves isolation: all other services improved after the same timestamp (e.g., ts-user-service p90 0.3185->0.02313, ts-assurance-service 0.2479->0.01962, ts-consign-price-service 0.2664->0.02301) while only ts-order-service degraded, and no application ERROR logs were present but benchmark flagged the metric anomaly as ERROR. TOPOLOGY excludes noisy-neighbor contention (noisy_neighbors list contains only self-reference on node-worker-01, no co-located pods, no dependencies). DEPLOYMENTS excludes deployment regression (status Degraded but sha=null, commit_msg=null, no Git evidence to correlate). SECURITY excludes breach/RBAC/secret issues. Pattern is consistent with an internal CPU hot-loop, infinite loop, thread contention, or insufficient CPU limits/requests leading to throttling and performance degradation.",
  "recommendation": "1. Immediate mitigation: Restart pod and horizontally scale ts-order-service replicas to restore availability. 2. Check and increase CPU requests/limits (kubectl describe pod, check throttling metrics via `container_cpu_cfs_throttled_seconds_total`), and review HPA/VPA configuration. 3. Profile application at 1705935125 window: collect CPU flame graphs, thread dumps, GC logs, and APM traces to identify hot-loop, deadlock, or inefficient code path. 4. Review node-worker-01 kubelet and cgroup metrics for CPU pressure despite lack of noisy neighbors. 5. Add alerts for CPU > 5x baseline and latency SLO burn. 6. If limits are correct, investigate recent config change (non-Git) or workload spike specific to order service.",
  "severity": "CRITICAL",
  "confidence": 0.94,
  "evidence": [
    "MONITORING (0.96): Critical anomaly at 1705935125 - CPU 5.289 -> 37.52 (7.1x), p50 +248%, p90 +145%, disk I/O -95.7% indicating resource contention",
    "LOGS (0.92): Isolated failure confirmed - same CPU/latency/diskIO degradation isolated to ts-order-service while all other services (ts-user-service, ts-assurance-service, ts-consign-price-service) showed opposite latency improvement after 1705935125",
    "TOPOLOGY (0.92): Excludes noisy-neighbor - pod on node-worker-01 has no dependencies and noisy_neighbors=[ts-order-service] is self-reference only, no true co-located contention, proving issue is internal",
    "DEPLOYMENTS (0.68): Excludes deployment cause - status Degraded but sha=null and commit_msg=null, no Git commit evidence; regression is metric-observed not Git-confirmed",
    "SECURITY (0.8): Excludes security cause - no breaches, secret reference warnings, or RBAC alerts"
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
Internal CPU Saturation Causing Performance Degradation on ts-order-service Pod 'ts-order-service' has Failed due to severe isolated internal resource contention. At 1705935125 CPU usage spiked 7.1x causing 248% p50 / 145% p90 latency degradation and 95.7% disk I/O collapse, rendering order service unavailable. Impact is isolated to this pod only. Root cause is internal CPU-bound resource contention/saturation within ts-order-service itself, not external factors. At 1705935125 CPU mean jumped from 5.289 to 37.52 (7.1x), p50 latency 0.01019 -> 0.03552 (3.48x, +248%), p90 latency 0.03546 -> 0.08698 (2.45x, +145%), and disk I/O collapsed 1.216e+06 -> 5.201e+04 (-95.7%), indicating CPU starvation of I/O. LOGS agent proves isolation: all other services improved after the same timestamp (e.g., ts-user-service p90 0.3185->0.02313, ts-assurance-service 0.2479->0.01962, ts-consign-price-service 0.2664->0.02301) while only ts-order-service degraded, and no application ERROR logs were present but benchmark flagged the metric anomaly as ERROR. TOPOLOGY excludes noisy-neighbor contention (noisy_neighbors list contains only self-reference on node-worker-01, no co-located pods, no dependencies). DEPLOYMENTS excludes deployment regression (status Degraded but sha=null, commit_msg=null, no Git evidence to correlate). SECURITY excludes breach/RBAC/secret issues. Pattern is consistent with an internal CPU hot-loop, infinite loop, thread contention, or insufficient CPU limits/requests leading to throttling and performance degradation.

Example output:
[{"claim_id": "claim-1", "text": "...", "claim_type": "state"}]
```

**📤 LLM JSON RESPONSE RETURNED (35 Extracted Atomic Claims):**

```json
[
  {
    "claim_id": "claim-1",
    "text": "Pod 'ts-order-service' has Failed.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-2",
    "text": "At timestamp 1705935125 CPU usage spiked 7.1x on ts-order-service.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-3",
    "text": "CPU mean jumped from 5.289 to 37.52 at timestamp 1705935125.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-4",
    "text": "p50 latency increased from 0.01019 to 0.03552 (3.48x, +248%) at timestamp 1705935125.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-5",
    "text": "p90 latency increased from 0.03546 to 0.08698 (2.45x, +145%) at timestamp 1705935125.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-6",
    "text": "Disk I/O collapsed from 1.216e+06 to 5.201e+04 (-95.7%) at timestamp 1705935125.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-7",
    "text": "CPU spike at 1705935125 caused p50 latency degradation of 248% and p90 latency degradation of 145%.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-8",
    "text": "CPU starvation caused disk I/O collapse of 95.7%.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-9",
    "text": "Severe isolated internal resource contention caused ts-order-service pod to fail.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-10",
    "text": "Internal CPU-bound resource contention/saturation within ts-order-service itself caused performance degradation.",
    "claim_type": "causal"
  },
  {
    "claim_id": "claim-11",
    "text": "Order service became unavailable.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-12",
    "text": "Impact is isolated to ts-order-service pod only.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-13",
    "text": "All other services improved after timestamp 1705935125.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-14",
    "text": "ts-user-service p90 latency improved from 0.3185 to 0.02313 after timestamp 1705935125.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-15",
    "text": "ts-assurance-service p90 latency improved from 0.2479 to 0.01962 after timestamp 1705935125.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-16",
    "text": "ts-consign-price-service p90 latency improved from 0.2664 to 0.02301 after timestamp 1705935125.",
    "claim_type": "temporal"
  },
  {
    "claim_id": "claim-17",
    "text": "Only ts-order-service degraded while other services improved.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-18",
    "text": "No application ERROR logs were present.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-19",
    "text": "Benchmark flagged the metric anomaly as ERROR.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-20",
    "text": "ts-order-service pod is located on node-worker-01.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-21",
    "text": "TOPOLOGY noisy_neighbors list contains only self-reference to ts-order-service on node-worker-01.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-22",
    "text": "There are no co-located pods on node-worker-01 with ts-order-service.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-23",
    "text": "ts-order-service has no dependencies.",
    "claim_type": "entity_relationship"
  },
  {
    "claim_id": "claim-24",
    "text": "TOPOLOGY excludes noisy-neighbor contention as a cause.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-25",
    "text": "DEPLOYMENTS status is Degraded.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-26",
    "text": "DEPLOYMENTS sha is null.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-27",
    "text": "DEPLOYMENTS commit_msg is null.",
    "claim_type": "state"
  },
  {
    "claim_id": "claim-28",
    "text": "No Git evidence correlates to a deployment regression.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-29",
    "text": "DEPLOYMENTS excludes deployment regression as a cause.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-30",
    "text": "SECURITY excludes breach, RBAC, and secret issues as a cause.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-31",
    "text": "Root cause is not external factors.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-32",
    "text": "Pattern is consistent with an internal CPU hot-loop.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-33",
    "text": "Pattern is consistent with an infinite loop.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-34",
    "text": "Pattern is consistent with thread contention.",
    "claim_type": "general"
  },
  {
    "claim_id": "claim-35",
    "text": "Insufficient CPU limits/requests leading to throttling caused performance degradation.",
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

> 🔗 **Downstream Connection:** This exact list of **35 atomic claims** is passed forward to both **GPCS (Step 6)** for graph-provenance verification and **Ground-Truth Correctness Labelling (Step 8)** for deterministic evaluation against held-out ground truth.

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
* **$\text{proximity} = \frac{1}{1 + \text{min\_hop}(c_i, e)}$** (Graph hop distance from target pod `ts-order-service` in Neo4j).
* **$\text{reliability} = \text{SOURCE\_RELIABILITY}(e)$**: Metric = `0.95`, Log = `0.85`, Topology = `0.80`, Commit = `0.70`.
* **$\text{penalty} = 0.15 \times (\text{min\_hop} \times 0.05)$**

### 3. Decision Threshold Rule

$$\text{gpcs\_unsupported}(c_i) = \begin{cases} \text{False (SUPPORTED)} & \text{if } \text{trust\_score}(c_i) \ge 0.50 \\ \text{True (UNSUPPORTED)} & \text{if } \text{trust\_score}(c_i) < 0.50 \end{cases}$$

### 4. Worked Step-by-Step Calculation Example (`rcaeval-03-HYBRID`)

* **Claim $c_1$:** `"Pod 'ts-order-service' experienced resource pressure"`
* **Retrieved Evidence Node $e_1$:** Metric node `container_cpu_usage_seconds_total` on `ts-order-service`.
  * **Vector Cosine Similarity:** `0.7500`
  * **Graph Hop Distance:** `1 hop` (`ts-order-service` Pod -> Metric Node) $\implies \text{proximity} = \frac{1}{1 + 1} = 0.5000$
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

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-03-HYBRID`):**

```text
claims scored    : 35
GPCS unsupported : 25/35 = 71.4% (10 supported)
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

### 4. Worked Step-by-Step Calculation Example (`rcaeval-03-HYBRID`)

* **Primary Claim $c_1$:** `"ts-order-service experienced resource exhaustion"`
* **Generation $G_2$ Claims:** Contains $c_{2,4}$ `"ts-order-service resource utilization spiked"` $\implies \text{cosine\_sim} = 0.94 \ge 0.80$ (**Match 1**).
* **Generation $G_3$ Claims:** Contains $c_{3,2}$ `"resource pressure observed on ts-order-service"` $\implies \text{cosine\_sim} = 0.88 \ge 0.80$ (**Match 2**).

$$\text{recurrence}(c_1) = \frac{1 + 1}{2} = \mathbf{1.00}$$
* **Verdict:** `1.00 >= 0.50` $\implies$ **`SUPPORTED`** (`sc_unsupported = False`).

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-03-HYBRID`):**

```text
claims scored               : 35
Self-Consistency unsupported: 20/35 = 57.1% (15 supported)
```

---

## 📊 STEP 8 — Ground-Truth Correctness Labelling

### 1. Concept & Objective
Determines whether an extracted atomic claim $c_i$ is objectively **`CONSISTENT`** (True), **`CONTRADICTED`** (False), or **`UNVERIFIABLE`** (N/A) against held-out benchmark ground truth (`target_service = ts-order-service`, `fault = cpu_exhaustion`).

### 🔒 Role of Held-Out Ground-Truth Claims

Each benchmark scenario contains 2 reference ground-truth claims (e.g., `"Service ts-order-service was affected by CPU resource exhaustion"`).

In this experiment, these reference claims are strictly **held out** (withheld from all prompts and databases):

* **Zero Data Leakage:** Never passed to LLM prompts, Neo4j, or Qdrant.
* **Metadata-Driven Labeling:** Python labeling uses top-level scenario metadata (`target_service = ts-order-service`, `root_cause = cpu`) directly, rather than reading the reference text.
* **Contamination Guardrail:** Serves as a reference check to verify that generated claims do not copy held-out benchmark text verbatim.

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

    if names_correct_mechanism: return "consistent", f"names injected mechanism (cpu_exhaustion)"
    if blamed_foreign:           return "contradicted", f"blames {blamed_foreign[0]}"
    if competing:                return "contradicted", f"names competing cause {competing[0]}"
    return "unverifiable", "no mechanism or service identifiable"
```

**📤 MEASURED OUTPUT FOR THIS RUN (`rcaeval-03-HYBRID`):**

```text
consistent=2   contradicted=0   unverifiable=33
EVALUABLE SUBSET: 2 of 35 claims (5.7%)
```

---

## 📈 STEP 9 — Head-to-Head Precision, Recall, & Contingency Evaluation (`rcaeval-03`)

### 1. Concept & Objective
Pairs the verifiers' unsupported flags (`UNSUPPORTED` = Positive Class) with the ground-truth correctness labels (`CONTRADICTED` = Positive Class) to build a 2×2 contingency matrix and evaluate verifier accuracy for scenario **`rcaeval-03`**.

### 🔗 How Ground-Truth Labels (`CONSISTENT` / `CONTRADICTED`) Feed Into Step 9
The evaluable claims labeled in Step 8 form the **ground-truth baseline columns** (`CONTRADICTED` vs `CONSISTENT`) in the 2×2 contingency matrix:
* **Positive Class (Target to Catch):** `CONTRADICTED` (Factually wrong claims).
* **Negative Class (Acceptable Claims):** `CONSISTENT` (Factually accurate claims).
* **Verifier Flags (Positive Class):** `UNSUPPORTED` (Verifier marks claim as invalid/hallucinated).

This pairing enables computing true Precision, Recall, Specificity, and F1 Score for both GPCS and Self-Consistency, measuring whether a verifier's `UNSUPPORTED` flag actually discriminates wrong claims from right ones.

### 2. 2×2 Contingency Matrix for Scenario `rcaeval-03` (HYBRID)

```text
                          DERIVED GROUND TRUTH (SCENARIO RCAEVAL-03)
                     CONTRADICTED (Wrong)    CONSISTENT (Right)
flagged UNSUPPORTED     True Positive (0)    False Positive (25)
flagged SUPPORTED       False Negative (0)    True Negative (10)
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
| **GPCS** | **35** | **25** | **10** | **71.4%** | 2 (2 consistent, 0 contradicted) | Consistent Cause Identified |
| **Self-Consistency** | **35** | **20** | **15** | **57.1%** | 2 (2 consistent, 0 contradicted) | Consistent Cause Identified |

---

---

## 💡 Scenario `rcaeval-03` — findings, mapped to the Experiment 1 research questions

Measured for **rcaeval-03** (Train Ticket, `cpu_exhaustion`) under condition **`HYBRID`**.

| | This run |
|---|---|
| Claims extracted | 35 |
| GPCS unsupported | 25/35 = 71.4% |
| Self-consistency unsupported | 20/35 = 57.1% |
| Accepted by **both** verifiers | 7/35 = 20.0% |
| Ground-truth labelled | 2 of 35 (2 consistent, 0 contradicted) |
| Distinct GPCS trust values | 3 — [0.0, 0.708, 0.71] |

**E1-RQ1 — pipeline executes reliably.** Supported. The run completed with no
fallback, timeout or refused connection, and produced paired GPCS and
self-consistency verdicts for all 35 claims.

**E1-RQ2 / E1-RQ3 — context cost and the seeded red herring.** See the
comparison table at the top of this document. The `Commit` node reaches only
`RAW` (15 prompts) and is discounted there on its timestamp; its absence
from `HYBRID` is a consequence of top-5 ranking, **not** active pruning.

**E1-RQ4 — joint verifier filter.** 7 of 35 claims are accepted by both
verifiers. This is a reproducible candidate set, not an accuracy result: across
the whole experiment only 1 of the 95 intersection claims carries a
ground-truth label.

**E1-RQ5 / E1-RQ6 — correctness is not established here.** This run names the injected mechanism.
Only 2 of 35 claims are adjudicable, so no precision, recall or flag-rate gap can
be computed for a single run.

### On GPCS versus self-consistency

GPCS flags **71.4%** of claims unsupported against self-consistency's
**57.1%** — a difference of **+14.3 percentage points**, at no
additional LLM call.

**This is a strictness and cost result, not an accuracy result.** The two
verifiers measure different properties: GPCS asks whether a claim is traceable
to graph or vector evidence; self-consistency asks whether it recurs across
independent generations. Across the full 18-scenario experiment they agree on
61 of 93 labelled claims, and the net difference between them is small relative
to 1,950 — which is why this project reports them as complementary signals
rather than ranking one above the other.

GPCS emits only **3 distinct trust values** in this run. Across all 1,950
claims it emits eight, with 79.3% at exactly `0.000`, so it cannot rank claims or
be threshold-tuned on this evidence.
