# Experiments

## Current state

**No complete result exists yet.** One clean pilot batch (6 of 36
scenarios) has been run and validated; batches 2-6 have not. Nothing
here is reportable until all 36 are in.

A partial run is not simply a smaller one. Batch is confounded with
fault type by construction — each batch of 6 covers only 2 of the 6
fault types while staying balanced 2/2/2 across the 3 systems — so the
pilot covers CPU and delay faults only, with a single replicate per
system x fault cell. Two independent isolated runs of those same 6
scenarios also moved per-condition concordance by up to 8 points on
generation stochasticity alone, so no per-condition claim survives at
n=6.

Four integrity defects were found and fixed along the way, each of which
had invalidated a full run: ground-truth leakage into the input
observations, a GPCS/self-consistency join by positional id across two
independent LLM extractions, evidence with no graph path receiving full
graph-proximity credit, and cross-scenario contamination of the vector
store. All are regression-tested; see `dissertation/PROGRESS.md` Week 9
and `experiments/batches/_invalid_*/README.md` for the full account.

Anything citing "64.0% agreement", "44.2% vs 31.5%", or any figure from
the archived `_invalid_*` batches is referring to an invalid run. Those
numbers should not be reused. Note also that `agreement` measures
whether GPCS and self-consistency reached the *same* verdict — it is
inter-method concordance, not ground-truth accuracy.

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
unranked), `hybrid` (ranked GraphRAG retrieval) — and for each:

1. Generates 3 sampled RCA analyses and extracts atomic claims from the
   primary one.
2. Scores those claims two independent ways: **self-consistency** (does
   the claim recur across samples?) and **GPCS** (does the claim have
   supporting evidence in the graph, above a calibrated relevance
   floor?).
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

- Selection is deterministic, not sampled — the same 36 cases reproduce
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
| `results/` | Created by a run — currently absent, see "Current state" |
| `figures/` | Created by `scripts/make_figures.py` — currently absent |
