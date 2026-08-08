# IMPLEMENTATION_ROADMAP.md

Five phases. Each phase must complete before the next begins — this is a hard dependency chain, not a suggestion, because every later phase's evidence depends on earlier phases being real.

---

## Phase 1 — Make the evaluation loop real (COMPLETED)

**Objective.** Replace the simulated `_calc_*` heuristic functions in `benchmark.py` with real invocations of retrieval, orchestration, GCP, and GPCS against the existing 25-scenario dataset.

**Research motivation.** No claim anywhere in this roadmap has evidentiary value until this is done. This is not itself a research contribution; it is the precondition for all of them.

**Implementation tasks.**

- Build an `evaluate_scenario(scenario, method, orchestration_mode)` function that actually calls `graphrag_search`/`graph_traversal_retriever`/`semantic_store`, the orchestrator, GCP, and GPCS, and returns real precision/recall/F1 against `expected_tags` and `ground_truth_claims`.
- Remove the fixed-offset `tp = len(tags) + N` pattern entirely.
- Add wall-clock latency measurement per condition (already partially present, keep it).
- Re-run and report the "before/after" numbers honestly, including if the real numbers are worse than the simulated ones — this asymmetry (simulated always increasing monotonically; real numbers may not) is itself worth one paragraph in the methodology chapter as evidence of rigor.

**Expected experiments.** A single controlled run: Keyword vs. Vector vs. Graph vs. Hybrid, each with real evaluation, on the 10 existing scenarios.

**Risks.** Real numbers may show much smaller gaps between methods than the simulated leaderboard implied, or even show a different ranking. This is expected and should be reported, not resisted.

**Deliverables.** A real evaluation harness (Python module, not UI-only), a re-run benchmark table, and a short "simulated vs. real" comparison note for the methodology chapter.

---

## Phase 2 — Cheap, high-value controls and ablations

**Objective.** Add the lowest-cost, highest-value experimental conditions: raw-context control (RQ6), neuro-symbolic ablation (Contribution 3 — largely free reuse of existing `keyword`/`vector`/`hybrid` methods), and GPCS-vs-self-consistency (RQ1, Contribution 2, already specified in `HALLUCINATION_SCORING_DESIGN.md`).

**Research motivation.** These three experiments require the least new code and answer the questions a reviewer will ask first: "does structure help vs. just dumping context," "does the graph earn its complexity," and "is your hallucination detector better than the obvious baseline."

**Implementation tasks.**

- Raw-context assembler: given an incident window, pull all evidence nodes without ranking/filtering and concatenate into a prompt; run the same consensus/agent step on it.
- Self-consistency baseline for GPCS: generate the RCA text 2–3 times at elevated temperature, extract claims each time (reuse `GraphProvenanceClaimScorer.extract_claims`), flag claims that don't recur as unsupported; report agreement/disagreement with GPCS per claim type.
- Neuro-symbolic ablation write-up: re-run the existing `keyword` (near-pure symbolic/lexical), `vector` (near-pure neural/semantic), and `hybrid` (neuro-symbolic) methods from Phase 1's real harness, and analyze failure modes qualitatively per method, not just aggregate scores.

**Expected experiments.** 3-way comparison (raw-context vs. hybrid-retrieval), GPCS-vs-self-consistency agreement/disagreement table stratified by claim type, and a qualitative failure-mode table for the neuro-symbolic ablation.

**Risks.** GPCS and self-consistency may simply agree most of the time on a 25-scenario dataset (too small to show disagreement) — this motivates Phase 3's dataset scaling before this experiment is fully reportable, though a first pass here is still valuable for iterating on the harness.

**Deliverables.** Three short experimental notes/tables ready to drop into a results chapter or paper draft; validated harness extensions for later phases.

---

## Phase 3 — Dataset scaling and statistical rigor

**Objective.** Scale the benchmark from 25 to 100+ category-stratified scenarios (per the existing `data-collection-strategy.md` target), add a held-out split for calibration, and implement statistical significance testing.

**Research motivation.** 25 scenarios cannot support meaningful statistics or a held-out calibration split; this is the dataset work explicitly flagged as unstarted in `ROADMAP.md` (Week 7) and required by every Tier-1/Tier-2 RQ that depends on cross-category robustness (RQ15) or calibration (RQ5, RQ9).

**Implementation tasks.**

- Extend `benchmark_dataset.py`'s schema and generate/curate 100+ scenarios across the five existing categories (Kubernetes, networking, security, deployment, observability), using the chaos-injection tooling already scaffolded (`apply_demo_incident.sh`, Falco/chaos adapters) to produce at least some scenarios from real cluster runs rather than hand-authored text.
- Define a fixed 70/30 (or similar) train/held-out split with the split boundary fixed *before* any weight fitting or threshold calibration (this ordering is a labeled requirement in `HALLUCINATION_SCORING_DESIGN.md` and must not be violated).
- Implement paired statistical testing (paired bootstrap and/or Wilcoxon signed-rank, since conditions share incidents) in the evaluation harness from Phase 1.
- Add inter-rater agreement tooling for any manually-labeled ground truth (Cohen's kappa) if more than one person labels scenarios.

**Expected experiments.** Full re-run of Phase 1 and Phase 2 experiments at n≥100, with confidence intervals and significance tests reported for every headline comparison; a category-stratified breakdown (RQ15).

**Risks.** Scenario authoring/labeling is the single largest time sink in the whole roadmap; budget accordingly and prefer semi-automated generation (chaos injection + templated ground truth) over fully manual authoring where possible.

**Deliverables.** A versioned 100+-scenario dataset with documented provenance, a held-out split, and a statistically rigorous results table for the dissertation's evaluation chapter.

---

## Phase 4 — Calibrated GCP and multi-agent interaction

**Objective.** Implement the two contributions that require genuinely new algorithmic/experimental infrastructure: GCP weight fitting + calibration (Contribution 4, RQ5, RQ9) and one round of cross-agent critique (Contribution 5, RQ4).

**Research motivation.** These are the contributions most likely to constitute the dissertation's primary novel-methods chapter, since Phases 1–3 are mostly evaluation rigor rather than new mechanisms.

**Implementation tasks.**

- GCP: fit `EDGE_WEIGHTS` and `decay_factor` on the Phase-3 training split (e.g. via grid search or a simple differentiable relaxation) to maximize root-cause top-1 accuracy or minimize Brier score; compute reliability diagrams and Brier score on the held-out split for both hand-set and fitted weights.
- GPCS/self-consistency threshold: calibrate the trust-score cutoff on the held-out split rather than hand-picking it (also already labeled as required in the design doc).
- Multi-agent critique: add one orchestration mode where each specialist sees the other four specialists' findings and revises its confidence/finding once before consensus; this needs a new orchestrator code path (`agent-orchestrator/main.py`) but reuses `_call_llm_agent` machinery already present.
- Run the matched-compute self-consistency control (Mode D from `SYSTEM_ARCHITECTURE.md`) to isolate whether any gain from the critique round is due to interaction or just extra compute.

**Expected experiments.** Fitted-vs-hand-set GCP weights (held-out accuracy + calibration curves); independent-ensemble vs. critique-round vs. matched-compute-self-consistency (accuracy + hallucination rate + latency + call count).

**Risks.** Weight fitting on ~70 training incidents may overfit; report training vs. held-out gap explicitly. The critique round may not beat the simpler baselines — this is a valid, reportable negative result per Contribution 5's design.

**Deliverables.** Calibration curves and fitted-weight tables; a controlled multi-agent-interaction comparison table; updated GCP/GPCS modules with documented calibration procedures.

---

## Phase 5 — Positioning, comparison, and write-up

**Objective.** Benchmark against or carefully position relative to MetaRCA and agentic structured graph traversal for RCA (RQ11), finalize the temporal-operational-GraphRAG framing (Contribution 1), and produce publication-ready artifacts.

**Research motivation.** No submission is credible without addressing the closest 2025–2026 prior work directly; this phase closes that gap and consolidates everything above into a coherent narrative.

**Implementation tasks.**

- Attempt a fair comparison against MetaRCA / agentic structured graph traversal: either reproduce a minimal version of each on CloudGraph's dataset, or adapt CloudGraph's evaluation to a dataset/metric reported in their papers, whichever is more tractable; if neither is feasible within time constraints, produce a rigorous qualitative comparison table (architecture, evaluation methodology, dataset scale, reported numbers) and state this limitation explicitly rather than omitting the comparison.
- Write the temporal-operational-GraphRAG framing as a short standalone analysis: quantify how often ground-truth-relevant evidence falls outside a naive (non-temporal) top-k window, to make the temporal-retrieval contribution concrete rather than asserted.
- Consolidate all phase results into reproducibility artifacts: fixed seeds, versioned dataset, exported configs, and a results notebook/script that regenerates every table and figure from raw run logs.
- Draft the paper/dissertation chapters using the exact structure in `PUBLICATION_STRATEGY.md`.

**Expected experiments.** Final comparison table against external baselines/systems; temporal-retrieval necessity analysis; full reproducibility check (re-run from scratch produces matching results within tolerance).

**Risks.** External reproduction may not be possible if MetaRCA/Cui et al. code or datasets are not public — mitigate by contacting authors early and having the qualitative-comparison fallback ready well before the submission deadline.

**Deliverables.** Reproducibility package, final results chapter, and a draft manuscript targeting the venue(s) selected in `PUBLICATION_STRATEGY.md`.

---

## Phase-to-existing-roadmap mapping

| This roadmap | Corresponds to (existing project state) |
|---|---|
| Phase 1 | The user's existing "v1 — highest priority blocker" (real pipeline runs replacing heuristic benchmarks) |
| Phase 2 | Overlaps with v1's remaining items: GPCS self-consistency baseline, statistical significance groundwork |
| Phase 3 | v1's dataset scaling target (100+ scenarios) plus v2's reproducibility/statistics requirements, pulled earlier because they are prerequisites for Phase 4's calibration work |
| Phase 4 | v2's formal ablation studies and inter-rater reliability, plus new GCP/GPCS calibration work not currently on any existing roadmap tier |
| Phase 5 | v2's applied-systems paper draft, and the comparison/positioning work needed regardless of venue |

Note: this sequencing pulls some v2 items (dataset scaling, statistics) earlier than the user's original v1→v2→v3 split, because Phase 4's calibration work is not statistically meaningful without them. v3 items (theoretical formalization beyond what Phase 4 covers, generalization beyond Kubernetes, learned/RL-based consensus, longitudinal studies) remain correctly out of scope for this roadmap and are PhD-track, not dissertation-track.
