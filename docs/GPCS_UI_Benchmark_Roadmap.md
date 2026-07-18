# GPCS + UI + Benchmarking Roadmap

## Purpose

This document defines a production-ready, research-oriented roadmap for:

- implementing Graph-Provenance Claim Scoring (GPCS)
- building UI surfaces for investigation, claim provenance, and benchmark comparison
- supporting evaluation, baseline comparison, and publication-quality results

This roadmap is intended for a journal submission and for a polished demo/UI-driven platform.

---

## 1. Objectives

1. Implement a research-grade GPCS module that assigns trust scores to RCA claims.
2. Expose GPCS evidence and unsupported-claim metrics in the API and UI.
3. Build benchmarking dashboards for baseline comparisons and research evaluation.
4. Make the UI and docs a coherent product: explainable incident investigation + reproducible evaluation.

---

## 2. High-level architecture

### Core components

- `services/api/app/research/gpcs.py` — GPCS implementation
- `services/api/app/main.py` — investigation trigger and claim scoring integration
- `services/api/app/retrieval/*` — GraphRAG retrieval and semantic search
- `services/ui/static/*` — UI pages and JavaScript for evidence display and benchmarking
- `services/api/app/database/redis_client.py` — optional caching for search and evaluation

### Research flow

1. Trigger incident investigation
2. Generate RCA text via orchestrator/agents
3. Extract atomic claims from RCA text
4. Retrieve supporting evidence for each claim
5. Score each claim using graph-provenance trust scoring
6. Produce `unsupported_claim_rate` and per-claim provenance data
7. Render results in the UI and export benchmark results

---

## 3. GPCS implementation plan

### 3.1 Claim extraction

- Extract atomic, verifiable claims from generated RCA text.
- Prefer structured output if an LLM is available; otherwise use a deterministic parser.
- Classify claim type: `temporal`, `causal`, `entity_relationship`, `state`, `general`.
- Store `claim_id`, `text`, `type`.

### 3.2 Evidence alignment

- Reuse existing GraphRAG vector search and graph retrieval.
- For each claim:
  - run semantic search on the claim text
  - run graph-driven retrieval from named entities if present
  - merge candidate evidence from both sources

### Current implementation status

- [x] Claim extraction and claim-type classification exist in `services/api/app/research/gpcs.py`
- [x] Semantic retrieval is performed through hybrid GraphRAG search
- [x] Graph retrieval is included via hybrid GraphRAG scoring
- [x] Evidence merging is currently handled by the GraphRAG hybrid result set
- [x] Trust scoring is implemented with semantic similarity, graph proximity, source reliability, and path-length penalty
- [x] API output includes `unsupported_claim_rate`, `claim_count`, and per-claim support details
- [x] UI highlighting for unsupported claims is implemented in `services/ui/static/diagnosis.js` and `style.css`
- [x] LLM Context Explorer backend endpoint and UI tab are implemented

### 3.3 Trust scoring

- Compute a trust score for each claim using a weighted formula:
  - semantic similarity
  - graph proximity (hop distance)
  - source reliability by evidence type
  - path-length penalty
- Calibrate a threshold on a held-out dataset split.
- Label claims below threshold as `unsupported`.

### 3.4 Aggregation and output

- Produce per-RCA metrics:
  - `unsupported_claim_rate`
  - `claim_count`
  - `claims: [{claim_id, text, claim_type, trust_score, unsupported, supporting_evidence}]`
- Expose the output in the investigation API response.
- Save benchmark artifacts as JSON/CSV for later analysis.

---

## 4. Baseline comparison plan

### 4.1 Required baselines

- Keyword search only
- Vector-only RAG
- GraphRAG retrieval
- GraphRAG + agents
- GraphRAG + agents + GCP
- GraphRAG + agents + GCP + GPCS
- Self-consistency hallucination baseline

### 4.2 Metrics

- Precision
- Recall
- F1 score
- Top-1 / top-3 RCA accuracy
- Unsupported claim rate
- MTTR proxy
- Explanation completeness
- Per-claim-type error rates

### 4.3 Experiment outputs

- Benchmark summary tables
- Baseline comparison charts
- Per-category breakdown
- Self-consistency vs GPCS comparison
- Export CSV and JSON files for publication

---

## 5. UI design requirements

### 5.1 Investigation dashboard

- Incident selector / list
- RCA result card showing title, cause, recommendation, severity
- Evidence chain summary panel
- Claim provenance panel with:
  - claim text
  - trust score
  - unsupported status highlight
  - supporting evidence snippets
- GraphRAG context summary for the incident

### 5.2 Claim provenance UI

- Display claim type badge (`temporal`, `causal`, etc.)
- Show supporting evidence as clickable items
- Visually highlight unsupported claims in red or warning state
- Show overall `unsupported_claim_rate`
- Show counts by claim type and support status

### 5.3 Benchmark / comparison dashboard

- Baseline comparison table with metrics
- Charts for accuracy, hallucination rate, MTTR proxy
- Filter by incident category and claim type
- Comparison rows for:
  - GraphRAG
  - GraphRAG + agents
  - GraphRAG + agents + GCP
  - GraphRAG + agents + GCP + GPCS
- Self-consistency comparison panel

### 5.4 Research-oriented UI

- Export buttons for CSV/JSON
- Dataset split status and held-out evaluation summary
- Experimental notes section for publication documentation
- Clear labels: `Research evaluation`, `Model comparison`, `Support evidence`

---

## 6. Product-ready engineering checklist

- [ ] Add GPCS integration tests (`services/api/tests/test_gpcs.py`)
- [ ] Add API tests for investigation output schema and claim provenance
- [ ] Add UI test coverage or manual validation checklist for new screens
- [x] Add UI routing for benchmark/comparison pages
- [ ] Add prompt/files versioning and document them in source control
- [ ] Secure API authentication and lock down CORS for production
- [ ] Add logging for research experiment runs and result exports

---

## 7. Recommended file and UI structure

### Proposed new docs

- `docs/GPCS_UI_Benchmark_Roadmap.md` — this file
- `docs/week-4/README.md` — update with GPCS and benchmark summary
- `docs/week-1/research-methodology.md` — include final evaluation schema

### Proposed UI files

- `services/ui/static/gpcs.html` — claim provenance dashboard
- `services/ui/static/benchmark.html` — baseline comparison dashboard
- `services/ui/static/app.js` — client code to fetch investigation and benchmark APIs
- `services/ui/main.py` — serve the new pages and API routes if not already exposed

---

## 8. Remaining checklist items from `CloudGraph_3_Week_97-99_Checklist.md`

### Already done

- [x] End-to-end deployment works
- [x] Neo4j + Qdrant integrated
- [x] GraphRAG retrieval operational
- [x] Multi-agent orchestration complete
- [x] RCA report generation complete
- [x] Graph Confidence Propagation (GCP) design, scores, and UI

### Still left to implement

- [x] Complete the end-to-end GraphRAG + Multi-Agent pipeline in a research-grade way
- [x] Introduce Graph-Provenance Claim Scoring (GPCS) as a completed algorithm
- [x] Add the LLM Context Explorer UI and backend comparison endpoint
- [ ] Build or collect a 60–80 balanced incident dataset with ground truth labels
- [ ] Execute the full ablation study
- [ ] Run human evaluation with 3–5 reviewers
- [ ] Perform statistical analysis with confidence intervals and effect sizes
- [ ] Complete dissertation chapters aligned to RQ1–RQ4

### GPCS-specific implementation tasks

- [x] Extract atomic claims from RCA outputs
- [x] Classify claims by type (`Temporal`, `Causal`, `State`, `Relationship`)
- [x] Align each claim with semantic and graph evidence
- [x] Merge evidence sources for claim support
- [x] Compute trust scores with semantic similarity, graph proximity, source reliability, and path-length penalty
- [x] Expose unsupported claim rate, claim confidence, and evidence path in the API
- [x] Highlight unsupported claims in the UI

### Baselines still missing

- [ ] Keyword Search
- [ ] Vector RAG
- [ ] GraphRAG
- [ ] GraphRAG + Agents
- [ ] GraphRAG + Agents + GCP
- [ ] GraphRAG + Agents + GCP + GPCS
- [ ] Self-consistency hallucination baseline comparison

### UI / benchmarking tasks still missing

- [x] Backend endpoint `/api/v1/investigations/context-comparison`
- [x] UI Context Explorer tab inside AI Diagnosis page
- [x] 4-way comparison toggles for raw logs, metrics, prompts, and evidence
- [x] Baseline comparison dashboard with charts and filters
- [x] Export buttons for CSV/JSON benchmark results
- [x] Research experiment notes and dataset split summary

### Week 3 evaluation tasks still missing

- [ ] 60–80 incident benchmark dataset
- [ ] Balanced categories with ground truth labels
- [ ] Ablation: remove GraphRAG, Agents, GCP, GPCS
- [ ] Metrics: accuracy, precision, recall, F1, MTTR reduction, hallucination rate, latency
- [ ] Human evaluation: usefulness, trustworthiness, explainability, inter-rater agreement
- [ ] Statistical evidence: confidence intervals, effect size, significance tests
- [ ] Dissertation sections: methodology, algorithm design, experimental setup, results, threats to validity, limitations, future work

---

## 9. Next steps

1. Implement the improved GPCS engine in `services/api/app/research/gpcs.py`.
2. Add API responses for claim provenance and benchmarking data.
3. Add UI pages for investigation results and benchmark comparison.
4. Build the dataset + evaluation pipeline for journal-quality metrics.
5. Update this roadmap and the dissertation docs with actual results.
