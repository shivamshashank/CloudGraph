# Submission Checklist

Two kinds of item appear below. **Institution-specific** items are marked
🎓 — their exact requirements come from your programme handbook and cannot be
determined from this repository; the boxes are there so nothing is forgotten,
not because the answer is filled in. Everything else is verifiable here.

---

## 1. 🎓 Confirm from the programme handbook first

Fill these in before writing anything, because several of them change the shape
of the document.

- [ ] Maximum word count, and what is excluded (references? appendices? captions?)
- [ ] Required declaration-of-originality wording — use it **verbatim**
- [ ] Whether AI-assistance disclosure is required, and in what form
- [ ] Title page fields: student ID, supervisor name, degree title, month/year
- [ ] Referencing style (the current files use numbered `[n]`; convert if the handbook requires Harvard, APA, or IEEE)
- [ ] Submission format — PDF only, or PDF plus source archive
- [ ] Whether the software artefact is submitted, and how (repository link, tagged release, or uploaded archive)
- [ ] Deadline, submission portal, and late-submission policy
- [ ] Whether a viva or demonstration is part of assessment

## 2. Ethics and data governance

- [x] **No human participants.** No user study, interview, survey, or human
      annotation was conducted. If a human-labelling study is added later
      (recommended in [`DISSERTATION_OUTLINE.md`](DISSERTATION_OUTLINE.md) §8.3),
      it will require ethical review before it starts.
- [x] **No personal data.** All telemetry is synthetic chaos-injection output
      from open-source demo applications. Redaction is documented in
      [`experiments/DATA_PROVENANCE.md`](../experiments/DATA_PROVENANCE.md).
- [x] **Third-party data licensed and attributed.** RCAEval is MIT-licensed,
      covering both code and the authors' datasets; DOI, arXiv ID, retrieval
      date, and licence are recorded in `DATA_PROVENANCE.md`.
- [x] **Raw corpus not redistributed.** The ~65 MB upstream parquet is
      gitignored and regenerated on demand; only derived scenarios are tracked.
- [x] **Credentials redacted** in the logged LLM request/response traces.
- [x] **Repository licensed** — MIT, `LICENSE` at the repository root,
      compatible with RCAEval's MIT terms for the derived data it ships.
- [ ] 🎓 Ethics form submitted or self-certified as exempt, per your handbook
- [ ] Consider adding `CITATION.cff` so the artefact is citable

## 3. Written dissertation

- [ ] All chapters drafted per [`DISSERTATION_OUTLINE.md`](DISSERTATION_OUTLINE.md)
- [ ] Abstract states all three scope boundaries (task shape, corpus, concordance≠accuracy)
- [ ] Every figure and table regenerated from `experiments/`, not retyped
- [ ] Every figure has a caption naming its data source
- [ ] All references resolve, and the ⚠-marked entries in [`REFERENCES.md`](REFERENCES.md) have been independently verified
- [ ] Threats-to-validity section written in full (material is in the outline)
- [ ] Proofread; consistent British/American spelling throughout

## 4. Pre-submission integrity check

Run this list against the finished document. Each item is a mistake that was
made and corrected at least once during the project.

- [ ] No number predating commit `9787fde` is cited anywhere. Search the
      document for `64.0`, `44.2`, `31.5`, and `n=25` — all four belong to
      invalidated runs.
- [ ] The word "calibrated" does not appear describing GPCS or GCP parameters.
- [ ] `agreement` / concordance is never described as accuracy or correctness.
- [ ] The system is never described as identifying *which* service failed.
- [ ] No result is reported broken down by batch (batch is confounded with fault type).
- [ ] The agent count is five, and consensus is described as static aggregation.
- [ ] Claimed capabilities match [`docs/project/STATUS.md`](../docs/project/STATUS.md) — in particular, Tempo was never deployed and traces were not exercised by any scenario.
- [ ] Diagrams shown are only those in `docs/architecture/figures/`; the ten removed in the 2026-08-11 pass depicted unbuilt components.

## 5. Software artefact

- [ ] Repository tagged at the exact commit the dissertation describes
- [ ] `README.md` states what is built versus planned
- [ ] Full test suite green — record the pass count and date in the appendix

```bash
cd services/api && .venv/bin/python -m pytest tests/ -q -n auto
```

- [ ] Benchmark regenerates deterministically from upstream

```bash
cd services/api && .venv/bin/python scripts/build_rcaeval_dataset.py --n-cases 36
```

- [ ] Statistics and figures regenerate from the merged dataset

```bash
cd services/api && .venv/bin/python scripts/paired_bootstrap.py && .venv/bin/python scripts/make_figures.py
```

- [ ] `experiments/results/MANIFEST.json` SHA-256 digests match the shipped files

### Reproduction path for an examiner

1. Install per [`docs/guides/INSTALLATION.md`](../docs/guides/INSTALLATION.md)
   (kubeadm/Rancher + Helm; the Terraform/EKS path in git history is not
   supported).
2. Regenerate the benchmark with the command above — selection is
   deterministic, so the same 36 cases reproduce exactly.
3. Run the evaluation batches — [`testing/report/run_report_batched.sh`](../testing/report/run_report_batched.sh)
   or [`testing/report/run_batches_k8s.sh`](../testing/report/run_batches_k8s.sh);
   end-to-end procedure in [`testing/END_TO_END_RUNBOOK.md`](../testing/END_TO_END_RUNBOOK.md).
4. Merge with [`scripts/merge_reports.py`](../services/api/scripts/merge_reports.py) —
   integrity gates abort on duplicate claims, broken claim joins, or
   ground-truth echo.
5. Regenerate statistics and figures.

**Expected divergence.** Bootstrap resampling is seeded (`seed=42`) and case
selection is deterministic, but the LLM provider's sampling at temperature 0.8
is not seedable through these APIs. Per-condition concordance moved across a
12-point range over four isolated re-runs of identical scenarios, so a
reproduction will land near, not on, the published figures. This is stated as
a limitation rather than concealed.

## 6. Files that constitute the dissertation pack

| File | Purpose |
|---|---|
| [`README.md`](README.md) | Index of this directory |
| [`PROGRESS.md`](PROGRESS.md) | Week 1–8 (+9) checklist, evidence-backed from git |
| [`LITERATURE_REVIEW.md`](LITERATURE_REVIEW.md) | Consolidated review, Chapter 2 source |
| [`REFERENCES.md`](REFERENCES.md) | Consolidated numbered bibliography |
| [`DISSERTATION_OUTLINE.md`](DISSERTATION_OUTLINE.md) | Chapter plan, evidence map, word budget, threats to validity |
| `SUBMISSION_CHECKLIST.md` | This file |

Six files, no subdirectories. The per-week packs and the original 8-week
roadmap were consolidated into these and removed; see `README.md` for where
each one's content went.
