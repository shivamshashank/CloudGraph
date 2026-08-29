# Research notes

[Repository](https://github.com/shivamshashank/CloudGraph) ·
[Experiment 1](https://github.com/shivamshashank/CloudGraph/tree/main/experiment-1-benchmark)

Two documents supporting the evaluation in
[`experiment-1-benchmark/`](../experiment-1-benchmark/).

| Document | Contents |
|---|---|
| [`LABELLING_POLICY.md`](LABELLING_POLICY.md) | How claim correctness is decided — the rules the labeller applies |
| [`RESEARCH_GAPS.md`](RESEARCH_GAPS.md) | Where this work sits against the literature |
| [`NOVEL_CONTRIBUTIONS.md`](NOVEL_CONTRIBUTIONS.md) | Candidate contributions with their falsification criteria |

## What the evaluation establishes

- **Only 4.8% of generated claims are adjudicable.** 93 of 1,950. The remainder are
  descriptive rather than causal, or name no mechanism the benchmark can settle.
  This bounds what any claim-level verifier can be shown to do on this class of
  benchmark.
- **Graph-temporal evidence can override semantic plausibility.** A seeded commit
  was rejected as the root cause in every scenario, on
  the strength of its timestamp.
- **Graph-provenance scoring behaves differently from a self-consistency
  baseline, at no additional inference cost**, flagging more claims in every run.
- **Ranked retrieval cuts the request payload by 52% against an unranked dump**
  and produces a higher proportion of adjudicable claims.

## What it does not establish

- That graph-provenance scoring is **more accurate**. It is stricter. On 93
  labelled claims the two verifiers differ by one claim.
- That **ranked retrieval improves correctness** over supplying no context at
  all. It does not, on this benchmark.
- Anything about **calibration**. Thresholds are hand-set defaults.
