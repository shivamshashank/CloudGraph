# CloudGraph — Dissertation Completion & Future Roadmap

**Goal:** Reach 95+ marks on the current dissertation (v1), then extend the work
toward journal publication and PhD positioning (v2 / v3).

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

- [ ] Replace heuristic benchmark calculators (`_calc_kw`, `_calc_vector`,
      `_calc_graphrag`, `_calc_agents`, `_calc_gcp`, `_calc_gpcs` in
      `routers/benchmark.py`) with **real pipeline invocations** — each baseline
      must actually run keyword search / vector search / GraphRAG traversal /
      agent orchestration / GCP / GPCS against the ground-truth dataset, not
      simulate scores via formulas.
- [ ] Expand the benchmark dataset from 10 to **25–30 scenarios** if time
      allows, maintaining balanced coverage across Kubernetes, Networking,
      Security, Deployment, and Observability categories already defined in
      `research-methodology.md`.
- [ ] Implement a **train/held-out split** (e.g. 70/30, matching the split
      already documented in `docs/week-2` evidence but not yet applied to actual
      threshold calibration).
- [ ] Add **statistical significance testing**:
  - [ ] Paired t-test or Wilcoxon signed-rank test between baseline pairs (e.g.
        GraphRAG vs Vector RAG; GraphRAG+Agents+GCP+GPCS vs GraphRAG alone).
  - [ ] Report p-values and effect sizes (Cohen's d) alongside raw metric
        deltas.
  - [ ] Add **bootstrap or normal-approximation confidence intervals** on
        headline accuracy/F1/hallucination-rate numbers.
- [ ] Implement the **GPCS self-consistency baseline** (explicitly marked "not
      optional" in `HALLUCINATION_SCORING_DESIGN.md` but currently absent from
      `gpcs.py`):
  - [ ] Generate 2–3 RCA outputs per incident at higher temperature.
  - [ ] Extract claims from each generation using the existing Step A claim
        extractor.
  - [ ] Flag claims as unsupported if they don't recur consistently across
        generations.
  - [ ] Produce a comparison table: GPCS vs self-consistency
        agreement/disagreement, broken down by claim type (temporal, causal,
        entity_relationship, state).
- [ ] Calibrate the GPCS `threshold` value (currently hardcoded at 0.50 in
      `GraphProvenanceClaimScorer.__init__`) on the held-out split rather than
      leaving it as an unvalidated constant.
- [ ] Report hallucination rate **broken down by claim type and incident
      category**, not just as a single aggregate number (per-category breakdown
      was named as a required output in the GPCS design doc but is not yet
      produced by `score_claims`).

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
  - [ ] Replace "React / Vue / Svelte + D3.js" frontend claims with accurate
        description of the static HTML/CSS/vanilla-JS UI
        (`services/ui/static/*`), or add a small real D3 enhancement to
        `topology.js` to make the claim true.
  - [ ] Reframe AWS EKS/IAM/S3 references as historical/superseded, consistent
        with the annotations already present in
        `docs/week-1/architecture-design.md` and
        `docs/week-1/data-collection-strategy.md`.
- [ ] Add a **"Design Evolution / Deviations from Initial Design"** section to
      the dissertation itself (Methodology or Discussion chapter) explicitly
      explaining: AWS → Helm/kubeadm, LangGraph → custom orchestrator, planned
      SPA → static UI. Frame these as engineering decisions with reasons, not
      omissions.
- [ ] Reconcile `ROADMAP.md` checkboxes fully — some items already correctly
      marked `[~]` (partial); ensure Week 7 statistical analysis checkboxes
      reflect actual completion once Section 1 above is done.

## 4. Threats to Validity / Limitations Section

- [ ] Write an explicit Threats to Validity section covering:
  - [ ] Small dataset size (10–30 synthetic scenarios vs. production-scale
        incidents).
  - [ ] Synthetic vs. real-world incident realism.
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
      `allow_origins=["*"]` with zero auth on any route, including LLM settings
      endpoints that store plaintext API keys in Neo4j.
- [ ] Either deploy Tempo genuinely in the demo environment (manifest already
      exists at `deployments/kubernetes/observability/tempo.yaml`) so real trace
      data drives `CALLS` relationship generation, or explicitly document that
      `build_service_dependency_map()` relies on the env-var/naming-convention
      fallback tiers in the current demo, and discuss the limitation.

## 6. Dissertation Writing (Currently 0% Complete — Largest Remaining Time Cost)

- [ ] **Introduction** — problem motivation, RQ1–RQ4, H1–H4 (source material
      already exists in `docs/week-1/research-methodology.md`).
- [ ] **Literature Review** — expand `docs/week-1/literature-review.md` into
      full academic prose with citations in required format (reference list
      already compiled in `docs/week-1/references.md`).
- [ ] **Methodology** — adapt from `research-methodology.md`; update with the
      real (not heuristic) evaluation protocol once Section 1 is complete.
- [ ] **System Design / Implementation** — adapt from `architecture-design.md`
      and actual code; include the Design Evolution subsection from Section 3.
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
      target stated in `README.md` and `docs/week-1/data-collection-strategy.md`
      but never reached).
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
      GraphRAG-for-RCA papers already in `references.md` (MetaRCA, Agentic
      Structured Graph Traversal, Graphical Causal Reasoning for Root Cause
      Analysis) with a proper comparison table (method, dataset, metrics,
      limitations).
- [ ] Identify and cite 2025–2026 competing/adjacent systems not yet in the
      reference list; run a systematic (not ad hoc) literature search.

## Reproducibility

- [ ] Publish the benchmark dataset, prompts, and evaluation scripts as a
      versioned artifact (e.g., a `benchmark/` release with a DOI via Zenodo).
- [ ] Add prompt/version pinning — currently no prompt-versioning system exists
      in source control (flagged as an open item in
      `docs/GPCS_UI_Benchmark_Roadmap.md`).
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
      latter already partially exists in `docs/research/gcp_design.md`).
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
      empirical `O(V·b^d)` estimate in `gcp_design.md`.
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
      actually improve RCA quality over time, as claimed in
      `data-collection-strategy.md`'s "Dissertation Value" section? This
      requires multi-month deployment data — a natural PhD-length study.

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
