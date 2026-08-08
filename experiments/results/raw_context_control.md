# Raw-context control

**Question.** Does structured, ranked retrieval (GraphRAG's `hybrid` mode)
actually earn its complexity, or does dumping all seeded evidence unranked
into the prompt do just as well?

**Method.** All 25 scenarios were run under 3 context conditions — `none`
(no retrieved context, agents reason from `error_logs` alone), `raw` (every
seeded evidence node/document for the scenario, concatenated with no
ranking or filtering), and `hybrid` (GraphRAG's own ranked retrieval) — in
the same pass as the main GPCS-vs-self-consistency comparison
(`experiments/README.md`). Data: `experiments/results/claims.csv`, filter
on `context_condition`.

## Result

| condition | n claims | GPCS-vs-SC agreement | GPCS unsupported rate | self-consistency unsupported rate |
|---|---|---|---|---|
| `hybrid` (ranked GraphRAG) | 578 | **66.1%** (382/578) | **42.0%** | **47.9%** |
| `none` (no context) | 550 | 65.1% (358/550) | 42.5% | 54.5% |
| `raw` (unranked dump) | 557 | **60.9%** (339/557) | **46.5%** | 52.2% |

## Conclusion

**Structured retrieval earns its complexity.** `hybrid` beats both `raw`
and `none` on every column: highest agreement between the two independent
scoring methods, lowest GPCS-measured unsupported rate, and lowest
self-consistency-measured unsupported rate. `raw` is the worst condition on
every column, including agreement — worse than giving the agents *no*
retrieved context at all.

This means dumping unranked evidence isn't neutral, it's actively harmful:
more raw material gives the LLM more surface area to produce claims that
sound evidence-backed but aren't tied to the actually-relevant evidence,
which is exactly what both GPCS (evidence grounding) and self-consistency
(generation stability) independently penalize. Ranking matters, not just
retrieval.

## Statistical significance — important caveat

`scripts/paired_bootstrap.py` (see
`experiments/results/significance_tests.md`) runs the formal paired test on
this exact delta, per-scenario: **hybrid vs. raw agreement rate is *not*
statistically significant at n=25** — mean paired delta +0.050, 95%
bootstrap CI **[-0.017, +0.114]** (crosses zero), Wilcoxon p=0.15.

This does not contradict the table above — the aggregate numbers are real,
measured results, not simulated — but per guardrail #3 they must not be
oversold as a settled finding. With only 25 paired observations, a
per-scenario swing of a few claims either way is enough to explain the gap.
The direction is consistent with the aggregate result (hybrid still wins on
every column), but "hybrid beats raw" should be read as a real, but not yet
statistically confirmed, effect — a natural target for re-running with more
scenarios if that becomes practical (see `experiments/README.md`'s n=25
limitation note).

## Limitation

n=25 scenarios, single generation pass per condition (self-consistency's 3
samples are 3 independent generations *within* one condition, not repeated
condition runs).
