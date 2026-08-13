# Dissertation pack

Everything needed to write and submit the MSc dissertation for CloudGraph.
Start with the outline; use the checklist last.

## Core documents

| File | What it is |
|---|---|
| [`DISSERTATION_OUTLINE.md`](DISSERTATION_OUTLINE.md) | Chapter-by-chapter plan with an evidence map, word budget, threats-to-validity material, and the writing rules |
| [`LITERATURE_REVIEW.md`](LITERATURE_REVIEW.md) | Consolidated literature review — the source for Chapter 2 |
| [`REFERENCES.md`](REFERENCES.md) | Numbered bibliography matching the review's `[n]` citations |
| [`PROGRESS.md`](PROGRESS.md) | Week 1–8 (+9) progress checklist, every tick backed by a commit hash or file path |
| [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) | Ethics, artefact, reproduction path, and a pre-submission integrity check |

Six files, no subdirectories. That is the whole pack.

## What was removed, and where its content went

The 2026-08-11 consolidation removed sixteen files — the `week-1/`–`week-4/`
packs, `OLD_8_WEEK_ROADMAP.md`, and `demo_guidance.md`. All remain in git
history. Nothing unique was lost:

| Removed | Where its content lives now |
|---|---|
| `week-1/literature-review.md`, `references.md` | [`LITERATURE_REVIEW.md`](LITERATURE_REVIEW.md), [`REFERENCES.md`](REFERENCES.md) — expanded and corrected |
| `week-1/research-methodology.md` | RQ and hypothesis tables at the end of [`PROGRESS.md`](PROGRESS.md), carrying the pre-registered "evidence that would support it" column; its metrics and baselines were superseded by what actually shipped |
| `week-1/architecture-design.md` | [`docs/architecture/`](../docs/architecture/) and [`graph/schema.cypher`](../graph/schema.cypher) |
| `week-1/data-collection-strategy.md` | [`docs/README.md`](../docs/README.md)'s product-versus-evaluated-scope section |
| `week-1/dissertation-evidence.md` | [`DISSERTATION_OUTLINE.md`](DISSERTATION_OUTLINE.md)'s evidence map |
| `week-2/`–`week-4/` READMEs | The per-week checklists in [`PROGRESS.md`](PROGRESS.md), which map the same deliverables to the same paths |
| Three `task-evidence-matrix.md` files | Same — they duplicated their week's README, and Week 1's pointed entirely at a dead `docs/week-1/` path |
| `week-3/ROADMAP.md` | Week-scoped duplicate roadmap; it ticked trace-driven `CALLS` generation, which was never built |
| `OLD_8_WEEK_ROADMAP.md` | Plan-versus-delivery is now recorded by `PROGRESS.md`'s unticked boxes, with reasons |
| `demo_guidance.md` | — removed; write a fresh demo script from `DISSERTATION_OUTLINE.md` Chapter 6 if a demonstration is required |

## Where the results live

Result documents live with the data they describe, not here:

| Location | Contains |
|---|---|
| [`../experiments/FINDINGS.html`](../experiments/FINDINGS.html) | Eight findings with evidential status, statistics, and figures |
| [`../experiments/README.md`](../experiments/README.md) | Benchmark, headline results, integrity guarantees, known limitations |
| [`../experiments/DATA_PROVENANCE.md`](../experiments/DATA_PROVENANCE.md) | Corpus source, licence, selection algorithm, checksums |
| [`../docs/project/STATUS.md`](../docs/project/STATUS.md) | What is implemented and what is not — the scope source of truth |

## Three things to get right

Repeated here because they are the errors this project actually made and had
to correct, and they are the errors an examiner will catch.

1. **Only cite results from commit `9787fde` onwards.** Four integrity defects
   invalidated everything before it. Anything reporting `64.0%`, `44.2% vs
   31.5%`, or `n=25` is from an invalidated run.
2. **`agreement` is concordance, not accuracy.** It measures whether two
   verifiers reached the same verdict; both can be wrong together.
3. **The task is fault-type diagnosis for a known affected service.** The
   benchmark supplies the faulted service. Nothing here demonstrates
   root-cause service localisation.
