# Research

**CloudGraph v1 is complete.** Four documents. They answer a different question
from the rest of the repository. Not *what was built and measured* (that is
[`experiments/`](../experiments/) and [`dissertation/`](../dissertation/)), but
**what v1 settled, what it did not, and why the remainder is worth doing**.

This is the seed material for a PhD proposal and for the related-work and
future-work sections of any paper.

| Document | What it holds |
|---|---|
| [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md) | The seven research questions defining the project — **four answered in v1** (three of them against the design's predictions), **three deferred to v2** with the work each needs stated |
| [`RESEARCH_GAPS.md`](RESEARCH_GAPS.md) | CloudGraph against the literature across eight areas — GraphRAG, multi-agent systems, adaptive RAG, KG reasoning, long-context, AIOps RCA, diagnosis calibration, neuro-symbolic — with gap size versus tractability |
| [`NOVEL_CONTRIBUTIONS.md`](NOVEL_CONTRIBUTIONS.md) | Five candidate contributions, each with a **pre-registered falsification criterion** written before measurement, and a verdict table judging each against its own criterion |
| [`PROJECT_FLOW_METHODS_AND_CITATIONS.md`](PROJECT_FLOW_METHODS_AND_CITATIONS.md) | Diagram separating this project's own contributions from borrowed, cited technique — source material for the dissertation's contributions section |

## How this relates to the results

The falsification criteria in `NOVEL_CONTRIBUTIONS.md` were written before
any valid run and are kept unedited. Two of the five are now settled, and
both settled *against* the original hypothesis:

- **Contribution 3 (neuro-symbolic framing) is falsified as stated**: vector
  and hybrid retrieval were byte-identical on all 36 scenarios (mean recall
  0.6065 each), so the symbolic graph added nothing to retrieval. It remains
  load-bearing for claim *scoring*. → **RQ4**
- **Contribution 2 (GPCS as a distinct family) is not established**: the two
  verifiers differ significantly in strictness (70.3% vs 57.9% flagged,
  p<0.0001), but neither discriminates correct claims from incorrect ones on
  the labelled subset (both gaps −0.8 pp). → **RQ1**

Contributions 1, 4, and 5 are untested, not disproved. Contribution 5's
matched-compute control (**RQ5**) is the cheapest of the three to close.

### Mapping contributions to the seven research questions

| Contribution | RQ | v1 status |
|---|---|---|
| 2 — GPCS as a distinct family | RQ1 | Answered — difference shown, advantage not |
| — (evaluation-loop prerequisite) | RQ2 | Answered — yes |
| 1 — Temporal Operational GraphRAG | RQ3 | Answered — null vs raw context |
| 3 — Neuro-symbolic ablation | RQ4 | Answered — falsified for retrieval |
| 5 — Multi-agent vs ensemble | RQ5 | Deferred to v2 |
| 4 — Calibrated GCP | RQ6 | Deferred to v2 |
| 2 — blind-spot half | RQ7 | Deferred to v2 — blocked on human labels |

## Removed on 2026-08-11

- `paper/` and `paper_nora/` (drafts plus the NeurIPS LaTeX tree): every
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
