# CloudGraph — Path to 95+ (Distinction-with-Publication-Potential)

**Precondition:** This assumes the 100%-completion checklist's §5 quick wins
(Redis, Tempo route, dependency-map fix, credentials) and a working — not
necessarily brilliant — LLM-backed multi-agent pipeline (§1–2 of that
checklist) are done first. 95+ is not reachable through feature breadth; it
is reached by taking ONE contribution to research-grade depth while keeping
everything else honestly scoped-down. Read the companion file
`CLOUDGRAPH_TO_100_PERCENT.md` for the baseline; this file is the delta on
top of it.

**Centerpiece decision:** RQ3/H3 (graph-grounded hallucination checking) is
the chosen centerpiece. It is the least crowded part of the literature you
already cited, and it is buildable without needing agent sophistication to
be state-of-the-art.

**Explicit de-scoping (do this on purpose, and say so in the dissertation):**

- [ ] Agents do not need to be highly sophisticated LLM reasoners — a
      working, honestly-labeled LangGraph pipeline is sufficient. Do not
      spend the limited remaining time tuning agent prompt engineering.
- [ ] Dataset size target is **60–80 incidents**, not 100+. Depth of labeling
      and category balance matters more than count at this stage.
- [ ] State in the dissertation, explicitly, that these are deliberate scope
      decisions made to prioritize evaluation rigor over feature breadth —
      examiners read intentional scoping as maturity, not as a gap.

---

## 1. Centerpiece: Graph-Provenance Hallucination Scoring (RQ3/H3)

- [ ] Design and name the mechanism (see companion design doc
      `HALLUCINATION_SCORING_DESIGN.md`). It needs a name because a named,
      specified mechanism is a citable artifact; "we checked for
      hallucinations" is not.
- [ ] Implement claim extraction from generated RCA text — break the RCA
      output into atomic factual claims (not just sentences) before scoring
      each one.
- [ ] Implement per-claim graph-provenance scoring: for each claim, find the
      closest supporting node/edge path in Neo4j and Qdrant evidence, and
      compute a distance-weighted trust score (reuse the existing
      `hybrid_ranker.py` distance-decay logic — you already have the
      primitive, it just needs repurposing for claim verification instead of
      retrieval ranking).
- [ ] Implement at least one **comparison baseline** from general NLP
      hallucination-detection literature (e.g., self-consistency sampling —
      generate the RCA twice at different temperatures and check claim
      agreement — or NLI-based entailment checking against retrieved
      evidence text). This is the single highest-leverage addition: showing
      your graph-grounded method beats a generic method is what makes this
      a contribution rather than a feature.
- [ ] Define a clear metric: unsupported-claim rate (% of claims below a
      trust threshold), and report it per baseline (keyword / vector /
      GraphRAG / GraphRAG+agents) so H3 has a real comparison table, not a
      single number.
- [ ] Write the formula and its justification explicitly into
      `docs/week-6/README.md` in the same style as
      `docs/week-4/README.md` — you already have the pattern for
      documenting a scoring formula rigorously, reuse it.

## 2. Ablation Study (operationalizes H1–H4 individually)

- [ ] Run and report results for each of these configurations separately,
      not just the four original baselines:
      - GraphRAG retrieval alone (no agents)
      - GraphRAG + agents (no hallucination check)
      - GraphRAG + agents + hallucination check (full system)
- [ ] For each ablation step, report: top-1/top-3 RCA accuracy, hallucination
      rate, and investigation latency — so each research question has its
      own isolated evidence rather than one aggregate "full system vs.
      baseline" comparison.
- [ ] Explicitly write the interpretation: which component contributed what,
      and where a component's contribution was smaller than expected or
      negative. A component that doesn't help is a real, reportable finding.

## 3. Human Evaluation (single highest-ROI addition for credibility)

- [ ] Recruit 3–5 people with SRE/platform/on-call experience (classmates,
      supervisor's network, HPE colleagues) — does not need to be large.
- [ ] Design a blind rating protocol: for a sample of ~15–20 incidents,
      raters see RCA outputs from different baselines with method labels
      hidden, and score them on a fixed rubric (e.g., usefulness,
      trustworthiness, actionability — 1–5 scale each).
- [ ] Report inter-rater agreement (Cohen's kappa or Krippendorff's alpha).
      Low agreement is itself a finding worth discussing, not a failure.
- [ ] Correlate human ratings against your automated metrics (hallucination
      rate, hybrid score) — showing whether your automated metric tracks
      what a human actually cares about is a strong methodological point.
- [ ] This does not require IRB-level formality for a taught MSc, but do
      document consent and anonymize rater identities in the writeup.

## 4. Evaluation Rigor Upgrades

- [ ] Report effect sizes (Cohen's d or similar) alongside every
      significance test — not just p-values.
- [ ] Report confidence intervals on all headline metrics.
- [ ] Add a held-out generalization split: tune any thresholds (e.g.,
      hallucination trust cutoff, hybrid ranking weights) on one incident
      category, then evaluate cold on a category not used for tuning.
      Report whether performance holds — this directly counters the
      "overfit to your own synthetic incidents" critique before an examiner
      raises it.
- [ ] Add category-level breakdowns to every results table (Kubernetes vs.
      networking vs. security vs. deployment vs. observability) instead of
      only aggregate numbers — this is what lets you write sentences like
      "GraphRAG's advantage was concentrated in networking incidents,"
      which reads as real analysis rather than a mean-and-p-value dump.

## 5. Dataset Discipline (60–80 incidents, done well)

- [ ] Balance categories deliberately (roughly even split across the 5
      categories already defined in `research-methodology.md`), not
      whatever's easiest to synthesize.
- [ ] Write ground-truth labeling criteria down explicitly *before* labeling
      — a short rubric document — so labels are reproducible and you can
      cite inter-labeler consistency if you label with anyone else.
- [ ] Store the dataset, prompts used to generate synthetic incidents (if
      LLM-assisted), retrieved evidence, generated RCA output, and
      evaluation results all in version control — this is already your
      own stated principle in `research-methodology.md`'s reliability
      section; actually do it this time.
- [ ] Explicitly address circularity: your own labels are both ground truth
      and evaluation criteria. Name this as a limitation and mitigate
      partially via the human evaluation in §3, which provides an
      independent signal.

## 6. Threats-to-Validity and Limitations (write this like you mean it)

- [ ] Internal validity: LLM non-determinism across runs — report whether
      you fixed temperature/seed, and if not, report variance across
      repeated runs of the same incident.
- [ ] External validity: single cluster topology, synthetic/injected
      incidents, limited incident categories relative to real production
      AIOps datasets — name these plainly.
- [ ] Construct validity: your definition of "correct root cause" and how
      subjective judgment entered the ground-truth labeling process.
- [ ] Do not bury this in a short paragraph — a full subsection with the
      above four points, each with one or two sentences on how it was
      partially mitigated, reads as far more mature than a hedge-free
      results chapter.

## 7. Writing Standard (every table needs interpretation, not description)

- [ ] For every results table: one paragraph that states what varied, by
      how much, where the effect was concentrated or absent, and why that
      pattern makes sense given the system's design — not just "X performed
      better than Y."
- [ ] In the discussion chapter, state at least one place where the
      **hypothesis failed or the result was weaker than expected**, and
      analyze why. A dissertation with zero disconfirming evidence reads as
      less credible to an examiner than one that shows where the system's
      claims have real boundaries.
- [ ] Explicitly connect the ablation results (§2) and human evaluation (§3)
      back to RQ1–RQ4 point by point in the conclusion — make the examiner's
      job of verifying "did they answer their own research questions" as
      easy as possible.

---

## What NOT to spend time on for the 95+ path

- [ ] Do not chase 100+ incidents if it comes at the cost of §1–3 above.
      60–80 well-labeled incidents with real ablation and human evaluation
      outscores 150 incidents with only aggregate baseline comparisons.
- [ ] Do not over-invest in agent prompt engineering sophistication — a
      working, clearly-documented LangGraph pipeline is enough; its job is
      to produce evidence for the hallucination-checker to score, not to be
      the star of the dissertation.
- [ ] Do not add more baselines beyond the existing four plus the one
      hallucination-detection comparison baseline in §1 — more baselines
      without deeper analysis of the ones you have dilutes rather than
      strengthens the evaluation chapter.
- [ ] Do not skip §6 (limitations) to save time — it is one of the
      cheapest, highest-return sections in the entire dissertation.

---

## Minimum bar to credibly claim 95+ is in reach

- [ ] Named, implemented, and baselined hallucination-scoring mechanism (§1)
- [ ] Full ablation study isolating each component's contribution (§2)
- [ ] Human evaluation with reported inter-rater agreement (§3)
- [ ] Effect sizes, confidence intervals, and a held-out generalization
      split on all headline results (§4)
- [ ] A full, honest threats-to-validity section (§6)
- [ ] At least one clearly stated, analyzed disconfirming or weaker-than-
      expected result in the discussion chapter (§7)

If all six of these exist in the final submission, the dissertation has a
real claim to distinction-with-publication-potential, independent of exact
final incident count or agent sophistication.
