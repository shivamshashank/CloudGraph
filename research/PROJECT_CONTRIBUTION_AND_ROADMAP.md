# CloudGraph — contribution, provenance, and the full roadmap to publication

One consolidated answer to: what's mine vs. borrowed, what papers ground
this, and the exact path from where the project stands today to a
dissertation and a journal/workshop submission.

---

## 1. What is your contribution vs. what already existed

Be precise about this distinction — it's what a marker or reviewer will
probe first, and overclaiming is a bigger risk than being accurate.

### Techniques that already existed (you applied/adapted them, didn't invent them)

| Technique | Where it comes from | Where it's used here |
|---|---|---|
| Retrieval-Augmented Generation (RAG) | Lewis et al. 2020 | The baseline "Vector RAG" method |
| GraphRAG | Edge et al. 2024 | The general idea of graph-based retrieval (`GraphRAG` method + `graph_traversal.py`) |
| Multi-agent LLM systems | Guo et al. 2024 survey | The 5-specialist + consensus orchestrator design |
| Self-consistency | Wang et al. 2022 | The `self_consistency.py` recurrence-checking baseline |
| Noisy-OR combination / belief propagation | Classical probabilistic graphical models (Pearl-style Bayesian network inference — foundational AI theory, not one paper) | GCP's method for combining multiple evidence paths into one confidence score |
| Cosine similarity for semantic matching | Standard NLP/IR | Used throughout retrieval, GPCS, and self-consistency |

None of these are secrets — citing them correctly is what makes your work
look grounded, not derivative. Claiming you invented RAG, GraphRAG, or
self-consistency would actively hurt you; citing them and explaining your
specific adaptation is what a strong methodology chapter does.

### What is genuinely yours

1. **The system as a whole.** No one paper describes "GraphRAG + Neo4j +
   Qdrant + 5-specialist multi-agent consensus + GCP + GPCS, applied to
   Kubernetes AIOps RCA." That specific combination, engineered and made to
   work end to end, is your system design — this is the majority of the
   actual work in the repo (the Go CLI, Helm charts, FastAPI services,
   ingestion adapters, UI).
2. **GCP's specific instantiation.** Noisy-OR propagation is borrowed
   theory; the edge weights (`GENERATES=0.95`, `BELONGS_TO=0.80`, etc.), the
   initial-confidence heuristics tuned to Kubernetes log/metric semantics,
   and applying this specifically to K8s topology graphs is your design
   choice, not copied from a paper about Kubernetes (none of your current
   references are about this).
3. **GPCS's path-length trust penalty.** Most of GPCS's formula reuses your
   own existing retrieval signals (semantic similarity, hop-distance —
   already built for `hybrid_ranker.py`, just repointed at claim
   verification). Your own design doc (`HALLUCINATION_SCORING_DESIGN.md`)
   says this explicitly. The **one piece that isn't repurposed** — the
   penalty for long inferential chains reducing trust even when the
   endpoint match is strong — is the actual novel mechanism. This is your
   strongest, most specific, most defensible "I built something new" claim
   in the whole project.
4. **Temporal-aware GraphRAG retrieval.** Per `research/NOVEL_CONTRIBUTIONS.md`
   Contribution 1: canonical GraphRAG (Edge et al. 2024) assumes a static
   graph built once. Your graph is continuously mutating, and your
   retrieval respects temporal windows and recency decay — a genuine,
   documented departure from the source technique, not yet common in the
   GraphRAG literature.
5. **Applying self-consistency as GPCS's head-to-head comparison, in this
   domain.** Wang et al.'s technique itself isn't yours. Using it
   specifically to validate an operational-AIOps hallucination detector,
   with an identical claim extractor for fairness, with a claim-type
   breakdown, is your experimental design — the methodology, not the
   algorithm.
6. **The 6-method ablation ladder.** Not from a specific paper — your own
   evaluation design to show what each pipeline stage actually contributes.

### A real gap to fix before submission

I checked `docs/week-1/references.md` directly — **Wang et al. 2022 (self-consistency)
and the Noisy-OR/belief-propagation grounding for GCP are not in your
reference list yet**, even though both are load-bearing methodological
choices. Add:

- Xuezhi Wang, Jason Wei, Dale Schuurmans, Quoc Le, Ed Chi, Sharan Narang,
  Aakanksha Chowdhery, Denny Zhou. "Self-Consistency Improves Chain of
  Thought Reasoning in Language Models." arXiv, 2022.
  <https://arxiv.org/abs/2203.11171> — verified via direct search, not
  recalled from memory.
- A citation for Noisy-OR / Bayesian belief propagation (e.g. Pearl's
  foundational work on probabilistic graphical models) — I'd suggest
  searching for the specific edition/citation format your department
  expects before finalizing, rather than me picking one blind.

Your existing 6 references (Lewis et al. 2020, Edge et al. 2024, Guo et al.
2024, plus the three closest-competitor RCA papers — MetaRCA, Cui et al.'s
agentic structured graph traversal, Chraim et al.'s graphical causal
reasoning) are already solid and correctly scoped. The comparison against
those three RCA papers (Phase 5 in your roadmap) is still not done — that's
listed below.

---

## 2. Exact steps, start to finish

### Where you actually are right now (verified today)

- **Day 1** (benchmark harness is real, not simulated): done. 5 real bugs
  found and fixed, full writeup in `experiments/notes/day1_real_vs_simulated.md`.
- **Day 2** (GPCS vs self-consistency): infrastructure complete and tested,
  but **only 2 of 25 scenarios have real comparison data** so far — blocked
  by free-tier cloud rate limits (Gemini, then Groq). A local-only Ollama
  detour was tried to remove that ceiling entirely, but real-world CPU
  inference latency made it impractical; the current plan is a
  paid/upgraded-tier API key on a supported cloud provider (OpenAI, Gemini,
  or Meta's Llama API) instead. Full status in
  `research/DAY2_HANDOFF_PROMPT.md`.

### Step by step from here

**Step 1 — Finish Day 2 with a connected cloud provider (next, today/tomorrow).**

- Connect a provider with a paid/upgraded-tier API key via the Settings UI
  (or `POST /api/v1/settings`) — a free tier is what caused Day 2's original
  quota wall.
- Validate on 2-3 scenarios first (confirm the run reliably produces valid
  JSON and doesn't fall back to the rule-based path), then run the full 25
  scenarios. `INTER_SAMPLE_DELAY_SECONDS` in `self_consistency.py` paces
  requests to stay under per-minute rate limits.
- Produces: `experiments/results/day2_claims.csv`,
  `day2_agreement_crosstab.csv`, and the manual disagreement read-through
  (`day2_disagreements.md`) that's still outstanding.

**Step 2 — Days 3-7 of the sprint** (`research/7_DAY_SPRINT_CHECKLIST.md`
has the full detail per day):

- Raw-context control + neuro-symbolic ablation (cheap, reuses existing code).
- Statistical rigor: paired bootstrap CIs, Wilcoxon signed-rank, and the
  matched-compute control — kept in scope; cheap, and close a predictable
  reviewer objection to any comparative or multi-agent claim.
- GCP/GPCS calibration analysis (Brier score, reliability diagrams) —
  **deferred, not in scope for the workshop paper.** Per
  `OXBRIDGE_READINESS.md`'s own framing, this is specifically for
  Oxford/Cambridge uncertainty-quantification-adjacent PhD groups
  ("otherwise this can be deferred to the PhD itself as a first-year
  project seed"); `PUBLICATION_STRATEGY.md` confirms the workshop paper only
  needs the GPCS-vs-self-consistency result, not calibration. Revisit if
  targeting that specific application angle.
- Day 5 figures trimmed to the 3 that Days 1-4's kept results actually need
  (no calibration plots, since no calibration work is done); the full
  latency/cost table, `run_all.sh`, and `requirements-lock.txt`
  reproducibility pass also deferred.
- Repo/docs accuracy pass, minimal API auth fix.
- Consolidate into a citable draft write-up.

**Step 3 — Dissertation writing** (Day 8+, per `TODO.md`'s v1 plan):
Introduction, Literature Review (add the two missing citations above),
Methodology, System Design, Evaluation (this is where all the real numbers
from Steps 1-2 go), Discussion (including the one place results were weaker
than expected — report it honestly, that's what a 95+ mark requires),
Conclusion & Future Work.

**Step 4 — First publication: workshop, not journal, and that's
deliberate.** Per `research/PUBLICATION_STRATEGY.md`'s own sequencing, the
fastest, most defensible first submission is a workshop paper (NeurIPS/
ICLR/ACL-adjacent "Trustworthy AI" or "RAG" workshop) built around the
GPCS-vs-self-consistency result specifically — self-contained, doesn't need
the full 100+-scenario dataset, and gets you a citable artifact before your
Oxbridge application deadlines.

**Step 5 — Second submission, ~1-3 months after the dissertation: the
actual journal/applied-systems-venue target** (IEEE Cloud, NOMS, or
similar). This needs: the dataset scaled from 25 to 100+ scenarios, full
statistical rigor at that scale, and — the piece still missing — **a real
comparison against MetaRCA and Cui et al.'s agentic structured graph
traversal**, your two closest competitors, already in your reference list
but not yet empirically compared against.

**Step 6 (optional, PhD-track, not dissertation-track):** generalizing
beyond Kubernetes, formal calibration of GCP as probabilistic graphical
inference, learned/RL-based retrieval — explicitly deferred per your own
roadmap, this is what a doctoral proposal extends toward, not what you need
before submitting anything.

---

## 3. How the project should continue, practically

Right now: finish Day 2 with a connected cloud provider. After that, work through Days 3-7 in
order — each one is scoped to be completable in the time given, and each
one's output is a specific thing your dissertation's evaluation chapter
will cite directly (see the mapping table at the end of
`research/7_DAY_SPRINT_CHECKLIST.md`). Don't start dissertation prose until
the evidence exists — writing around numbers you don't have yet is how
scope creep happens.
