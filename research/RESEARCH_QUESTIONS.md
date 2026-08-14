# Research Questions

**Status: CloudGraph v1 is complete.** Seven research questions define the
project. Four were answered by the 36-scenario RCAEval RE2 evaluation
(`experiments/`); three are deferred to v2 with the work they need stated
explicitly.

Three of the four answers went **against** the design's predictions. They are reported as measured.

| RQ | Question | v1 status |
|---|---|---|
| **RQ1** | Does GPCS behave differently from a self-consistency baseline, and does either flag track claim correctness? | ✅ **Answered — partly against** |
| **RQ2** | Is the measured result real end-to-end, rather than an artefact of a simulated scorer? | ✅ **Answered — yes** |
| **RQ3** | Does graph-structured retrieval beat dumping all evidence into context? | ✅ **Answered — null** |
| **RQ4** | Is the retrieval benefit symbolic-structural or neural-semantic? | ✅ **Answered — against** |
| **RQ5** | Does the five-agent architecture beat a single LLM at matched compute? | ⏭ **Deferred to v2** |
| **RQ6** | Are GCP/GPCS confidence scores calibrated, and would fitted weights beat hand-set ones? | ⏭ **Deferred to v2** |
| **RQ7** | Which claim types are each verifier's blind spot? | ⏭ **Deferred to v2** |

All figures below are from `experiments/results/significance_tests.md` and
`experiments/results/correctness_labels.md`, over n = 36 scenarios and 3,685
extracted claims. Confidence intervals are scenario-clustered paired bootstrap
(10,000 resamples, seed 42); *p*-values are Wilcoxon signed-rank.

---

## Answered in v1

### RQ1 — Does GPCS behave differently from self-consistency, and does either flag track correctness?

**Answered, and the second half is the project's central negative result.**

*Does it behave differently?* Yes, decisively. GPCS flags **70.3%** of claims
unsupported against self-consistency's **57.9%** — Δ **+0.1185**,
95% CI **[+0.0729, +0.1632]**, *p* < 0.0001. The effect survives dropping the
four scenarios containing a rule-based-fallback generation
(Δ +0.1255, CI [+0.0801, +0.1724], n = 32).

*Does either flag track correctness?* **No.** On the 155 claims (4.2%) carrying
automatic correctness labels:

| Verifier | Flags an incorrect claim | Flags a correct claim | Gap |
|---|---|---|---|
| GPCS | 60.4% | 61.2% | **−0.8 pp** |
| Self-consistency | 72.6% | 73.5% | **−0.8 pp** |

Both gaps are negligible and point the wrong way. GPCS is **stricter, not
sharper**. Its extra strictness is not evidence that it is better aimed.

> This is why the project reports *concordance*, never *accuracy*. Two verifiers
> agreeing means they reached the same verdict, not that either was right.

The *which* claim types half of this question is not settled at 4.2% label
coverage. It is carried forward as **RQ7**.

### RQ2 — Is the measured result real end-to-end?

**Answered: yes — and smaller than the earlier simulated numbers implied.**

Every baseline now invokes the real pipeline: real retrieval, real agents, real
GCP, real GPCS. The prior `_calc_kw` / `_calc_vector` fabricated-offset
heuristics are gone.

This was the stated non-negotiable prerequisite: every other RQ's evidence
depends on it. Discharging it required finding and fixing integrity defects in
the project's own pipeline first; earlier results were invalid and were
discarded rather than reinterpreted. See `docs/project/STATUS.md`.

### RQ3 — Does graph-structured retrieval beat a raw long-context dump?

**Answered: null.**

Hybrid (ranked) context vs. raw (unranked) evidence dump, on per-scenario
claim-agreement rate: Δ **+0.0240**, 95% CI **[−0.0280, +0.0773]**,
*p* = **0.302**.

The interval spans zero. Ranked retrieval did not measurably beat handing the
model everything. Reported as a null result rather than omitted.

### RQ4 — Is the retrieval benefit symbolic-structural or neural-semantic?

**Answered, and against the design: entirely neural.**

Mean expected-tag recall across 36 scenarios:

| Method | Mean recall |
|---|---|
| keyword | 0.4167 |
| vector | **0.6065** |
| hybrid | **0.6065** |

Hybrid beats keyword by Δ **+0.1898**, CI **[+0.1157, +0.2685]**, *p* = 0.0003 —
the largest effect in the study. But **vector and hybrid are byte-identical on
all 36 scenarios**: same expected tags, same hit tags, same recall. The graph
component contributes **nothing** to retrieval on this benchmark.

The reading is *embeddings work; the graph does not help retrieve*. The
graph does contribute to claim **scoring** (GPCS proximity and hop-decay terms),
which is a different mechanism and is not evidence for graph retrieval.

> Recall, not F1: the saved data records hit/missed tags but no false-positive
> count. Full F1 would require re-running retrieval with precision tracking.

---

## Deferred to v2

### RQ5 — Does the five-agent architecture beat a single LLM at matched compute?

**Not answered.** The matched-compute control has only ever run against the
pre-fix pipeline, so its numbers are invalid and are not reported. No
`matched_compute_raw.csv` ships with v1, and `paired_bootstrap.py` therefore
emits no fourth section.

**What v2 needs:** re-run `scripts/run_matched_compute_control.py` against the
corrected pipeline — five specialists + consensus versus five independent
single-LLM samples, both scored by the same GPCS instance on the same hybrid
evidence. This isolates architecture from raw compute.

**Cost:** the cheapest remaining closure. One evaluation run, no new code.

### RQ6 — Are GCP/GPCS confidence scores calibrated?

**Not started.** Every threshold and weight in the system is hand-set:

- GPCS: `0.45·semantic + 0.35·proximity + 0.25·reliability − 0.15·(min_hop×0.05)`,
  unsupported below `0.50`, evidence admitted at `MIN_SEMANTIC_EVIDENCE_SCORE = 0.30`
- Hybrid ranker: `0.50·vector + 0.30·proximity + 0.20·recency`
- GCP: typed `EDGE_WEIGHTS` with hop-decay

No data was used to fit any of them. No reliability diagram and no Brier score
exist. **The word "calibrated" must not appear anywhere describing v1.**

**What v2 needs:** reliability diagrams and Brier scores over a labelled set;
then a weight-fitting procedure (e.g. logistic regression on labelled root
causes) compared against the hand-set defaults, plus a sensitivity sweep over
`EDGE_WEIGHTS`.

### RQ7 — Which claim types are each verifier's blind spot?

**Not answered — blocked on labels.** Automatic labelling derives from RCAEval
case metadata and reaches only causal claims: 155 of 3,685 (**4.2%**) are
evaluable; the remaining 3,530 are `unverifiable` and excluded. Claim-type
stratification at that coverage would produce cells too small to interpret.

The five claim types are already tracked in `claims.csv` (`causal`, `state`,
`temporal`, `entity_relationship`, `general`) and plotted in
`experiments/figures/unsupported_rate_by_claim_type.png`, so the machinery
exists — only labels are missing.

**What v2 needs:** human annotation of a stratified sample, targeting enough
labelled claims per type to give usable per-type intervals. This is the
prerequisite for completing RQ1 and the single highest-value unblocking step.

---

## Why these seven

The four answered questions form a closed argument: the pipeline is real
(RQ2), so the comparison is meaningful (RQ1), and the two mechanisms the design
bet on, graph retrieval (RQ3) and symbolic structure (RQ4), did not pay off,
while the verifier that did behave distinctly cannot be shown to be better
aimed (RQ1).

The three deferred questions are exactly the three a reviewer asks on reading
that argument: *is the architecture earning its complexity* (RQ5), *are the
thresholds principled* (RQ6), and *where precisely does each verifier fail*
(RQ7). None can be answered with the data v1 collected; each has a stated,
planned path.

Questions considered and dropped from earlier drafts: inter-agent critique,
query-adaptive retrieval, topology effects on propagation, agent-selection as
planning, competitor reproduction, temporal-graph ablation, RL-tuned ranking,
operator trust studies, cross-category robustness, scale limits, and
cross-domain transfer — are recorded in `docs/project/ROADMAP.md` as v3 and
beyond. They were dropped from the research register because none is reachable
without infrastructure v1 does not have, and listing them here would overstate
the project's scope.
