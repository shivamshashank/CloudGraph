# Experiments

## What this is

The flagship research result for CloudGraph: does GPCS (Graph-Provenance
Claim Scoring) agree with self-consistency on which claims in an LLM-
generated root-cause analysis are actually grounded, and does structured
GraphRAG retrieval earn its complexity over dumping unranked context or
using none at all? `results/` holds the full 25-scenario run answering
both questions — Day 2 and Day 3 of `internal/planning/7_DAY_SPRINT_CHECKLIST.md`,
produced together in one pass since `report_runner.py` generates both
sections from the same underlying scenario runs rather than as separate
scripts.

## How we got it

For each of the 25 benchmark scenarios (`app/demo/benchmark_dataset.py`),
under each of 3 context conditions (`none` — no retrieved context, `raw` —
all seeded evidence unranked, `hybrid` — GraphRAG's own ranked retrieval),
the pipeline:

1. Generates 3 sampled RCA analyses (`self_consistency.generate_and_score`)
   and extracts atomic claims from the primary one.
2. Scores those same claims two independent ways: **self-consistency**
   (does the claim recur across the 3 samples?) and **GPCS** (does the
   claim have supporting evidence in the Neo4j graph, found via exact-entity
   traversal and semantic/keyword search, above a calibrated relevance
   floor?).
3. Separately, runs a neuro-symbolic retrieval benchmark (keyword=symbolic,
   vector=neural, hybrid=neuro-symbolic) per scenario, checking whether each
   method's retrieved evidence hits the scenario's expected tags.

Run via `cloudgraph report`, in 5 batches of 5 scenarios
(`--limit 5 --offset {0,5,10,15,20}`) combined with
`services/api/scripts/merge_reports.py` — see that script's docstring for
combining future batched runs. Provider: Meta (`muse-spark-1.2-contributor`).
Generated 2026-08-08.

Getting a valid run required fixing 5 real bugs in GPCS's evidence
retrieval, found by inspecting real output data rather than assuming the
pipeline worked:

1. Entity-name extraction truncated identifiers at the matched keyword
   (`payment-service-pod-7f` → `payment-service-pod`), breaking the graph's
   exact-name match for almost every claim.
2. `graph_traversal_retriever.retrieve()`'s seed-label filter excluded
   `Deployment` nodes entirely.
3. `report_runner.py` wired the wrong function in as GPCS's semantic-search
   callback — the mismatch raised `TypeError` on every call, silently
   caught, so that evidence path contributed nothing at all until fixed.
4. Fixing (3) surfaced a follow-on defect: Qdrant's vector search has no
   relevance threshold, so every claim — however vague — got back some
   "supporting evidence." A `MIN_SEMANTIC_EVIDENCE_SCORE = 0.30` cutoff,
   calibrated against real query scores from this cluster, fixed it.
5. `Node`-labeled entities (`node-worker-01`) were never extracted as
   candidates, since the extraction regex required a character before the
   keyword — but "node" is the keyword *and* the identifier's own prefix.

## Results

- **25/25 scenarios**, 0 excluded attempts (75/75 scenario×condition runs
  succeeded)
- **1777 claims extracted**; GPCS scored **1685 (94.8%)** of them (see
  Known limitations for the other 5.2%)
- **Overall agreement: 1079/1685 (64.0%)** between GPCS and self-consistency

## Conclusion

**GPCS is the more lenient method; self-consistency is the stricter one —
and this is statistically significant, not sampling noise.** GPCS flags
43.7% of claims unsupported vs. self-consistency's 51.5% on the same set.
When the two disagree (606 cases), 60.9% of the time it's GPCS calling a
claim *supported* while self-consistency calls it *unsupported* — only
39.1% the other way. Self-consistency's `recurrence_rate` has a median of
0.0: more than half of all claims never recur across the 3 sampled
generations at all, a strict "did this get said again" bar. GPCS's
evidence-based trust_score is more forgiving — any claim clearing the
~0.30 semantic-relevance floor with reasonable graph proximity passes.
Paired bootstrap over all 75 (scenario × context-condition) groups: mean
delta -0.087, 95% CI **[-0.119, -0.055]** (excludes zero), Wilcoxon
p≈0.0000 — see `results/significance_tests.md`.

**Structured retrieval measurably wins, though not yet at statistical
significance on this sample size.** This is the real, if provisional,
answer to Day 3's question ("does structured retrieval earn its
complexity, or is dumping everything just as good"):

| context condition | agreement rate |
|---|---|
| hybrid (ranked GraphRAG) | 66.1% (382/578) |
| none (no retrieved context) | 65.1% (358/550) |
| raw (unranked full dump) | 60.9% (339/557) |

Hybrid retrieval beat both no-context and raw unranked context on every
column measured — see `results/raw_context_control.md` for the full
breakdown. But the paired, per-scenario version of the hybrid-vs-raw delta
does **not** reach significance at n=25: mean delta +0.050, 95% CI
**[-0.017, +0.114]** (crosses zero), Wilcoxon p=0.15. Report the direction
as real and measured, not the magnitude as settled — guardrail #3. The
neuro-symbolic ablation's hybrid-vs-keyword tag-recall delta, by contrast,
*is* significant: +0.150, 95% CI [+0.060, +0.240], p=0.0055 — see
`results/neurosymbolic_failure_modes.md`.

**Vague/meta-commentary claims are the hardest for both methods to agree
on.** By claim_type: causal/entity_relationship/state cluster around
63-65% agreement, temporal claims reach 76.9% (n=26, small sample), and
`general` claims — process commentary like "the finding is inconclusive" —
are lowest at 60.4%. These are inherently harder to ground since they're
about the investigation process itself, not a checkable fact.

**Retrieval quality itself isn't the bottleneck.** The neuro-symbolic
retrieval benchmark scored 96-100% correct across all three methods on the
tag-hit metric — vector was perfect (25/25); keyword and hybrid each missed
the same single case. The ~36% GPCS-vs-self-consistency disagreement isn't
because relevant evidence can't be found — both can find it — it's a
disagreement in how each method *scores confidence* given evidence both can
retrieve.

**Trust scores are now a real, bimodal signal.** 43.6% of scored claims
land at a hard trust_score of 0.0 (no evidence clears the relevance floor),
and the rest cluster in a 0.6-0.85 band — not the degenerate all-zero or
all-supported distributions the pipeline produced before this session's
fixes.

**The 5-agent architecture does not earn its complexity over a matched-
compute single-LLM baseline — a real, significant negative result.** The
matched-compute control (`results/matched_compute_control.md`) ran the
real 5-specialist-agent consensus system against a single LLM sampled 5
times (self-consistency-checked, same GPCS scorer, same retrieved
evidence — only the architecture differs) across all 25 scenarios. The
single-LLM baseline had a *lower* hallucination rate in 19/25 scenarios:
mean unsupported rate 31.5% vs. the 5-agent system's 44.2%. Paired delta
+0.127, 95% CI [+0.053, +0.201], Wilcoxon p=0.0018 — significant, not
noise. Per guardrail #5 this is reported as measured: on this benchmark,
CloudGraph's gains (if any) don't come from the multi-agent architecture
itself.

## Known limitations

- **n=25 scenarios** — a small sample; treat every number above as having
  wide confidence intervals, not as a precise point estimate. Day 4's
  paired bootstrap CI / Wilcoxon work
  (`internal/planning/7_DAY_SPRINT_CHECKLIST.md`) is the planned way to make this
  rigorous.
- **5.2% of claims lack a GPCS score.** `GraphProvenanceClaimScorer.
  extract_claims()` is called independently by both `self_consistency.py`
  and `report_runner.py`'s GPCS scoring path — two separate LLM calls
  against the same generation text. At nonzero sampling temperature this
  occasionally re-segments claims differently between the two calls, so a
  few claim IDs from self-consistency's pass have no GPCS counterpart. Not
  a correctness bug — those rows are correctly excluded from the agreement
  count, not miscounted — but it modestly shrinks the joined sample. The
  clean fix is to have GPCS reuse self-consistency's already-extracted
  primary-generation claims instead of re-extracting; not yet done.
- Neuro-symbolic retrieval detail is exported data, not a finished
  qualitative analysis — Day 3's failure-mode read is still a judgment
  call for a human reader, not something this report automates.

## Files in `results/`

| File | What it is |
|---|---|
| `claims.csv` | Every claim from every (scenario × context-condition) run, GPCS's `trust_score`/`unsupported` verdict and self-consistency's `recurrence_rate`/`unsupported` verdict side by side. |
| `agreement_crosstab.csv` | `claim_type` × (gpcs_unsupported, self_consistency_unsupported) cross-tabulation. |
| `neurosymbolic_retrieval_detail.csv` | Per-scenario, per-method retrieval detail and tag hit/miss. |
| `excluded_scenarios.json` | Scenario×condition attempts that failed outright (empty — none did). |
| `summary.txt` | The auto-generated headline numbers. |
| `raw_context_control.md` | Dedicated write-up of the raw-vs-hybrid-vs-none context ablation. |
| `neurosymbolic_failure_modes.md` | Qualitative read of where keyword/vector/hybrid retrieval each miss expected evidence. |
| `matched_compute_control.md` | Real 5-agent system vs. matched-compute single-LLM baseline write-up — generated by `scripts/run_matched_compute_control.py`. |
| `matched_compute_raw.csv` | Per-scenario raw numbers backing the matched-compute write-up. |
| `significance_tests.md` | Paired bootstrap CI + Wilcoxon results for all four key deltas — generated by `scripts/paired_bootstrap.py`, re-run it after any change to the underlying CSVs. |
| `logs/llm_logs_*.log` | Concatenated LLM request/response logs from all 5 batches, in scenario order, per service (gitignored — see `.gitignore`). |
| `logs/matched_compute_llm_requests.jsonl` | Every real LLM request/response from the matched-compute control's single-LLM arm (gitignored). |

If this is re-run (e.g. after the extraction-mismatch fix above, or with
more scenarios), replace `results/`'s contents with the new run and update
this README rather than keeping multiple result sets side by side.

## Figures (`experiments/figures/`)

Generated by `scripts/make_figures.py` — script-generated, not hand-edited,
re-run it after any change to the underlying CSVs:

- `retrieval_recall.png` — tag recall by method with 95% bootstrap CI.
  Labeled recall, not F1: the saved retrieval data never tracked false
  positives, and a fresh live re-query was rejected because real
  operational incidents accumulated in Neo4j over this long session now
  pollute keyword search's results for the benchmark scenarios (confirmed
  live) — re-querying now would show retrieval performing worse than what
  the actual report measured. See the script's docstring for the full
  reasoning.
- `unsupported_rate_by_claim_type.png` — GPCS vs. self-consistency vs.
  GPCS-under-raw-context, grouped by claim type.
- `agreement_heatmap.png` — the agreement/disagreement cross-tab as a
  heatmap.

**Seed-fixing:** audited every script from this sprint for local,
Python-side randomness — the only one is `scripts/paired_bootstrap.py`'s
bootstrap resampling, already seeded (`seed=42`). There's nothing else to
fix: every other source of run-to-run variation is the LLM provider's own
sampling temperature, which isn't locally seedable through these APIs.
