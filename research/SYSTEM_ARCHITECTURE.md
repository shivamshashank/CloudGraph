# SYSTEM_ARCHITECTURE.md

## Research Architecture for CloudGraph v2 (Research Track)

This document specifies the target architecture once CloudGraph is repositioned as a research testbed. It reuses existing modules wherever possible and adds only the components required to make the five contributions in `NOVEL_CONTRIBUTIONS.md` testable.

---

## 1. System diagram

```text
                              ┌─────────────────────────────┐
                              │   Incident Benchmark Suite    │
                              │  (scaled, category-stratified,│
                              │   held-out split for GCP/GPCS │
                              │   calibration)                │
                              └──────────────┬───────────────┘
                                              │ ground truth + queries
                                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        RETRIEVAL POLICY LAYER (NEW)                     │
│  Chooses among: keyword | vector | graph | hybrid | raw-long-context     │
│  Fixed-per-run in Phase 1 (ablation control); adaptive/learned Phase 3   │
└───────────┬───────────────────┬───────────────────┬─────────────────────┘
            ▼                   ▼                   ▼
 ┌───────────────────┐ ┌────────────────────┐ ┌────────────────────────┐
 │ SemanticVectorStore │ │ GraphTraversalRetriever│ │ Raw-context assembler  │
 │ (existing, Qdrant)   │ │ (existing, Neo4j, temporal window)            │ (NEW control condition)│
 └──────────┬──────────┘ └──────────┬─────────┘ └────────────┬────────────┘
            └───────────┬───────────┘                        │
                         ▼                                    │
                ┌──────────────────┐                          │
                │   HybridRanker    │◄─────────────────────────┘
                │  (existing)       │
                └────────┬──────────┘
                         ▼
       ┌──────────────────────────────────────────┐
       │      ORCHESTRATION LAYER (existing + NEW)  │
       │  Mode A (existing): 5 independent          │
       │    specialists → static/LLM consensus       │
       │  Mode B (NEW): specialists → 1 round of     │
       │    cross-agent critique → consensus         │
       │  Mode C (control, NEW): single LLM, full     │
       │    evidence, no specialization               │
       │  Mode D (control, NEW): single LLM,          │
       │    self-consistency at matched call count    │
       └───────────────────┬────────────────────────┘
                            ▼
              ┌───────────────────────────┐
              │  GCP (existing + weight-    │
              │  fitting procedure, NEW)    │
              └──────────────┬─────────────┘
                              ▼
              ┌───────────────────────────┐
              │  GPCS (existing) +          │
              │  Self-Consistency baseline  │
              │  (NEW, per design doc)      │
              └──────────────┬─────────────┘
                              ▼
       ┌────────────────────────────────────────┐
       │        EVALUATION HARNESS (NEW)          │
       │ Runs all Mode/Method combinations over    │
       │ the full dataset; computes accuracy,      │
       │ F1, hallucination rate, calibration       │
       │ (Brier, reliability), latency, and         │
       │ significance tests (paired bootstrap,      │
       │ Wilcoxon)                                  │
       └────────────────────────────────────────┘
```

## 2. Module-by-module research rationale

| Module | Status | Research purpose |
|---|---|---|
| `SemanticVectorStore`, `GraphTraversalRetriever`, `HybridRanker` | Existing, unmodified | Provide the retrieval conditions needed for the neuro-symbolic ablation (Contribution 3) and the raw-context control (RQ6) |
| Retrieval Policy Layer | **New** | Fixed selector in Phase 1 (so each condition is a controlled arm); becomes the object of study for RQ7 (adaptive retrieval) in a later phase |
| Raw-context assembler | **New, small** | Cheapest possible control condition: dump all evidence for the incident window into the LLM context with no graph/vector structuring, to test whether structure earns its complexity (RQ6) |
| Orchestration Mode A | Existing | The current system; retained unmodified as the primary "treatment" condition being explained |
| Orchestration Mode B (cross-agent critique) | **New** | Required for RQ4 / Contribution 5 — the only mode with genuine agent interaction |
| Orchestration Mode C (single LLM, all evidence) | **New, small** | Matched-evidence control for RQ3 |
| Orchestration Mode D (self-consistency ensemble) | **New, small** | Matched-compute control for RQ3/RQ5 — reuses `call_llm` at higher temperature, no new infra |
| GCP + weight-fitting | Existing algorithm, **new fitting procedure** | Required for Contribution 4; fitting is a small supervised step (logistic regression or grid search over `EDGE_WEIGHTS`/`decay_factor` against labeled root causes) |
| GPCS + self-consistency baseline | Existing algorithm, **new baseline** | Required for Contribution 2 / RQ1; the design doc (`HALLUCINATION_SCORING_DESIGN.md`) already specifies this exactly, it only needs implementing |
| Evaluation Harness | **New, highest priority** | Replaces the simulated benchmark; the single blocking deliverable for every other line in this table |

## 3. Data flow for a single experimental run

1. Evaluation harness selects an incident scenario and a fixed condition (retrieval method × orchestration mode × GCP-weights-variant × GPCS-vs-self-consistency).
2. Retrieval Policy Layer invokes the specified retriever(s); results pass through `HybridRanker` (or bypass it for keyword/vector-only conditions, matching current behavior).
3. Orchestration Layer runs the specified mode over the retrieved evidence, producing a draft RCA (`title`, `cause`, `recommendation`, `evidence`).
4. GCP assigns/propagates confidence over the local subgraph using the run's weight variant.
5. GPCS (or the self-consistency baseline) scores claims extracted from the RCA text; both are run in every condition so their outputs can be directly compared per incident, not just in aggregate.
6. Evaluation harness records: accuracy vs. ground truth, precision/recall/F1 over evidence retrieval, unsupported-claim rate (both methods), GCP confidence + correctness (for calibration), wall-clock latency, and LLM call count (for compute-matching).
7. After all incidents × conditions have run, the harness computes paired statistical tests between conditions (same incidents, different treatment) rather than independent-sample tests, since incidents are shared across conditions.

## 4. Why this design and not a rewrite

Every "new" component above is additive and small (a control condition, a baseline, a fitting step, a harness) — nothing requires discarding or re-architecting the existing retrieval, GCP, or GPCS code, all of which are already correct, tested, and structurally sound. This keeps the implementation roadmap realistic within a dissertation timeline while directly targeting the five contributions and the Tier-1 research questions.

## 5. Literature mapping summary (condensed; full mapping per contribution is in `NOVEL_CONTRIBUTIONS.md`)

| Component | Closest prior work | How CloudGraph's version differs |
|---|---|---|
| Graph retrieval | Edge et al. 2024 (GraphRAG) | Temporal/operational graph, not static document corpus |
| Hallucination detection | Self-consistency (repeated sampling + agreement) | Evidence-graph-grounded scoring with explicit path-length penalty, run head-to-head against self-consistency rather than replacing it unverified |
| Multi-agent orchestration | Guo et al. 2024 survey (LLM multi-agent systems) | Adds a matched-compute self-consistency control, which most multi-agent papers omit |
| Confidence propagation | Probabilistic soft logic / Markov Logic Networks; Noisy-OR evidence combination (classical Bayesian networks) | Applied to live infrastructure graphs with a decay-weighted, depth-bounded BFS variant, with (new) data-fit weights instead of hand-set ones |
| RCA for cloud-native systems | MetaRCA (Liang et al. 2026), agentic structured graph traversal (Cui et al. 2025) | Direct competitors; CloudGraph must be benchmarked against these (or their reported results) before submission — see `PUBLICATION_STRATEGY.md` |
