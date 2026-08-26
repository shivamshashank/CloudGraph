# Experiment 1 — six-scenario RCAEval evaluation

Six RCAEval RE2 scenarios × three context conditions = **18 runs, 661 claims,
zero fallbacks**. Executed 2026-08-20 against a local OrbStack Kubernetes
deployment.

> **Status: pilot.** One sample per cell, six scenarios, and ~15 percentage
> points of run-to-run variance measured on an identical configuration. No
> inferential statistics are reported and none should be quoted from here. See
> the limitations in `results/EXPERIMENT1_FINAL_RESULTS.md`.

## Scenarios

| Scenario | System | Target | Injected fault |
|---|---|---|---|
| `rcaeval-03` | Train Ticket | `ts-order-service` | `cpu_exhaustion` |
| `rcaeval-14` | Sock Shop | `carts` | `memory_exhaustion` |
| `rcaeval-07` | Online Boutique | `checkoutservice` | `disk_saturation` ⚠ |
| `rcaeval-04` | Online Boutique | `checkoutservice` | `network_delay` |
| `rcaeval-29` | Sock Shop | `catalogue` | `packet_loss` |
| `rcaeval-18` | Train Ticket | `ts-auth-service` | `socket_exhaustion` |

Six fault families, two scenarios per system.

⚠ **`rcaeval-07` cannot be solved by any arm.** Its fault metric
(`checkoutservice_diskio`) has no readings before the injection, so
`build_rcaeval_dataset.py` drops it on a NaN baseline and the ground truth never
reaches the model. It is retained because the failure is itself a finding about
benchmark construction, not because it measures pipeline quality.

## Layout

```text
logs/       18 gzipped run logs — the raw evidence. Every number in
            results/ and traces/ is derived from these.
traces/      9 narrative walkthroughs: three scenarios × three conditions.
            Derived, illustrative. Traces exist for rcaeval-03, -14 and -07
            only; the other three scenarios were run but not narrated.
results/    claims.csv (the analysis substrate) plus the three analysis
            documents and the manifest.
```

### What is raw and what is derived

| Path | Kind | Regenerable by a script in this repo? |
|---|---|---|
| `logs/*.log.gz` | **raw evidence** | **No.** Re-running produces different samples at T=0.8 |
| `results/claims.csv` | derived from logs | **No script ships.** Every field is present in the logs, so it can be rebuilt — but by ad-hoc extraction, not a committed tool |
| `results/*.md` | derived analysis | **No script ships.** Written against `claims.csv` by hand |
| `traces/*.md` | derived narrative | **No script ships.** Written by hand against the logs |

**Only the logs are produced by a committed tool** (`scripts/trace_scenario.py`).
Everything under `results/` and `traces/` was derived from them by hand or by
one-off extraction. Two consequences worth being explicit about:

- **The derivation is reproducible in principle, not by command.** The logs
  carry every field `claims.csv` holds — one `CONSISTENT`/`CONTRADICTED`/
  `UNVERIFIABLE` line, one `TRUST =` line and one `recurrence=` line per claim,
  38 of each for `rcaeval-03/NONE`. Parsing them is deterministic. No parser is
  committed, so there is no `make results` to run.
- **`services/api/scripts/label_claim_correctness.py` will not read this file.**
  It requires a `claim_type` column that `claims.csv` does not carry. It is the
  labeller whose *logic* produced the `correctness_label` values, but it is not
  the tool that produced this CSV.

Treat the logs as the authority. Where a figure in `results/` or `traces/`
disagrees with them, the logs win — and a reader checking a number should grep
the log rather than trusting the derived file.

### `results/claims.csv` — column dictionary

661 rows, one per extracted claim. 16 columns.

| Column | Type | Values |
|---|---|---|
| `scenario_id` | text | `rcaeval-03` … `rcaeval-29` |
| `system` | text | Train Ticket · Sock Shop · Online Boutique |
| `target_entity` | text | the faulted service (given to the system) |
| `injected_fault` | text | held-out fault type |
| `context_condition` | text | `none` · `raw` · `hybrid` |
| `claim_id` | text | `claim-N`, unique **within** a run only |
| `claim_text` | text | **truncated to 52 characters** — full text is in `logs/` |
| `gpcs_trust_score` | float | 0.000–0.713; only **6 distinct values** occur |
| `gpcs_unsupported` | **bool** | `TRUE` / `FALSE` — GPCS flagged it (trust < 0.50) |
| `sc_recurrence_rate` | float | 0.0 · 0.5 · 1.0 — only three values are reachable from 3 samples |
| `sc_unsupported` | **bool** | `TRUE` / `FALSE` — self-consistency flagged it (recurrence < 0.5) |
| `verifiers_agree` | **bool** | `TRUE` / `FALSE` — both verifiers reached the same verdict |
| `joint_verdict` | text | `both_supported` · `gpcs_only_flagged` · `sc_only_flagged` · `both_unsupported` |
| `correctness_label` | text | `consistent` · `contradicted` · `unverifiable` |
| `label_reason` | text | why the labeller decided that |
| `evaluable` | **bool** | `TRUE` / `FALSE` — `correctness_label != unverifiable`. **22 TRUE** |

The four boolean columns use `TRUE`/`FALSE` rather than `1`/`0`, so the file
reads correctly in Excel, R (`read.csv` → logical) and pandas
(`read_csv` → `bool`) without a converter.

**`correctness_label` and the `*_unsupported` columns are different axes.**
The label comes from held-out ground truth; `unsupported` is what a verifier
*said*. The experiment asks whether the second predicts the first — so never
read `gpcs_unsupported = TRUE` as "the claim is wrong".

## Reproducing

The logs cannot be reproduced byte-for-byte: generation runs at temperature 0.8,
and identical configurations were measured to vary by ~15 pp on verifier rates.
What *is* reproducible is the analysis.

```bash
gunzip -k logs/*.gz                       # restore the raw logs
```

To re-run a scenario end to end (requires the cluster and port-forwards):

```bash
cd services/api
AUTH=$(kubectl get secret cloudgraph-neo4j-auth -n cloudgraph-system \
        -o jsonpath='{.data.NEO4J_AUTH}' | base64 -d)
NEO4J_URI=bolt://127.0.0.1:7687 NEO4J_AUTH="$AUTH" \
QDRANT_HOST=127.0.0.1 QDRANT_PORT=6333 \
AGENT_ORCHESTRATOR_URL=http://localhost:8082 \
.venv/bin/python ../../scripts/trace_scenario.py rcaeval-03 hybrid out.log
```

**Scenarios must run sequentially.** `teardown_benchmark_data()` deletes every
`is_benchmark` node without scenario scoping, and `assert_semantic_store_isolated()`
fails if the vector store holds any foreign scenario. Parallel runs break both.

## Pipeline properties

Two properties of the pipeline that produced these logs, both of which affect how
the results should be read:

- **GPCS's semantic term is a constant.** Evidence reaches GPCS through graph
  traversal, which assigns a fixed score (`0.75` within two hops, `0.6` beyond)
  rather than a measured similarity. Trust is therefore determined by graph
  reachability, and takes six distinct values across the 661 claims, 80.8% of
  them exactly `0.000`.
- **Retrieval isolation is enforced at query time.** A `scenario_id` filter on
  both the Neo4j query and the Qdrant search restricts each run to its own
  seeded scenario. Every log prints the store census before and after seeding so
  this is checkable.

`claim_text` in `results/claims.csv` is truncated to 52 characters; full text is
in the logs and traces.

Labelling follows the pre-registered policy in
[`research/LABELLING_POLICY.md`](../research/LABELLING_POLICY.md), including its
recorded deviations.

## Headline results

| | `NONE` | `RAW` | `HYBRID` |
|---|---:|---:|---:|
| Claims | 218 | 241 | 202 |
| GPCS unsupported | 83.5% | 80.1% | 78.7% |
| Self-consistency unsupported | 59.6% | 47.3% | 50.5% |
| Accepted by both | 11.0% | 16.2% | 15.8% |
| Consistent : contradicted | 4 : 3 | 4 : 0 | 3 : 8 |
| Mean specialist prompt | 1,101 ch | 30,655 ch | 13,808 ch |

**No condition wins outright.** `HYBRID` cuts prompt size 55% versus `RAW` and
doubles its evaluable coverage, but has the worst correctness ratio and wins no
scenario. `NONE` is not beaten on correctness.

**The strongest positive result is not in this table:** the seeded commit
red herring reached 102 `RAW` prompts and was rejected as the root cause in
**6 of 6** scenarios, on the graph's own timestamp evidence.

**The binding constraint is coverage — 22 of 661 claims (3.3%) are
adjudicable.** 76.6% of claims are excluded as "not a causal claim" and 20.1%
as "no mechanism identifiable". Both are labeller decisions, not gaps in the
data.
