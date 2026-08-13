# Week 1 – Week 8 Progress Checklist

Every ticked box below is backed by a commit hash or a file path that exists
in this repository. Boxes are left unticked where the item appeared in the
project's original 8-week roadmap but was not actually delivered — those are
not failures to hide, they are the scope boundary of what this dissertation
can claim. (That roadmap, and the per-week deliverable packs it produced, were
removed in the 2026-08-11 consolidation once their content had been absorbed
here; both remain in git history.)

- Source of truth: `git log` (first commit `df48078`, 2026-06-09; this log's
  cutoff `5d89c81`, 2026-08-11), cross-checked against
  [`docs/project/STATUS.md`](../docs/project/STATUS.md).
- Real elapsed time was **nine** weeks, not eight. Week 9 is included below
  because the corrected evaluation — the only evaluation whose numbers are
  citable — happened there. Compressing it into "Week 8" would misreport the
  project.

**Legend** — `[x]` delivered and verifiable · `[~]` delivered but later
replaced or superseded · `[ ]` planned, not delivered.

---

## Summary

| Week | Dates | Theme | Commits in window | Status |
|---|---|---|---|---|
| 1 | 06-09 – 06-15 | Research & system design | 2 | Complete |
| 2 | 06-16 – 06-22 | Infrastructure & observability | 0 in window (5 landed 06-23 – 06-30) | Complete, slipped |
| 3 | 06-23 – 06-29 | Knowledge graph | 4 | Complete |
| 4 | 06-30 – 07-06 | GraphRAG retrieval engine | 22 | Complete |
| 5 | 07-07 – 07-13 | Multi-agent framework | 9 | Complete |
| 6 | 07-14 – 07-20 | GCP & GPCS algorithms | 8 | Complete |
| 7 | 07-21 – 07-27 | Evaluation infrastructure | 2 | Complete (baselines still synthetic) |
| 8 | 07-28 – 08-08 | Real evaluation & statistics | 11 | Complete, results later invalidated |
| 9 | 08-09 – 08-11 | Integrity fixes & corrected run | 4 | Complete — **the citable results** |

---

## Week 1 (2026-06-09 – 2026-06-15) — Research & System Design

**Commits:** `df48078` (06-09), `8e8118f` (06-10).

- [x] Repository initialised with documentation and architecture diagrams — `df48078`
- [x] Research scope and 8-week roadmap defined — `8e8118f`
- [x] Literature review across RAG, GraphRAG, AIOps/RCA, multi-agent LLM systems — [`LITERATURE_REVIEW.md`](LITERATURE_REVIEW.md)
- [x] Research questions RQ1–RQ4 and hypotheses H1–H4 stated — `6fbde78`; definitions and verdicts consolidated into the two tables at the end of this file
- [x] Initial system design: high-level architecture, graph schema, agent roles — `6fbde78`; superseded by [`docs/architecture/`](../docs/architecture/) and [`graph/schema.cypher`](../graph/schema.cypher)
- [x] Open-source data-collection strategy (Prometheus, Loki, OpenTelemetry, Falco, Argo CD, Git webhooks) — `6fbde78`; the shipped ingestion surface is described in [`docs/README.md`](../docs/README.md)
- [x] Reference list compiled — [`REFERENCES.md`](REFERENCES.md)
- [~] AWS deployment plan drawn up — superseded in Week 4 by Helm + kubeadm (`2284e41`)

## Week 2 (2026-06-16 – 2026-06-22) — Infrastructure & Observability

**No commits landed inside this calendar window.** The deliverables packaged
as "Week 2" arrived 06-23 – 06-30: `fcc0b11`, `6fbde78`, `2673643`, `29d6173`,
`97ef50f`. Reported here as it happened rather than back-dated.

- [x] Observability stack manifests — Prometheus, Grafana, Loki, OpenTelemetry Collector — [`deployments/kubernetes/observability/`](../deployments/kubernetes/observability/)
- [x] Sample microservice application with Prometheus scrape annotations and OTel exporters — [`deployments/kubernetes/sample-app/`](../deployments/kubernetes/sample-app/)
- [x] Custom Helm chart for the sample application, `helm lint` clean — [`deployments/helm/sample-app/`](../deployments/helm/sample-app/), `97ef50f`
- [x] Argo CD `Application` CRDs for GitOps — [`deployments/kubernetes/argocd-applications.yaml`](../deployments/kubernetes/argocd-applications.yaml)
- [x] Observability endpoint health test — [`tests/observability/observability_test.go`](../tests/observability/observability_test.go)
- [x] CI/CD pipeline scaffolding — `2673643`, `09ac3d0`
- [~] Terraform modules for AWS EKS (VPC, security groups) — `2673643`, `29d6173`; **never applied against a live AWS account** and removed in `2284e41`
- [ ] Live EKS cluster with IAM/VPC provisioning — not done; the project deploys to kubeadm/Rancher instead, which is what [`docs/guides/INSTALLATION.md`](../docs/guides/INSTALLATION.md) documents

## Week 3 (2026-06-23 – 2026-06-29) — Knowledge Graph Development

**Commits:** `fcc0b11`, `6fbde78`, `2673643`, and the merge pair `4e24ee6` / `fcd25f9` (06-28).

- [x] Neo4j (community + APOC) and Qdrant running locally via compose — [`deployments/helm/cloudgraph/`](../deployments/helm/cloudgraph/)
- [x] Cypher schema: node labels, uniqueness constraints, search indexes — [`graph/schema.cypher`](../graph/schema.cypher)
- [x] Neo4j driver client with lifespan-managed connections — [`services/api/app/database/neo4j_client.py`](../services/api/app/database/neo4j_client.py)
- [x] Prometheus metrics adapter → `(:Pod)-[:GENERATES]->(:Metric)` — [`adapters/prometheus.py`](../services/api/app/adapters/prometheus.py)
- [x] Loki log adapter → `(:Pod)-[:GENERATES]->(:Log)` — [`adapters/loki.py`](../services/api/app/adapters/loki.py)
- [x] Git / Argo CD webhook receiver → `(:Commit)-[:TRIGGERED_BY]->(:Deployment)` — [`adapters/webhooks.py`](../services/api/app/adapters/webhooks.py)
- [x] Graph construction engine: entity linking, dependency mapping — [`adapters/graph_constructor.py`](../services/api/app/adapters/graph_constructor.py)
- [x] FastAPI ingestion endpoints and health probes — [`services/api/app/main.py`](../services/api/app/main.py)
- [x] Schema-integrity and 100 ms traversal-latency tests — [`services/api/tests/test_graph.py`](../services/api/tests/test_graph.py)
- [~] Tempo trace adapter written and wired into `routers/telemetry.py` — but **Tempo was never deployed** in the observability stack, so `CALLS` edges fall back to naming-convention heuristics and no evaluation scenario exercised traces

## Week 4 (2026-06-30 – 2026-07-06) — GraphRAG Retrieval Engine

**Commits (22 — the heaviest infrastructure week):** `fe003d0`, `09ac3d0`,
`2284e41` (07-01); `fb3fa0b`, `e9bb19c`, `b973329` (07-02); `f3bc134`,
`e38c0fa` (07-04); `fc7569b`, `626f2f1`, `f0521d2` (07-05); `84f0d13`,
`f087d19`, `08c2324`, `f0dade5`, `6d3640b`, `8bff5e0` (07-08).

- [x] Backend restructured into `services/api` — `e38c0fa`
- [x] CLI migrated from shell scripts to Go — [`cmd/cloudgraph/`](../cmd/cloudgraph/), `e9bb19c`
- [x] Terraform replaced by Helm charts as the deployment path — `2284e41`
- [x] Local embedding pipeline, `all-MiniLM-L6-v2`, 384-dim, baked into the image (no hosted embedding API) — [`services/embeddings.py`](../services/api/app/services/embeddings.py), `84f0d13`
- [x] Qdrant vector store with a deterministic hashed-file fallback — [`services/semantic_store.py`](../services/api/app/services/semantic_store.py)
- [x] Multi-hop Cypher traversal retriever (1–4 hops, default 2) with an incident-derived time window — [`retrieval/graph_traversal.py`](../services/api/app/retrieval/graph_traversal.py)
- [x] Hybrid ranker `0.50·vector + 0.30·graph_proximity + 0.20·recency`, every result carrying a `score_breakdown` — [`retrieval/hybrid_ranker.py`](../services/api/app/retrieval/hybrid_ranker.py)
- [x] `keyword` / `vector` / `hybrid` selectable on one `method` parameter of `/api/v1/graphrag/search`
- [x] Kubernetes discovery and UI scaffolding — `f3bc134`
- [x] GitLab-tracked branch merged back into primary history — `b973329`

## Week 5 (2026-07-07 – 2026-07-13) — Multi-Agent Framework

**Commits:** `b020537` (07-09 — the largest single commit of the project),
`a7f635c`, `c6829e3` (07-10).

- [x] Five specialist agents implemented — **Monitoring, Log, Deployment, Topology, Security** — [`services/investigation-engine/main.py`](../services/investigation-engine/main.py)
- [x] Deterministic rule-based fallback per agent when no LLM provider is connected
- [x] `ConsensusEngine` aggregating agent findings into one report (title, cause, recommendation, severity, evidence) — [`services/agent-orchestrator/main.py`](../services/agent-orchestrator/main.py)
- [x] Incident-investigation UI workbench wired to live endpoints — [`services/ui/static/diagnosis.html`](../services/ui/static/diagnosis.html)
- [~] Authentication layer added, then removed the same week — `a7f635c`; the system is no-auth by default today
- [ ] Trace Agent and a separate Root Cause Agent, as drafted in the Week 1 design — never built. The Week 1 literature review lists seven agent roles; five exist. Topology took the place of Trace, and consensus is a static aggregation rather than a reasoning agent.

## Week 6 (2026-07-14 – 2026-07-20) — RCA Algorithms (GCP & GPCS)

**Commits:** `af76db4` (07-15), `42af387` (07-17), `e54894a`, `f80f914`,
`d1e9945` (07-18), `6eefca9`, `433de75`, `615d452` (07-19).

- [x] **Graph Confidence Propagation (GCP)** — Noisy-OR belief propagation over the topology with hop-decay — [`research/gcp.py`](../services/api/app/research/gcp.py), [`docs/design/GCP_DESIGN.md`](../docs/design/GCP_DESIGN.md), `af76db4`
- [x] **Graph-Provenance Claim Scoring (GPCS)** — the project's central contribution: claim extraction, graph-grounded evidence retrieval, trust score — [`research/gpcs.py`](../services/api/app/research/gpcs.py), [`docs/design/GPCS_DESIGN.md`](../docs/design/GPCS_DESIGN.md), `f80f914`
- [x] Incident CRUD endpoints and expanded observability integration — `6eefca9`
- [x] First benchmark-comparison UI — `f80f914`
- [ ] Calibration of GPCS thresholds on held-out data — **not done.** The 0.30 evidence floor and 0.50 trust cut are fixed defaults set by inspecting live score distributions. Both design documents were corrected in the Week 9 documentation pass to stop describing them as calibrated.
- [ ] GCP output validated as a probability — not done; it is a bounded score, not a calibrated probability

## Week 7 (2026-07-21 – 2026-07-27) — Evaluation Infrastructure

**Commits:** `c19ea09` (07-22), `b3fb5f6` (07-25).

- [~] Dynamic 6-baseline benchmark engine and UI (Keyword / Vector / GraphRAG / +Agents / +GCP / +GPCS) — [`routers/benchmark.py`](../services/api/app/routers/benchmark.py), `c19ea09`. Built and retained, but **hidden from the UI in the final release** and deferred: it emits point estimates with no CIs and confounds compute with architecture, so it is not citable. No published result came from it.
- [x] Cluster-metrics UI panel — `c19ea09`
- [x] Redis removed from the Helm chart as an unneeded dependency — `c19ea09`
- [x] Stale documentation and checklists purged — `b3fb5f6`
- [ ] Baselines invoking the real pipeline — **not this week.** The six baselines computed scores from fabricated heuristic offsets (`_calc_kw`, `_calc_vector`, …). Replacing them with genuine pipeline invocations was Week 8's work. Nothing produced in Week 7 is a measurement.

## Week 8 (2026-07-28 – 2026-08-08) — Real Evaluation & Statistical Rigour

**Commits:** `4844d0c` (07-31); `5dcc05f`, `afc733f` (08-01); `88f81a5`
(08-03); `959922f`, `cf5e1d2` (08-05); `dfdbd11`, `d6ab4ee` (08-06);
`6be53d8` (08-07); `277e82f`, `9d1d16a` (08-08).

This ran past the nominal 8-week boundary. Three phases:

**Phase A — LLM integration**

- [x] Per-request LLM provider settings rather than an environment variable — `4844d0c`, `dfdbd11`
- [x] Real credentials threaded into GPCS; orchestrator crash-loop fixed; full LLM request/response logging added — `6be53d8`
- [~] Fully local Ollama-only integration, including a `cloudgraph deploy llm` CLI command and an in-cluster Ollama deployment — `88f81a5`; **reverted** within the week (`dfdbd11`, 08-06) after CPU inference latency made it impractical for this workload. A documented design reversal, not a hidden dead end.

**Phase B — real evaluation**

- [x] Every fabricated benchmark heuristic replaced with real pipeline invocations — `5dcc05f`, `959922f`
- [x] Benchmark seeding and evaluation modules — [`app/demo/seeding.py`](../services/api/app/demo/seeding.py), [`research/evaluation.py`](../services/api/app/research/evaluation.py)
- [x] GPCS-vs-self-consistency comparison built (the RQ3 metric) — [`research/self_consistency.py`](../services/api/app/research/self_consistency.py)
- [x] Three-condition retrieval-context ablation: `none` / `raw` / `hybrid`
- [x] Neuro-symbolic retrieval ablation: keyword (symbolic) / vector (neural) / hybrid
- [x] Paired-bootstrap confidence intervals and Wilcoxon signed-rank tests — [`scripts/paired_bootstrap.py`](../services/api/scripts/paired_bootstrap.py)
- [x] Matched-compute control isolating whether five agents beat one LLM at equal sampling cost — [`scripts/run_matched_compute_control.py`](../services/api/scripts/run_matched_compute_control.py)
- [x] Five real bugs found and fixed in GPCS evidence retrieval (truncated entity extraction, an excluded `Deployment` label, a dead semantic-search callback, an unthresholded relevance floor, a `Node`-prefix regex gap)

**Phase C — packaging**

- [x] Result figures generated — [`scripts/make_figures.py`](../services/api/scripts/make_figures.py)
- [x] `testing/` restructured into a numbered, reproducible script suite — `277e82f`
- [x] Every `pylint: disable` suppression in first-party code removed by refactoring rather than silencing
- [x] Documentation tree reorganised into `docs/`, `research/`, `experiments/`, `dissertation/`
- [x] First submission-ready paper drafted — `9d1d16a`

**Results status — do not cite Week 8 numbers.**

- [ ] Valid results from this week — **none.** A benchmark data-leakage defect
      handed every condition the ground-truth answer as its input observation.
      The figures reported at the time (64.0% GPCS/self-consistency agreement;
      44.2% vs 31.5% matched-compute unsupported-claim rate) measured the leak,
      not the system. Both paper drafts built on them are stale. See Week 9.

## Week 9 (2026-08-09 – 2026-08-11) — Integrity Fixes and the Corrected Run

**Commits:** `8da51bc`, `d5611e2` (08-09), `9787fde` (08-10), `5d89c81` (08-11).

Four independent defects were found, each of which had produced confident,
invalid numbers. All four are now pinned by regression tests in
[`tests/test_evaluation_integrity.py`](../services/api/tests/test_evaluation_integrity.py).

- [x] **Ground-truth leakage** — `seeding.py` wrote `ground_truth_claims` into seeded log nodes and Qdrant documents, and `self_consistency.py` set `error_logs = scenario["ground_truth_claims"]` unconditionally across all three context conditions. Fixed: a separate `observed_symptoms` field supplies low-level telemetry that requires inference; `ground_truth_claims` is now held-out scoring reference only.
- [x] **Index-based claim join** — GPCS and self-consistency each ran their own LLM claim extraction and were joined by positional `claim-N` id, so scores were attached to different claims. Fixed: GPCS now scores the *same* segmentation self-consistency scored, and a `gpcs_claim_text` column lets the join be verified row by row.
- [x] **Unearned graph-proximity credit** — a missing path was conflated with hop distance 0, awarding full proximity for no evidence. Fixed: `None` now yields proximity 0.0 and no penalty.
- [x] **Cross-scenario vector contamination** — seeded evidence from other scenarios stayed visible in the shared Qdrant collection. Fixed: every node and document is tagged with `scenario_id`, search filters on it in both the Qdrant and fallback paths, and runs use a dedicated `evidence_eval` collection with an isolation assertion — `9787fde`
- [x] Inert recency signal fixed — timestamps now step back from a per-scenario incident time; measured spread went from 0.000 to 0.251 on real data
- [x] GCP no longer returns a hard-coded `0.80` when Neo4j is unreachable — it raises, and callers report 0.0
- [x] Matched-compute arms genuinely share one retrieval fetch
- [x] Bootstrap corrected to cluster by scenario (36) rather than scenario×condition (108), removing pseudo-replication
- [x] Benchmark migrated from 25 authored scenarios to **36 real RCAEval RE2 cases** (3 systems × 6 fault types × 2 replicates) — [`experiments/DATA_PROVENANCE.md`](../experiments/DATA_PROVENANCE.md)
- [x] Full 36-scenario run completed on one build, zero exclusions, zero contamination — `5d89c81`
- [x] Merge pipeline with SHA-256 manifest and integrity gates that abort on duplicate claims, broken joins, or ground-truth echo — [`scripts/merge_reports.py`](../services/api/scripts/merge_reports.py)
- [x] Findings written up with per-finding evidential status — [`experiments/FINDINGS.html`](../experiments/FINDINGS.html)

**Citable results** (36 scenarios, 3,685 claims, build `9787fde`, digest
`sha256:81c48641`):

| Result | Effect | 95% CI | p |
|---|---|---|---|
| GPCS flags more unsupported claims than self-consistency | +0.119 | [+0.073, +0.163] | <0.0001 |
| Hybrid beats keyword on retrieval recall | +0.190 | [+0.116, +0.269] | 0.0003 |
| Hybrid vs raw context (concordance) | +0.024 | [−0.028, +0.077] | 0.302 (null) |

---

## Research questions — delivered against

| ID | Question | Status |
|---|---|---|
| RQ1 | Can GraphRAG improve RCA accuracy over traditional RAG? | **Partially answered.** Hybrid beats keyword on recall (significant). Vector and hybrid are *identical on every measure*, so the graph adds nothing to retrieval on this benchmark — a negative result, reported as measured. |
| RQ2 | Does multi-agent reasoning improve investigation quality? | **Not answered on valid data.** The matched-compute control ran only under the leaked Week 8 pipeline; it has not been re-run since the fixes. |
| RQ3 | Can knowledge-graph retrieval reduce hallucinations? | **Partially answered.** GPCS flags 70.3% of claims unsupported vs self-consistency's 57.9% (significant). But *stricter is not better-aimed*: on the 4.2% of claims with automatic correctness labels, neither verifier discriminates correct from incorrect (both gaps −0.8 pp). |
| RQ4 | Can GraphRAG investigations reduce MTTR? | **Not attempted.** No timing or human-workflow measurement exists anywhere in the repository. RQ4 should be withdrawn from the dissertation's claims or restated as future work. |

## Hypotheses — delivered against

Stated in Week 1 (`6fbde78`) before any measurement, with the evidence that
would count as support fixed in advance:

| ID | Hypothesis | Evidence that would support it | Verdict |
|---|---|---|---|
| H1 | GraphRAG beats traditional RAG on accuracy | Higher precision, recall, F1, top-k root-cause accuracy | **Unsupported.** Vector ≡ hybrid on every measure. |
| H2 | GraphRAG + multi-agent beats GraphRAG alone | Better hypothesis ranking, fewer missed evidence sources | **Untested on valid data.** |
| H3 | Graph retrieval reduces hallucination rate | Lower unsupported-claim percentage in RCA reports | **Supported for strictness, not for accuracy.** |
| H4 | Confidence-aware voting improves trust | Higher expert or rubric score for remediation usefulness | **Untested.** No human study was run. |

## What is genuinely left

- [ ] Dissertation chapters written — see [`DISSERTATION_OUTLINE.md`](DISSERTATION_OUTLINE.md)
- [ ] Human-labelled correctness on a stratified claim sample — the single most valuable outstanding piece of work, and the only way to settle whether GPCS is better *aimed* rather than merely stricter
- [ ] Matched-compute control re-run on the corrected pipeline (closes RQ2/H2)
- [ ] Calibration analysis — Brier score and reliability diagrams for GCP and GPCS
- [ ] API authentication on `/api/v1/settings` and other routes — a real credential-exposure risk now that settings stores a live provider key
- [ ] RCAEval RE3 (code-level faults) to widen beyond resource and network faults
