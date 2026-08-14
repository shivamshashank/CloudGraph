# Experiments

## Current state

**The full 36-scenario run is complete.** All six batches ran on a single
build (`9787fde`, image `sha256:81c4864130e8`) against a dedicated
evaluation collection, with zero exclusions, zero cross-scenario
contamination, zero ground-truth leakage, and zero join defects.

### Findings

**→ [`FINDINGS.html`](FINDINGS.html)** — eight findings with their
evidential status, statistics, diagrams and charts. Open it in a browser.

Headline results, all derived from `results/claims.csv`:

| Result | Effect | 95% CI | p |
|---|---|---|---|
| GPCS flags more unsupported than self-consistency | +0.119 | [+0.073, +0.163] | <0.0001 |
| Neural/hybrid retrieval beats keyword recall | +0.190 | [+0.116, +0.269] | 0.0003 |
| Hybrid vs raw retrieval context (concordance) | +0.024 | [-0.028, +0.077] | 0.302 (null) |

Keyword retrieval scored **0/36** under strict matching: it never once
recovered a complete tag set. Vector and hybrid were **identical on every
measure**, so the graph contributes nothing to retrieval here (it does
contribute to scoring).

### What these results do not establish

`agreement` measures whether GPCS and self-consistency reached the *same*
verdict. It is inter-method concordance, **not ground-truth accuracy** —
both verifiers can be wrong on the same claim and it counts as agreement.

An automatic correctness label (`scripts/label_claim_correctness.py`,
output in `results/correctness_labels.md`) derives right/wrong from
RCAEval's own case metadata for the causal claims where that is possible
(4.2% of the corpus). On that subset **neither verifier discriminates**:
GPCS flags 60.4% of incorrect claims and 61.2% of correct ones, a −0.8 pp
gap; self-consistency 72.6% vs 73.5%, also −0.8 pp. Both precision figures
(0.681) sit exactly on the 68.4% base rate, which is what flagging
everything would score.

So GPCS being *stricter* than self-consistency (a statistically supported
result) is **not** evidence that it is better aimed. Settling that needs
human-labelled correctness on a stratified sample: the most valuable
outstanding piece of work.

Results are scoped to this RCAEval RE2 subset and are not general claims
about Kubernetes root-cause analysis.

### Non-LLM generations in the corpus

Five of the 329 logged investigations returned the deterministic
rule-based fallback instead of reaching the LLM (`generation_source:
"rule_based_fallback"`), in scenarios `rcaeval-02`, `-04`, `-05` (twice)
and `-36`. They produce boilerplate: *"Unusual pattern detected in
telemetry; pod is in state: Failed"*.

None of that text reaches `results/claims.csv`: no claim in the dataset
contains it, so every scored claim came from a real LLM generation. The
fallbacks were secondary self-consistency samples, where they can still
depress a recurrence rate.

`scripts/paired_bootstrap.py` therefore reports the headline delta twice —
once on all 36 scenarios, once with all four affected scenarios dropped:

| | n | delta | 95% CI | p |
|---|---|---|---|---|
| All scenarios | 36 | +0.1185 | [+0.0729, +0.1632] | <0.0001 |
| Excluding fallback-affected | 32 | +0.1255 | [+0.0801, +0.1724] | <0.0001 |

The effect survives and is marginally larger without them, so the result
does not depend on the affected scenarios. Counts and the affected-scenario
list are recorded in `results/MANIFEST.json` under `non_llm_generations`,
and the sensitivity section regenerates from it rather than from a
hardcoded list.

### Compute cost

`MANIFEST.json` distinguishes what the request log actually counts, because
an earlier manifest reported the record count as an LLM-call count and
understated real compute by roughly 6x:

| Field | Value | Meaning |
|---|---|---|
| `n_investigation_requests` | 329 | Logged records — one POST to the orchestrator each |
| `n_specialist_agent_calls` | 1,645 | Five specialists per investigation |
| `n_consensus_calls` | 329 | One consensus call per investigation |
| `n_agent_llm_calls` | 1,974 | Specialist + consensus |

GPCS claim extraction and scoring are additional and not counted in that
total. Model: `muse-spark-1.2-contributor` (provider `meta`), temperature
0.8, one model throughout — no cross-model comparison was run.

### Known limitations in the current data

- Per-condition concordance moved across a **12-point range** over four
  isolated re-runs of the same six scenarios (temperature 0.8), so
  single-batch condition comparisons are noise.
- The shipped retrieval `correct` flag reads 36/36 for all three methods
  and is saturated by construction; use `strict_correct` and `recall`
  from the merged CSV instead.
- Three fault types (`delay`, `loss`, `mem`) score 0/6 strict because
  their expected tags use vocabulary absent from the seeded telemetry —
  a benchmark-label mismatch, not a retrieval failure.

Four integrity defects invalidated earlier runs: ground-truth leakage,
an index-based claim join, unearned graph-proximity credit, and
cross-scenario vector contamination. All are now regression-tested; see
`dissertation/PROGRESS.md` Week 9. Anything citing "64.0% agreement" or
"44.2% vs 31.5%" refers to an invalid run and must not be reused.

## Benchmark

Real telemetry only — 36 scenarios derived from chaos-injected failures
in **RCAEval RE2**, where each case is a fault that actually occurred in
a running Kubernetes system (Online Boutique, Sock Shop, Train Ticket).

| | |
|---|---|
| Cases | 36 — exactly 2 per (system × fault-type) cell |
| Systems | Online Boutique 12, Sock Shop 12, Train Ticket 12 |
| Fault types | cpu, memory, disk, delay, loss, socket — 6 each |
| Per case | ~26 observations: metric before/after deltas across ~8 services, plus real container log lines |
| Source | RCAEval (MIT, Zenodo DOI 10.5281/zenodo.14590730) |

Full provenance — selection algorithm, derivation rules, licence,
citation, per-case table, checksum — is in
[`DATA_PROVENANCE.md`](DATA_PROVENANCE.md).

A hand-authored synthetic benchmark was previously used alongside this
and has been removed. Its incidents were written rather than observed,
so results on it could not speak to real telemetry, and its inputs had
to be authored too — which is how the leak went unnoticed. Git history
retains it.

### Scope limitation

RE2 covers six fault types, all resource or network. It contains no
config errors, security events, deployment failures, DNS faults, or
certificate expiry. Results from this benchmark are scoped to **resource
and network faults in microservice systems**, not Kubernetes incidents
in general. RCAEval RE3 (code-level faults) is the natural way to widen
this later.

### Task shape

`target_entity` is set to the faulted service, so the system is told
which entity is affected and must diagnose **why**. This measures
fault-type diagnosis, **not** root-cause service localisation. Results
must not be described as "the system found the culprit service."

## Generating the benchmark

```bash
cd services/api
.venv/bin/python scripts/build_rcaeval_dataset.py --n-cases 36
```

Raw parquet (~65MB) lands in `experiments/rcaeval_data/` and is
gitignored; the derived scenarios
(`services/api/app/demo/rcaeval_dataset_generated.json`) are tracked, so
the benchmark reproduces without vendoring the source corpus.

## What the run produces

`cloudgraph report` runs each scenario under three retrieval-context
conditions — `none` (no retrieved context), `raw` (all seeded evidence,
unranked), `hybrid` (ranked GraphRAG retrieval). For each condition:

1. Generates 3 sampled RCA analyses and extracts atomic claims from the
   primary one.
2. Scores those claims two independent ways: **self-consistency** (does
   the claim recur across samples?) and **GPCS** (does the claim have
   supporting evidence in the graph, above a **fixed** relevance floor of
   0.30?). The floor is not calibrated: it was set by inspecting live
   query score distributions, and no held-out fitting has been done. The
   0.50 trust threshold is likewise a default, not a fitted cutoff.
3. Separately runs a neuro-symbolic retrieval benchmark
   (keyword=symbolic, vector=neural, hybrid=neuro-symbolic).

The matched-compute control (`scripts/run_matched_compute_control.py`)
is a separate run: the real 5-agent system versus a single LLM sampled
the same number of times, both given identical retrieved evidence and
scored by the same GPCS instance.

## Evaluation-integrity guarantees

Each of these was a live defect, fixed and pinned by regression tests
(`tests/test_evaluation_integrity.py`, `tests/test_rcaeval_dataset.py`):

| Guarantee | Enforced by |
|---|---|
| Ground-truth claims never reach the system as input | `test_no_ground_truth_leakage_into_observations` |
| Observations span many services, not just the faulted one | `test_observations_span_multiple_services` |
| Recency actually discriminates between evidence | `test_staggered_timestamps_produce_distinct_recency` |
| GCP reports 0.0, not a confident default, when it cannot compute | `test_evaluation_step_scores_zero_not_confident` |
| Matched-compute arms share one retrieval fetch | `test_supplied_retrieval_results_are_used` |
| A missing dataset fails loudly rather than running over nothing | `test_missing_data_raises_rather_than_returning_empty` |

## Reproducibility

- Selection is deterministic, not sampled: the same 36 cases reproduce
  exactly.
- Bootstrap resampling is seeded (`seed=42` in
  `scripts/paired_bootstrap.py`).
- Remaining run-to-run variation is the LLM provider's own sampling
  temperature, which these APIs do not expose a seed for. This is a real
  limitation, not an oversight.
- Every LLM request/response is logged end-to-end during a run
  (credentials redacted); logs are gitignored for size.

## Files

| Path | What it is |
|---|---|
| `DATA_PROVENANCE.md` | Where the data came from, how it was selected and derived |
| `rcaeval_data/` | Raw upstream parquet (gitignored; regenerate on demand) |
| `FINDINGS.html` | Findings and conclusions — open in a browser |
| `results/` | The merged 36-scenario dataset, `MANIFEST.json` carries per-batch provenance |
| `results/significance_tests.md` | Paired bootstrap CIs + Wilcoxon, regenerated by `scripts/paired_bootstrap.py` |
| `figures/` | Charts regenerated by `scripts/make_figures.py` |
