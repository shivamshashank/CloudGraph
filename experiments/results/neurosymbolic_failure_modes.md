# Neuro-symbolic retrieval ablation — qualitative failure-mode read

**Question.** Re-framing the three existing retrieval modes by their
symbolic/neural character — `keyword` (near-pure symbolic/lexical),
`vector` (near-pure neural/semantic), `hybrid` (neuro-symbolic: vector +
graph proximity + recency) — does the neuro-symbolic mode actually
outperform its symbolic and neural halves, and on what kind of cases?

**Method.** All 25 scenarios × 3 methods (75 rows,
`experiments/results/neurosymbolic_retrieval_detail.csv`). A method scores
"correct" on a scenario if it retrieves at least half of the scenario's
expected tags. This is a much easier bar to fail than the claim-level GPCS
scoring — retrieval only needs to surface *roughly* the right evidence, not
ground every individual assertion — so a near-ceiling result here is
expected and doesn't contradict the ~64% claim-level agreement reported in
`experiments/README.md`.

## Result

| method | class | correct | avg n_results |
|---|---|---|---|
| `vector` | neural | **25/25 (100%)** | 5.0 |
| `keyword` | symbolic | 24/25 (96%) | 4.0 |
| `hybrid` | neuro-symbolic | 24/25 (96%) | 5.0 |

**Sanity check (guardrail #5): hybrid does not clearly beat keyword or
vector on this dataset.** It ties keyword and loses to vector outright.
Per the checklist's own instruction, we report this honestly rather than
adjusting the harness to flatter hybrid, and lean on Day 2's GPCS result
(`experiments/README.md`) as the stronger, more novel contribution — this
ablation's real finding is the qualitative pattern below, not "hybrid
wins."

## The one true failure

Every method that missed the "correct" bar failed on the same case:

- **scenario-15** (`rate_limit;user;http_429;requests`) — `keyword` and
  `hybrid` both recovered only `user`, missing `rate_limit`, `http_429`,
  and `requests` entirely. `vector` recovered `rate_limit;user`, missing
  only `http_429;requests`.

`http_429` is a numeric-code-style tag (an HTTP status code embedded in a
string) — none of the three methods fully resolved it, but `vector` got
closer, catching the semantically-related `rate_limit` where `keyword`
found nothing beyond the generic `user`. **Semantic search generalizes past
exact tokens better than lexical matching, as expected** — but neither
solves numeric/status-code-style evidence well.

## Partial misses (still scored "correct," but instructive)

Beyond the one true failure, the *complete* set of expected tags was rarely
recovered even in "correct" rows — 27 of the 75 rows missed at least one
tag while still clearing the ≥50% bar. This is where the symbolic/neural
distinction shows up most clearly:

- **`keyword` misses concentrate on paraphrased or synonym-shifted
  concepts**, not missing entities — e.g. scenario-01 caught `oom;payment`
  but missed `memory;killed` (the literal string "OOMKilled" doesn't
  contain "memory" or "killed" as separate substrings); scenario-03 missed
  `utilization;latency` despite catching `cpu;frontend`; scenario-10 missed
  `transaction` despite catching `deadlock;postgres;lock`. This is exactly
  the predicted symbolic failure mode: keyword search can't bridge a
  concept to its synonym or generalization.
- **`vector` has fewer and different partial misses** — e.g. scenario-14
  caught `mongodb;latency;recommendation` (getting `latency`, which
  `keyword` missed) but still missed `read`; scenario-20 missed
  `resolution;internal` on all three methods identically, suggesting that
  particular tag pair just isn't well-represented in the seeded evidence
  text for any retrieval mode to find, not a method-specific weakness.
- **`hybrid` doesn't clearly correct `keyword`'s specific misses.**
  Scenario-04: `keyword` missed only `backoff`; `hybrid` missed
  `image_pull;backoff` — *more* than keyword, not less. Scenario-07:
  `keyword` missed `137;exit`; `hybrid` missed `crashloop` instead — a
  different miss, not a strict improvement. This is consistent with the
  earlier GPCS threshold-calibration finding (`experiments/README.md`,
  bug 4) that `hybrid`'s recency-decay term can suppress otherwise-relevant
  evidence — a plausible mechanism for why combining vector + graph
  proximity + recency doesn't uniformly dominate vector alone here, though
  confirming that mechanism specifically would need a dedicated ablation
  (dropping the recency term) that's out of scope for this pass.

## Conclusion

At the retrieval-quality level (can the right evidence be found at all),
all three methods are strong (96-100%) and the differences are marginal —
this confirms the `experiments/README.md` conclusion that retrieval isn't
where GPCS-vs-self-consistency disagreement comes from. Where the methods
*do* differ is in **which specific tags they miss**: keyword fails on
paraphrase/synonym gaps, vector generalizes past those but still struggles
with numeric/code-style tags, and hybrid — on this dataset — doesn't
clearly combine their strengths, plausibly due to its recency-decay term.
With n=25 and only one true failure case, this pattern is suggestive, not
statistically established; treat it as a hypothesis for a larger-sample
follow-up, not a settled result.
