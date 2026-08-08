# 4-Week Publication Sprint Checklist

**Goal:** ship a citable, independently-checkable artifact — the GPCS-vs-self-consistency workshop paper — using CloudGraph's existing GraphRAG + GCP + GPCS pipeline, with a real (not simulated) evaluation loop behind it.

**Scope discipline:** this sprint = `IMPLEMENTATION_ROADMAP.md` Phase 1 + Phase 2 only. Do **not** attempt dataset scaling to 100+, GCP weight fitting, or the multi-agent critique round in this sprint — those are Phase 3/4 and will blow the 4-week budget. The 25-scenario dataset (`app/demo/benchmark_dataset.py`) is sufficient for a workshop-scale submission if the evaluation is real and honestly reported.

**Target venue:** workshop track (NeurIPS/ICLR/ACL/EMNLP-adjacent "RAG / Trustworthy AI / Foundation Models for Systems" workshop — pick based on open CFPs at sprint start). Page budget is typically 4–8 pages + references, which bounds scope appropriately.

---

## Tech stack to add this sprint

| Purpose | Library / tool | Where it plugs in |
|---|---|---|
| Statistical testing | `scipy.stats` (Wilcoxon, bootstrap), `numpy` | new `services/api/scripts/evaluate_real.py` |
| Paired bootstrap CIs | `scikit-learn` (already in `requirements.txt`) resampling utilities, or hand-rolled with `numpy.random.default_rng` | same eval script |
| Results tables/plots | `matplotlib`, `pandas` | new `scripts/make_figures.py` |
| Experiment config/repro | plain `json`/`yaml` run configs + fixed `random.seed`/`np.random.seed` | `experiments/configs/*.yaml` |
| Notebook for exploratory analysis (optional) | `jupyter`, `ipykernel` | `notebooks/gpcs_analysis.ipynb` |
| LLM self-consistency sampling | reuse existing `call_llm` in `app/research/gpcs.py`, just call at `temperature≈0.7–1.0`, N=3 | `app/research/self_consistency.py` (new) |
| Paper writing | LaTeX (Overleaf or local, workshop template from target venue) | separate `paper/` repo or folder, not `services/` |
| Reproducibility packaging | `pip freeze > requirements-lock.txt`, a `Makefile` or `run_all.sh` that regenerates every table/figure from raw logs | repo root |

Add to `services/api/requirements.txt`: `matplotlib`, `pandas` (if not already transitively present), and pin them. Everything else needed (`numpy`, `scipy`, `sentence-transformers`, `neo4j`, `qdrant-client`) is already in the stack.

---

## Week 1 — Kill the simulated benchmark, build the real evaluation harness

**Objective:** every number that appears in the paper must come from an actual pipeline run, never from `benchmark.py`'s current `_calc_*` fixed-offset functions.

### Tasks

- [x] **Audit and freeze scope.** Read `app/routers/benchmark.py` end to end; write down every place `_calc_kw`, `_calc_vector`, `_calc_graphrag`, `_calc_agents`, `_calc_gcp`, `_calc_gpcs` fabricate `tp/fp/fn` instead of measuring them. This audit becomes the "before" section of the methodology write-up.
- [x] **Build `scripts/evaluate_real.py`** (new file, `services/api/scripts/`) with a function:

  ```python
  def evaluate_scenario(scenario: dict, method: str) -> dict:
      # method in {"keyword", "vector", "hybrid"}
      # 1. call graphrag_search(...) or semantic_store.search(...) or
      #    graph_traversal_retriever.retrieve(...) directly — no mocking
      # 2. compute precision/recall/F1 against scenario["expected_tags"]
      #    by matching retrieved node/text content against tags
      # 3. return latency_ms, tp, fp, fn
  ```

  Reuse `app.retrieval.graph_traversal.graph_traversal_retriever`, `app.services.semantic_store.SemanticVectorStore`, `app.retrieval.hybrid_ranker.hybrid_ranker` exactly as `main.py`'s `graphrag_search` endpoint does — call the same code path, not a re-implementation.
- [x] **Wire real orchestration.** For the "agents" condition, actually POST to the investigation-engine/agent-orchestrator services (or call their functions in-process if running the full stack is too slow for 25 scenarios × N runs) instead of the current `tp = len(tags) + 2` stub.
- [x] **Wire real GCP.** Call `GraphConfidencePropagator().run_propagation(target_entity)` against a seeded local graph per scenario (you will need to seed Neo4j with each scenario's evidence — see Data Setup below) and record the actual output confidence, not the toy two-node example currently glued into `_calc_gcp`.
- [x] **Data setup: seed Neo4j/Qdrant per scenario.** For each of the 25 scenarios, write a small fixture that ingests the scenario's implied logs/metrics/commits into Neo4j and Qdrant using the existing adapters (`ingest_loki_log`, `ingest_prometheus_metric`, `SemanticVectorStore.index_document`) so retrieval has something real to retrieve. This is the single most time-consuming Week 1 task — budget 2–3 days.
- [x] **Run and record.** Execute `evaluate_scenario` for all 25 scenarios × {keyword, vector, hybrid}, save raw results to `experiments/results/week1_raw.json`.
- [x] **Sanity check.** Confirm the real numbers are *not* monotonically increasing by construction the way the simulated ones were — if hybrid doesn't clearly beat keyword on this small set, report that honestly; do not go back and adjust the harness to make it look better.

### End-of-week deliverable

A working, real evaluation script with raw JSON results for retrieval methods on all 25 scenarios, plus a one-paragraph note comparing the real numbers to the old simulated benchmark table (this note becomes part of the paper's methodology rigor argument).

---

## Week 2 — Self-consistency baseline + GPCS head-to-head

**Objective:** implement the comparison `HALLUCINATION_SCORING_DESIGN.md` already specifies but was never built, and run it against GPCS on real generated RCA text.

### Tasks

- [ ] **Implement `app/research/self_consistency.py`.**

  ```python
  def generate_and_score(analysis_prompt: str, n_samples: int = 3, temperature: float = 0.8) -> dict:
      # 1. call_llm(...) n_samples times at elevated temperature
      # 2. extract_claims() on each generation (reuse
      #    GraphProvenanceClaimScorer.extract_claims — same extractor,
      #    so claim segmentation is identical across both methods,
      #    which is required for a fair comparison)
      # 3. for each claim in generation 1, check if a semantically
      #    equivalent claim recurs in generations 2..n (use the existing
      #    SentenceTransformerEmbedder cosine similarity, threshold ~0.8)
      # 4. flag as unsupported if it doesn't recur in >= half of generations
      # 5. return unsupported_claim_rate, per-claim recurrence detail
  ```

- [ ] **Generate real RCA text for all 25 scenarios.** Use the existing orchestrator/consensus path (or a direct `call_llm` with the same prompt structure `agent-orchestrator/main.py` uses) to produce actual `title`/`summary`/`cause`/`recommendation` text per scenario — this is the input both GPCS and self-consistency will score, so it must be identical for both.
- [ ] **Run GPCS on the same generated text.** `GraphProvenanceClaimScorer().score_claims(analysis, search_func)` — already implemented, just point it at the real generations from this week instead of test fixtures.
- [ ] **Run self-consistency on the same generated text/regenerations.**
- [ ] **Build the comparison table.** Per claim (not just per scenario): GPCS trust score + unsupported flag, self-consistency recurrence + unsupported flag, claim type (`temporal`/`causal`/`entity_relationship`/`state`/`general`). Save to `experiments/results/week2_claims.csv`.
- [ ] **Cross-tab analysis.** Agreement rate (both flag unsupported / both flag supported) vs. disagreement rate, broken down by claim type — this cross-tab is the paper's central empirical result. Compute with `pandas.crosstab`.
- [ ] **Manual review of disagreements.** Pull every case where GPCS and self-consistency disagree (there will only be a handful at n=25 scenarios × ~3-5 claims each — this is tractable to read by hand) and categorize: GPCS-right / self-consistency-right / both-wrong / ambiguous. This qualitative table is what makes the workshop paper's contribution defensible rather than just "we built two things and compared aggregate numbers."

### End-of-week deliverable

`week2_claims.csv`, the agreement/disagreement cross-tab, and a hand-annotated table of disagreement cases with correctness judgments — this is effectively the paper's Results section in raw form.

---

## Week 3 — Statistics, figures, and the raw-context control (cheap bonus experiment)

**Objective:** add statistical rigor and the one extra control condition that meaningfully strengthens the paper for near-zero additional engineering cost.

### Tasks

- [ ] **Paired bootstrap CI.** Write `scripts/paired_bootstrap.py`:

  ```python
  def paired_bootstrap_ci(deltas: np.ndarray, n_resamples: int = 10000, seed: int = 42):
      rng = np.random.default_rng(seed)
      resampled_means = [
          rng.choice(deltas, size=len(deltas), replace=True).mean()
          for _ in range(n_resamples)
      ]
      return np.percentile(resampled_means, [2.5, 97.5])
  ```

  Apply to: hybrid-vs-keyword retrieval F1 delta, GPCS-vs-self-consistency unsupported-rate delta. Report explicitly that n=10 gives wide CIs — do not overclaim significance; this honesty is expected and rewarded in review.
- [ ] **Wilcoxon signed-rank** as a secondary confirmatory test (`scipy.stats.wilcoxon`) on the same paired deltas.
- [ ] **Raw-long-context control.** Implement the cheapest version: for each scenario, pull all evidence nodes in the incident window without ranking/filtering (a simple unfiltered Cypher query + all matching Qdrant docs), concatenate into one prompt, generate RCA text the same way as Week 2, and run GPCS + self-consistency on it too. This directly answers "does structure/retrieval matter at all" and is ~1 day of work reusing everything already built.
- [ ] **Figures.** Using `matplotlib`/`pandas`: (1) bar chart of retrieval F1 by method with bootstrap CI error bars, (2) unsupported-claim-rate bar chart: GPCS vs. self-consistency vs. raw-context baseline, by claim type (stacked or grouped bars), (3) the agreement/disagreement cross-tab as a heatmap. Save to `experiments/figures/*.png`, script-generated (not hand-edited) for reproducibility.
- [ ] **Latency/cost table.** Report LLM call count and wall-clock latency per condition — required so the raw-context comparison isn't confounded by "just used a bigger prompt for free," and so multi-agent-adjacent claims (if any survive into this draft) are compute-matched.
- [ ] **Reproducibility pass.** Fix all seeds, freeze `requirements-lock.txt`, write `run_all.sh` that regenerates every number/figure in the paper from `experiments/configs/*.yaml` + raw logs, and actually re-run it once end-to-end from a clean checkout to confirm it reproduces.

### End-of-week deliverable

All figures, all statistical tests, the raw-context control results, and a verified one-command reproduction script.

---

## Week 4 — Write, review, submit

**Objective:** produce and submit the workshop paper draft.

### Tasks

- [ ] **Draft structure** (4–8 pages, adapt to target workshop's template):
  1. **Introduction** — motivate evidence-grounded hallucination detection for operational RAG (graph-provenance claim scoring vs. model-internal self-consistency); state the research question and contribution crisply.
  2. **Related work** — RAG (Lewis et al. 2020), GraphRAG (Edge et al. 2024), self-consistency hallucination detection, briefly position against MetaRCA/Cui et al. as adjacent-but-distinct (full comparison is out of scope for this sprint — say so explicitly).
  3. **Method** — GPCS formula (semantic alignment + graph proximity + source reliability − path-length penalty), self-consistency baseline procedure, identical claim extractor for fairness.
  4. **Experimental setup** — 25-scenario dataset, explicitly stated as a small-scale pilot with n limitations acknowledged up front (do not hide this), real evaluation harness, statistical method.
  5. **Results** — retrieval real-vs-simulated honesty note, GPCS-vs-self-consistency agreement/disagreement by claim type, raw-context control, latency/cost.
  6. **Discussion / limitations** — explicitly state: small n, single domain (Kubernetes), hand-set GPCS weights not yet calibrated (flag as future work, references Phase 4), no comparison yet to MetaRCA/Cui et al. (flag as future work, references Phase 5).
  7. **Conclusion.**
- [ ] **Internal review pass.** Re-read every claim in the draft against the raw JSON/CSV in `experiments/results/` — every number in the text must trace to a file, no numbers from memory or the old simulated benchmark.
- [ ] **Check target workshop's submission requirements** (anonymization if double-blind, page limit, supplementary material policy) — package `experiments/`, figures, and `run_all.sh` as supplementary material/artifact if the venue supports it; this materially helps review outcomes for empirical papers.
- [ ] **Get one external read** (advisor/peer) focused specifically on: does the small-n limitation undermine the core claim, and is the GPCS-vs-self-consistency comparison actually fair (same claim extractor, same generated text, matched compute).
- [ ] **Submit.**

### End-of-week deliverable

Submitted paper + public/archived reproducibility artifact (`experiments/`, `run_all.sh`, `requirements-lock.txt`).

---

## Non-negotiable guardrails for the whole sprint

1. **No number in the paper may come from `benchmark.py`'s existing `_calc_*` functions** — those are simulated and must not appear anywhere in the submission, tables, or supplementary material.
2. **Same claim extractor for GPCS and self-consistency.** If extraction differs between the two methods, the comparison is invalid — this is the single easiest way to accidentally bias the result and must be checked explicitly in code review.
3. **Report n=25 as a stated limitation, not hidden.** A workshop paper honest about small-scale pilot status is fundable; one that overclaims significance at n=25 is a rejection risk and, per the project's existing standards, not the kind of work this repo should produce.
4. **Every figure/table must be regenerable from `run_all.sh`.** No hand-edited numbers in the LaTeX source.
5. **If Week 1's real evaluation shows hybrid retrieval does *not* clearly beat keyword/vector on this dataset, do not change the pitch to hide it** — pivot the paper's emphasis toward the GPCS-vs-self-consistency result (which is the stronger, more novel contribution anyway per `NOVEL_CONTRIBUTIONS.md`) and report the retrieval result as a secondary, honestly-caveated finding.

## Explicitly out of scope for this 4-week sprint (do not attempt)

- Dataset scaling to 100+ scenarios (Phase 3)
- GCP weight fitting/calibration (Phase 4)
- Multi-agent cross-critique orchestration mode (Phase 4)
- Comparison/reproduction of MetaRCA or Cui et al. (Phase 5)
- Any UI/frontend work
- Any Helm/Kubernetes deployment hardening

These remain correctly sequenced in `IMPLEMENTATION_ROADMAP.md` for after this sprint.
