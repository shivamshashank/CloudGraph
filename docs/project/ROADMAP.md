# CloudGraph — Dissertation Completion & Future Roadmap

**Goal:** Reach 95+ marks on the current dissertation (v1), then extend the work
toward journal publication and PhD positioning (v2 / v3).

This file is the forward-looking plan. For current implementation status
(what's actually done vs. not, verified against the code), see
`STATUS.md` — that file, not this one, is the source of truth for
"is X built yet."

---

## How to Use This Document

- **v1 (this section)** = everything required to submit a 95+ dissertation.
  Scope is deliberately bounded — no new product features, only evaluation
  rigor, consistency fixes, and writing.
- **v2 (Future Work)** = post-submission hardening needed before any journal
  submission.
- **v3 (Future Work)** = PhD-track extensions: generalization, theory, and
  broader empirical validation.

Do not pull v2/v3 items into v1. Scope creep into v2/v3 territory is the most
common way dissertation time budgets fail.

---

# 🎓 V1 — Dissertation Completion Plan (Target: 95+)

## 1. Evaluation Rigor (Highest Priority — Do This First)

- [x] Replace heuristic benchmark calculators (`_calc_kw`, `_calc_vector`,
      `_calc_graphrag`, `_calc_agents`, `_calc_gcp`, `_calc_gpcs` in
      `routers/benchmark.py`) with **real pipeline invocations** — done;
      `routers/benchmark.py` now calls the real `evaluate_scenario()`
      (`app/research/evaluation.py`) for all 6 baselines, no fabricated
      offsets remain.
- [x] Benchmark dataset — **superseded and improved**: the hand-authored
      set was retired in favour of 36 scenarios derived from real
      chaos-injected failures in RCAEval RE2
      (`app/demo/rcaeval_dataset.py`, `experiments/DATA_PROVENANCE.md`).
- [ ] Implement a **train/held-out split** (e.g. 70/30, as discussed in the
      original evaluation plan but never applied to actual threshold
      calibration). Still not done — GPCS's semantic-evidence
      threshold (`MIN_SEMANTIC_EVIDENCE_SCORE = 0.30` in `gpcs.py`) was
      calibrated ad hoc against real live query examples, not a formal
      held-out split methodology.
- [x] Add **statistical significance testing** — `scripts/paired_bootstrap.py`:
  - [x] Wilcoxon signed-rank test between paired conditions (GPCS vs.
        self-consistency, hybrid vs. raw-context, hybrid vs. keyword
        recall, real 5-agent vs. matched-compute single-LLM).
  - [x] Report p-values alongside raw deltas — implemented in
        `scripts/paired_bootstrap.py`; output pending the re-run.
        (Effect sizes/Cohen's d specifically not added — the paired
        bootstrap CI serves the same role of showing magnitude +
        uncertainty together.)
  - [x] Bootstrap confidence intervals (10000 resamples, seeded) on every
        headline delta.
- [x] Implement the **GPCS self-consistency baseline** (explicitly marked "not
      optional" in `docs/design/GPCS_DESIGN.md`) — code complete in
      `app/research/self_consistency.py`, unit-tested
      (`tests/test_self_consistency.py`):
  - [x] Generate N RCA outputs per incident at higher temperature
        (`generate_and_score(scenario, n_samples, temperature)`).
  - [x] Extract claims from each generation using the existing
        `GraphProvenanceClaimScorer.extract_claims` (identical extractor GPCS
        uses, so the comparison is fair by construction).
  - [x] Flag claims as unsupported if they don't recur consistently across
        generations (cosine similarity ≥ 0.8 recurrence check).
  - [x] **Produce the actual comparison table with real data** — done. Run
        via `cloudgraph report` (batched, `--limit`/`--offset`, merged with
        `scripts/merge_reports.py`) against Meta's Llama API — the old
        `scripts/run_day2_self_consistency.py` reference above no longer
        exists; `scripts/generate_research_report.py` (local-checkout path,
        wrapped by `testing/report/run_report_batched.sh`) or `cloudgraph
        report` (primary, no-checkout path) are the current entry points.
        An initial run produced real data but was invalidated by a
        ground-truth leak (`dissertation/PROGRESS.md`, Week 9); the
        comparison table is pending a re-run on the corrected pipeline.
- [ ] Calibrate the GPCS `threshold` value on the held-out split — not done,
      see the train/held-out split item above (the same gap).
- [x] Report hallucination rate **broken down by claim type** —
      implemented in `report_runner.py` (agreement cross-tab) and
      `scripts/make_figures.py`; output pending the re-run. (Breakdown by
      incident *category* specifically, as opposed to claim type, not
      separately produced.)

## 2. Minimal Human Evaluation (High Impact, Low Effort)

- [ ] Recruit 2–3 people (peers, supervisor, colleagues) to rate 10 generated
      RCA reports on a simple 1–5 scale for: usefulness, trustworthiness,
      explainability.
- [ ] Report inter-rater agreement even at small N (state it as a limitation,
      not omit it).
- [ ] Use this to give empirical support to **H4** ("confidence-aware agent
      voting improves recommendation quality and trust"), which currently has
      zero empirical backing in the codebase.

## 3. Docs/Code Consistency Cleanup

- [x] Rewrite documentation architecture section to match actual implementation:
  - [x] Replace "LangGraph" orchestration claims with accurate description of
        the custom `http.server`-based JSON orchestration layer
        (`agent-orchestrator/main.py`, `investigation-engine/main.py`).
  - [x] Replace "React / Vue / Svelte + D3.js" frontend claims with accurate
        description of the static HTML/CSS/vanilla-JS UI
        (`services/ui/static/*`) — done in `README.md`; the topology graph
        is hand-built SVG DOM manipulation, no D3/charting library is
        actually used anywhere.
  - [x] Reframe AWS EKS/IAM/S3 references as historical/superseded — README's
        architecture section already notes current deployment uses
        Helm+kubeadm, not AWS-specific; `docs/architecture/design-evolution.md` (new)
        covers the full reasoning.
- [x] Add a **"Design Evolution / Deviations from Initial Design"** doc —
      `docs/architecture/design-evolution.md`, covering all three deviations: AWS →
      Helm/kubeadm, LangGraph → custom orchestrator, planned SPA → static
      UI, each framed as an engineering decision with a reason. Written as
      a standalone doc rather than inline in the dissertation chapters
      (which don't exist yet — Section 6 below) — ready to drop into a
      Methodology/Discussion subsection once that writing starts.
- [ ] Reconcile `ROADMAP.md` checkboxes fully — some items already correctly
      marked `[~]` (partial); ensure Week 7 statistical analysis checkboxes
      reflect actual completion once Section 1 above is done.

## 4. Threats to Validity / Limitations Section

- [ ] Write an explicit Threats to Validity section covering:
  - [ ] Small dataset size (36 scenarios vs. production-scale incident
        volumes).
  - [ ] Fault-type coverage: RCAEval RE2 spans only resource and network
        faults, so claims scope to those and not to config, security, or
        deployment incidents.
  - [ ] Chaos-injected faults in benchmark systems vs. organically
        occurring production incidents.
  - [ ] LLM output non-determinism (temperature effects on RCA repeatability).
  - [ ] Rule-based fallback bias — when no LLM API key is configured, agents
        silently fall back to deterministic rules; state whether/how this
        affects reported "multi-agent" results.
  - [ ] Single-author ground-truth labeling with no inter-rater reliability
        check (unless Section 2 human eval is completed).
  - [ ] Reliance on `sentence-transformers/all-MiniLM-L6-v2` — a relatively
        small embedding model — for all vector retrieval.

## 5. Security/Completeness Fixes (Small Effort, Removes Red Flags)

- [ ] Add minimal API authentication (a simple API-key header check is
      sufficient) to `services/api/app/main.py` — currently
      `allow_origins=["*"]` with zero auth on any route.
      `/api/v1/settings` stores a real cloud provider API key, so this is a
      genuine credential-exposure risk on any deployment reachable beyond a
      trusted network, not just a completeness gap.
- [ ] Either deploy Tempo genuinely in the demo environment (manifest already
      exists at `deployments/kubernetes/observability/tempo.yaml`) so real trace
      data drives `CALLS` relationship generation, or explicitly document that
      `build_service_dependency_map()` relies on the env-var/naming-convention
      fallback tiers in the current demo, and discuss the limitation.

## 6. Dissertation Writing (Currently 0% Complete — Largest Remaining Time Cost)

- [ ] **Introduction** — problem motivation, RQ1–RQ4, H1–H4 (definitions and
      per-question verdicts already tabulated in `dissertation/PROGRESS.md`).
- [ ] **Literature Review** — expand `dissertation/LITERATURE_REVIEW.md` into
      full academic prose with citations in required format (reference list
      already compiled in `dissertation/REFERENCES.md`; three entries there
      are flagged ⚠ as needing independent verification).
- [ ] **Methodology** — write from `experiments/README.md` and
      `experiments/DATA_PROVENANCE.md`, following
      `dissertation/DISSERTATION_OUTLINE.md` Chapter 5.
- [ ] **System Design / Implementation** — write from `docs/architecture/` and
      actual code; include the Design Evolution subsection from Section 3.
- [ ] **Evaluation** — cannot be credibly written until Section 1 is complete.
      This chapter receives the heaviest marker scrutiny.
- [ ] **Discussion** — explicitly answer RQ1–RQ4 with evidence; include at least
      one place where results were weaker than expected (e.g., GPCS may
      underperform on causal claims requiring multi-hop inference — test and
      report this honestly, as flagged in the GPCS design doc itself).
- [ ] **Conclusion & Future Work** — list current "Still Left" items (real-time
      push, SPA migration, multi-cluster, auth hardening) as legitimate future
      work.
- [ ] **Appendices** — include the benchmark dataset, raw statistical test
      outputs, and (if completed) human evaluation forms/results.

## V1 Time Allocation Guide

| Task Area                                          | Relative Effort | Marks Impact                        |
| -------------------------------------------------- | --------------- | ----------------------------------- |
| Real pipeline benchmark runs + statistical testing | High            | Very High                           |
| GPCS self-consistency baseline                     | Medium          | High                                |
| Threats to Validity + minimal human eval           | Low–Medium      | High                                |
| Docs/code consistency cleanup                      | Low             | Medium (risk mitigation)            |
| API auth / security fix                            | Low             | Medium (risk mitigation)            |
| Dissertation writing (all chapters)                | Very High       | Determines final grade              |
| Real-time push / SPA / multi-cluster               | High            | **Do not attempt — defer to v2/v3** |

---

# 🚀 V2 — Journal Submission Hardening (Post-Dissertation)

Scope: turn the dissertation's empirical work into a defensible, reproducible
research artifact suitable for a peer-reviewed AIOps/MLSys/systems venue.

## Evaluation Depth

- [ ] Scale the incident benchmark dataset to 100+ scenarios (the original
      target stated in `README.md` but never reached).
- [ ] Replace synthetic/scripted incidents with a mix of real production-style
      traces — consider public incident datasets or partnering with an org
      willing to share anonymized incident logs.
- [ ] Run each baseline multiple times with different random seeds / LLM
      temperatures and report variance, not single-run point estimates.
- [ ] Add ablation studies isolating the individual contribution of each
      pipeline stage (GraphRAG alone vs. +Agents vs. +GCP vs. +GPCS) with proper
      factorial design rather than the current cumulative-stacking comparison.
- [ ] Formalize human evaluation: recruit 8–10+ raters, compute Cohen's Kappa /
      Krippendorff's alpha for inter-rater reliability, use a validated rubric
      (not an ad hoc 1–5 scale).
- [ ] Add cost/latency/token-usage analysis comparing LLM-call volume across
      baselines — a common reviewer request for AIOps papers.

## Related Work & Positioning

- [ ] Expand literature review to directly compare against recent
      GraphRAG-for-RCA papers already in `dissertation/REFERENCES.md` (MetaRCA, Agentic
      Structured Graph Traversal, Graphical Causal Reasoning for Root Cause
      Analysis) with a proper comparison table (method, dataset, metrics,
      limitations).
- [ ] Identify and cite 2025–2026 competing/adjacent systems not yet in the
      reference list; run a systematic (not ad hoc) literature search.

## Reproducibility

- [ ] Publish the benchmark dataset, prompts, and evaluation scripts as a
      versioned artifact (e.g., a `benchmark/` release with a DOI via Zenodo).
- [ ] Add prompt/version pinning — currently no prompt-versioning system
      exists in source control.
- [ ] Containerize the full evaluation harness so reviewers can reproduce
      numbers without manual environment setup.
- [ ] Add a `CITATION.cff` and clear artifact-availability statement.

## Security & Deployment Realism

- [ ] Implement full authentication/authorization (OAuth2 or API-key scoping)
      rather than the minimal v1 fix.
- [ ] Add TLS/secrets management for Neo4j and Qdrant in the Helm chart
      (currently plaintext credentials via `NEO4J_AUTH` env var).
- [ ] Add network policies and RBAC least-privilege review
      (`cloudgraph-discovery` ClusterRole currently grants broad read access
      cluster-wide).

## Writing for Publication

- [ ] Condense the dissertation's Evaluation and Discussion chapters into a
      standalone paper draft (8–10 pages, target venue format — e.g. NOMS,
      ICSE-SEIP, or an MLSys/AIOps workshop).
- [ ] Reframe GPCS and GCP as the paper's core technical contributions with
      dedicated formal descriptions (algorithm boxes, complexity analysis — the
      latter already partially exists in `docs/design/GCP_DESIGN.md`).
- [ ] Get supervisor/co-author sign-off and identify 2–3 target venues before
      submission.

---

# 🎓 V3 — PhD-Track Extensions

Scope: generalize CloudGraph's contributions beyond a single-author Kubernetes
prototype into research programs with independent theoretical or empirical
depth.

## Generalization Beyond Kubernetes

- [ ] Extend the knowledge-graph schema and GraphRAG retrieval layer to a second
      infrastructure domain (e.g., serverless/FaaS, service mesh, or multi-cloud
      environments) to test generalizability of the core claims (RQ1–RQ3).
- [ ] Evaluate portability of GCP/GPCS to non-Kubernetes observability graphs
      (e.g., distributed tracing-only environments without a strong topology
      graph).

## Theoretical Depth

- [ ] Formalize Graph Confidence Propagation (GCP) as a probabilistic graphical
      model; connect explicitly to existing literature on belief propagation and
      Noisy-OR networks, with convergence/complexity proofs beyond the current
      empirical `O(V·b^d)` estimate in `docs/design/GCP_DESIGN.md`.
- [ ] Investigate calibration properties of GPCS trust scores (are 0.7-trust
      claims actually correct ~70% of the time? — formal calibration analysis,
      reliability diagrams).
- [ ] Explore theoretical bounds on hallucination reduction achievable via
      graph-grounding vs. fundamental LLM hallucination rates — position this as
      a broader contribution to grounded-generation research, not just AIOps.

## Multi-Agent Systems Research

- [ ] Move beyond the current fixed 5-agent, rule-weighted consensus design
      toward learned consensus (e.g., a lightweight meta-model trained to weight
      agent outputs based on historical accuracy per incident category).
- [ ] Study emergent failure modes of multi-agent LLM systems in
      production-incident settings — a topic with growing interest in the
      broader agentic-AI research community, extending naturally from your Week
      5/6 work.

## Large-Scale Empirical Study

- [ ] Partner with an industry team (or use large public incident corpora) to
      validate CloudGraph-style GraphRAG RCA at production scale (thousands of
      incidents), addressing the "small dataset" limitation carried over from
      v1/v2.
- [ ] Conduct a longitudinal study: does the growing temporal knowledge graph
      actually improve RCA quality over time, as the original data-collection
      strategy claimed? This requires multi-month deployment data — a natural
      PhD-length study.

## Systems Contributions

- [ ] Real-time push architecture (WebSocket/SSE) and true
      multi-cluster/multi-cloud discovery — deferred from v1 — become legitimate
      systems-track contributions if built with rigor (e.g., evaluating
      consistency/latency trade-offs of live graph updates across clusters).
- [ ] Investigate learned/adaptive GraphRAG retrieval (e.g., reinforcement
      learning over hop-depth and ranking weights) rather than the current fixed
      hybrid-scoring formula — a natural PhD research question building directly
      on `hybrid_ranker.py`.

## Publication Targets (Illustrative)

- [ ] v2 paper: applied systems venue (NOMS, IM, ICSE-SEIP, AIOps workshop).
- [ ] v3 extensions: top-tier ML/systems venue (MLSys, OSDI/SOSP workshop track,
      or a dedicated agentic-AI/LLM-systems venue) once theoretical and
      large-scale empirical components are added.

---

## Summary

| Version | Scope                                                                                                       | Primary Outcome                     |
| ------- | ----------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| **v1**  | Real evaluation, minimal human study, docs/code consistency, security patch, full write-up                  | 95+ dissertation mark               |
| **v2**  | Reproducibility, dataset scale-up, formal ablations, related-work depth, security hardening                 | Peer-reviewed applied-systems paper |
| **v3**  | Theoretical grounding, generalization beyond Kubernetes, large-scale/longitudinal study, learned components | PhD-track research program          |

**Immediate next action:** Start with V1, Section 1 (real benchmark pipeline
runs) — every other v1 item depends on having credible numbers to write about.
