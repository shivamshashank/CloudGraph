# Research notes

Two documents supporting the evaluation in
[`experiment-1-benchmark/`](../experiment-1-benchmark/).

| Document | Contents |
|---|---|
| [`LABELLING_POLICY.md`](LABELLING_POLICY.md) | How claim correctness is decided: the pre-registered rules, and every deviation from them |
| [`RESEARCH_GAPS.md`](RESEARCH_GAPS.md) | Where this work sits against the literature |
| [`NOVEL_CONTRIBUTIONS.md`](NOVEL_CONTRIBUTIONS.md) | Candidate contributions with their falsification criteria |

## What the evaluation establishes

- **Only 3.3% of generated claims are adjudicable.** 22 of 661. The remainder are
  descriptive rather than causal, or name no mechanism the benchmark can settle.
  This bounds what any claim-level verifier can be shown to do on this class of
  benchmark.
- **Graph-temporal evidence can override semantic plausibility.** A seeded commit
  reached 102 prompts and was rejected as the root cause in all six scenarios, on
  the strength of its timestamp.
- **Graph-provenance scoring behaves differently from a self-consistency
  baseline, at no additional inference cost**, flagging more claims in every run.
- **Ranked retrieval reduces prompt size by 55% against an unranked dump** and
  produces a higher proportion of adjudicable claims.

## What it does not establish

- That graph-provenance scoring is **more accurate**. It is stricter. On 22
  labelled claims the two verifiers differ by one claim.
- That **ranked retrieval improves correctness** over supplying no context at
  all. It does not, on this benchmark.
- Anything about **calibration**. Thresholds are hand-set defaults.
