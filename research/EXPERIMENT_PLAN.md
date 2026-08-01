# EXPERIMENT_PLAN.md

## Datasets

**Primary.** The existing 25-scenario `BENCHMARK_GROUND_TRUTH_SCENARIOS` (`app/demo/benchmark_dataset.py`), scaled to 100+ under Phase 3, stratified across the five existing categories (Kubernetes, networking, security, deployment, observability). Each scenario must retain: a natural-language query, `target_service`/`target_entity`, `root_cause` label, `expected_tags` (for evidence precision/recall), and `ground_truth_claims` (for GPCS/self-consistency evaluation).

**Provenance requirement.** At minimum a documented subset (recommend ≥30%) should originate from actual chaos-injected cluster runs (using the existing `apply_demo_incident.sh` and Falco/chaos adapters) rather than hand-authored text, so that evidence (logs, metrics, traces) is real telemetry, not synthetic prose — this materially strengthens external validity claims.

**Held-out split.** Fixed 70/30 split, boundary set *before* any weight fitting or threshold calibration (Phase 3/4). The split must be stratified by category so both splits contain all five categories.

**Secondary/comparison dataset.** If a public dataset or reported-results table exists for MetaRCA or Cui et al.'s agentic structured graph traversal system, use it (or an adapted subset) for the Phase 5 comparison; otherwise document its absence explicitly as a limitation.

## Benchmarks / conditions (independent variable levels)

Retrieval method: `{keyword, vector, graph-only, hybrid, raw-long-context}`
Orchestration mode: `{single-LLM-no-specialization, independent-specialists+static-vote (current), independent-specialists+one-critique-round, self-consistency-ensemble-matched-compute}`
GCP weights: `{hand-set (current), data-fit}`
Hallucination detection: `{GPCS, self-consistency}` — run both on every generated report, not as an exclusive choice

This produces a 5×4×2 factorial space (40 cells) before crossing with hallucination detection; not every cell needs a full run in Phase 1–2 (see below for the minimal-viable-experiment ordering), but the harness should support the full space so later phases can query any cell without new plumbing.

## Baselines

1. **Keyword search** (already implemented, must become real per Phase 1) — literature baseline representing pre-embedding IR.
2. **Vector-only RAG** (already implemented) — literature baseline representing Lewis et al. 2020-style RAG.
3. **Raw-long-context** (new, Phase 2) — controls for "does structure matter at all given a large context window."
4. **Self-consistency** (new, Phase 2/4) — the literature-standard hallucination-detection and matched-compute multi-agent control.
5. **MetaRCA / agentic structured graph traversal** (Phase 5, best-effort) — closest direct competitors; required for positioning even if only a qualitative comparison is achievable.

## Metrics

**Retrieval quality.** Precision, recall, F1 over `expected_tags`; top-1 and top-3 root-cause accuracy.

**Hallucination.** Unsupported-claim rate (GPCS and self-consistency, reported separately and as an agreement/disagreement cross-tab), broken down by claim type (`temporal`, `causal`, `entity_relationship`, `state`, `general`).

**Confidence quality (new).** Brier score and reliability-diagram calibration for GCP root-cause confidence, computed only on the held-out split.

**Efficiency.** Wall-clock latency (already partially instrumented) and LLM call count per condition (new — required to matched-compute-control the multi-agent experiments).

**Explainability (secondary, if time allows).** Explanation-path completeness (already defined conceptually in `research-methodology.md`; needs an operational scoring rubric).

## Ablation studies

1. **Retrieval ablation** (Contribution 3 / RQ17): keyword vs. vector vs. hybrid, same downstream orchestration — isolates the graph/symbolic component's contribution.
2. **Orchestration ablation** (RQ3/RQ4/Contribution 5): single-LLM vs. independent-ensemble vs. critique-round vs. self-consistency-ensemble, same retrieved evidence — isolates whether gains come from specialization, interaction, or raw compute.
3. **GCP weight ablation** (RQ5/Contribution 4): hand-set vs. fitted weights, and a sensitivity sweep over individual edge-type weights and the decay factor, to characterize how much any single weight choice matters.
4. **GPCS component ablation**: drop each term of the trust-score formula (semantic alignment, graph proximity, source reliability, path-length penalty) one at a time to determine which components actually drive the unsupported-claim classification, since the formula currently has no reported per-term sensitivity.
5. **Temporal-filtering ablation** (Contribution 1): traversal with vs. without the temporal window constraint, on the subset of scenarios where root cause and symptom are separated by a nontrivial time gap.

## Statistical significance testing

- Conditions are evaluated on the *same* incidents (paired design) — use **paired bootstrap** (resample incidents with replacement, recompute the metric delta each time, report the 95% CI of the delta) as the primary test, since it makes no distributional assumption and directly answers "how likely is this delta due to chance."
- **Wilcoxon signed-rank test** as a secondary confirmatory test for paired accuracy/F1 comparisons.
- Report effect sizes (not just p-values) — e.g., Cohen's d or the raw accuracy-point delta with CI — per the dissertation's own "avoid overclaiming" discipline.
- With n≈100 (Phase 3), power is adequate for medium effect sizes (~0.5 Cohen's d) at α=0.05 with paired tests; explicitly note this power limitation for any small or category-specific comparisons that use fewer scenarios.

## Failure analysis

For every headline comparison, in addition to the aggregate metric, produce:

- A confusion-style breakdown of root-cause misclassifications by category (does GraphRAG fail more on security incidents than K8s incidents?).
- A qualitative sample (5–10 cases) of GPCS/self-consistency disagreement, manually reviewed and categorized (GPCS-right, self-consistency-right, both-wrong, ambiguous).
- The neuro-symbolic ablation's per-method failure taxonomy (Phase 2) as the primary qualitative-analysis artifact.

## Generalization tests

- Category-stratified evaluation (RQ15) is the primary generalization check within-domain — report per-category accuracy, not just aggregate, and test whether the aggregate improvement is uniform or concentrated (e.g., via a category × method interaction test).
- Held-out split (Phase 3/4) is the primary train/test generalization check for any fitted parameters (GCP weights, GPCS threshold).
- Cross-domain generalization (RQ18, generalizing beyond Kubernetes) is explicitly **out of scope** for the dissertation-track experiment plan and reserved for the v3/PhD-track roadmap; do not claim generalization beyond the tested domain.

## Scalability evaluation

- Graph-size scaling sweep (RQ16): measure traversal latency and retrieval quality as the Neo4j graph grows across at least 3 orders of magnitude (hundreds → tens of thousands → hundreds of thousands of nodes), using synthetic graph expansion if real cluster scale is unavailable, clearly labeled as synthetic.
- Report where the bounded k-hop traversal's fixed depth (currently 1–4) becomes a limiting factor as graph density increases.

## Cost and latency evaluation

- LLM call count and estimated token cost per condition (critical for the multi-agent matched-compute comparisons in Phase 4 — without this, any "multi-agent is better" claim is confounded with "multi-agent uses more tokens").
- Wall-clock latency distribution (not just mean) per condition, since RCA is a latency-sensitive use case and tail latency matters operationally even if it is secondary to the accuracy/novelty narrative.

## Minimal-viable-experiment ordering (do these first, in order, if time is constrained)

1. Real keyword/vector/hybrid comparison on existing 25 scenarios (Phase 1) — smallest possible real result.
2. GPCS vs. self-consistency on existing 25 scenarios (Phase 2) — reuses Phase 1 harness, no new dataset needed.
3. Raw-long-context control (Phase 2) — one new retrieval condition, reuses everything else.
4. Scale dataset to 100+ (Phase 3) and re-run 1–3 with statistics.
5. GCP calibration and multi-agent interaction ablation (Phase 4) — only once 1–4 are solid.
