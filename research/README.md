# Research

Four documents. They answer a different question from the rest of the
repository: not *what was built and measured* — that is
[`experiments/`](../experiments/) and [`dissertation/`](../dissertation/) —
but **what is worth doing next, and why it would be novel**.

This is the seed material for a PhD proposal and for the related-work and
future-work sections of any paper.

| Document | What it holds |
|---|---|
| [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md) | 18 candidate research questions scored on novelty, feasibility, publication potential, and effort, with a status table recording which the 36-scenario run closed |
| [`RESEARCH_GAPS.md`](RESEARCH_GAPS.md) | CloudGraph against the literature across eight areas — GraphRAG, multi-agent systems, adaptive RAG, KG reasoning, long-context, AIOps RCA, diagnosis calibration, neuro-symbolic — with gap size versus tractability |
| [`NOVEL_CONTRIBUTIONS.md`](NOVEL_CONTRIBUTIONS.md) | Five candidate contributions, each with a **pre-registered falsification criterion** written before measurement, and a verdict table judging each against its own criterion |
| [`PROJECT_FLOW_METHODS_AND_CITATIONS.md`](PROJECT_FLOW_METHODS_AND_CITATIONS.md) | Diagram separating this project's own contributions from borrowed, cited technique — source material for the dissertation's contributions section |

## How this relates to the results

The falsification criteria in `NOVEL_CONTRIBUTIONS.md` were written before
any valid run and are kept unedited. Two of the five are now settled, and
both settled *against* the original hypothesis:

- **Contribution 3 (neuro-symbolic framing) is falsified as stated** — vector
  and hybrid retrieval were identical on every measure, so the symbolic graph
  added nothing to retrieval. It remains load-bearing for claim *scoring*.
- **Contribution 2 (GPCS as a distinct family) is not established** — the two
  verifiers differ significantly in strictness, but neither discriminates
  correct claims from incorrect ones on the labelled subset.

Contributions 1, 4, and 5 are untested, not disproved. Contribution 5's
matched-compute control is the cheapest of the three to close.

## Removed on 2026-08-11

- `paper/` and `paper_nora/` (drafts plus the NeurIPS LaTeX tree) — every
  number in them predated the four integrity fixes: `n=25`, `64.0%`,
  `44.2% vs 31.5%`, and repeated "calibrated" claims. To be rewritten from
  `experiments/results/` rather than edited.
- `EXPERIMENT_PLAN.md` — built entirely on the retired 25-scenario authored
  dataset, its five incident categories, and a 100+ scaling target. What was
  executed is recorded in [`experiments/README.md`](../experiments/README.md);
  what was not is carried in the verdict table above.
- `SYSTEM_ARCHITECTURE.md` — proposed a research-track architecture whose
  headline deliverable ("replaces the simulated benchmark") has since been
  built; superseded by [`docs/architecture/`](../docs/architecture/).
- `USER_FLOW_LLM_AND_BENCHMARKS.md` — install-to-benchmark walkthrough,
  superseded by
  [`docs/architecture/system-overview.md`](../docs/architecture/system-overview.md).

All remain in git history.
