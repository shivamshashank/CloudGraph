# 7-Day Publication & Oxbridge Readiness Sprint

**Goal:** by end of Day 7, CloudGraph has real (not simulated) results, an
honest statistics story, a clean public repo, and a citable draft targeting
a workshop submission — the minimum needed for that, not everything
`research/OXBRIDGE_READINESS.md` lists as blocking a PhD application. Day 8
onward is dissertation writing; this sprint does not touch chapter prose,
only the evidence the chapters will cite.

**Scope discipline:** this compresses `IMPLEMENTATION_ROADMAP.md` Phases 1–2
into 7 days. Phase 4 (calibration) is explicitly deferred, not
in scope — it's specifically for uncertainty-quantification-adjacent PhD
groups, not required for the workshop paper (see Day 4's note). Dataset
scaling to 100+ scenarios, full GCP weight-fitting, and multi-agent
cross-critique are also explicitly **not** in scope — see "Out of scope" at
the bottom. Do not let any day expand into these.

**Non-negotiable guardrails (apply every day):**

1. No number in any result file may come from a hardcoded constant. Every
   metric must trace to an actual function call on real data.
2. Same claim extractor (`GraphProvenanceClaimScorer.extract_claims`) must be
   used for GPCS and self-consistency, or the comparison is invalid.
3. Report n=25 scenarios as a stated small-sample limitation everywhere it's
   used — never hide it, never imply more statistical power than you have.
4. Every figure/table must be regenerable by re-running a script, not
   hand-edited after the fact.
5. If a real number is *worse* than the old simulated one, report it anyway.
   That asymmetry is itself evidence of rigor, not a problem to hide.

---

## Day 1 — Kill the fake numbers, wire GCP into scoring

**Objective.** Fix the three correctness bugs found in the senior-engineer
audit before anything else is measured. Nothing built on top of these numbers
this week is trustworthy until this is done.

- [x] `services/api/app/research/evaluation.py:212` — `_run_agents_step`
      silently falls back to echoing `scenario["ground_truth_claims"]` when
      the agent-orchestrator is unreachable. Change this to raise/log a hard
      failure instead. A benchmark run must either use real orchestrator
      output or visibly report "orchestrator unavailable" — never a number
      computed from leaked ground truth. **Done.**
- [x] `services/api/app/research/evaluation.py:242` —
      `_BASELINE_UNSUPPORTED_RATES` hardcodes `hallucination_rate` for 5 of 6
      baselines. Every baseline that generates text (Agents,
      Agents+GCP) must run `GraphProvenanceClaimScorer` on its own real
      output. Baselines that don't generate text (Keyword, Vector, GraphRAG)
      should report `hallucination_rate` as `null`/N/A, not a picked number.
      **Done.**
- [x] `services/api/app/research/evaluation.py:222` — `_run_gcp_step` calls
      `GraphConfidencePropagator().run_propagation()` but discards the
      result. Wire the returned confidence score into the `correct`
      determination for GCP-tier baselines (e.g. require confidence above a
      threshold before counting a `tp` as correct) so the GCP row is
      measurably different from the non-GCP row. **Done** (0.50 threshold,
      matching GPCS's own default — flagged as an uncalibrated first-pass
      constant).
- [x] Start the full stack locally (`services/api`, `agent-orchestrator`,
      `investigation-engine`, Neo4j, Qdrant) so the orchestrator call in
      Day 1's first fix actually succeeds instead of hitting the failure
      path every time.
- [x] Run `python -m pytest services/api/tests` — confirm no regressions.
      75/76 passed, 1 pre-existing unrelated failure isolated and explained
      in `experiments/notes/day1_real_vs_simulated.md` (test-isolation gap:
      mocks Neo4j but not Qdrant, unaffected by today's diff).
- [x] `POST /api/v1/benchmark/run`, capture the response, save raw JSON to
      `experiments/results/day1_real_benchmark.json`.
- [x] Write one paragraph comparing these real numbers to the old
      `BENCHMARK_DATA` constants in `benchmark.py` — saved as
      `experiments/notes/day1_real_vs_simulated.md`.

**Deliverable:** done. Real, sane benchmark numbers with saved output and a
written real-vs-simulated note.

**Unplanned but required fixes made today** (the first real run exposed
these — see `experiments/notes/day1_real_vs_simulated.md` for full detail):
`run_hybrid_search`'s vector-hit reshaping silently zeroed out all
retrieved content before it reached `HybridRanker.rank()` (field-name
mismatch: `detail`/flat keys vs. the ranker's `text`/nested-`metadata`
contract), and a `graph_context.get("nodes", [])` call on what
`graph_traversal_retriever.retrieve()` actually returns (a plain list) was
a live crash waiting to happen. Both fixed.

**New priority item surfaced today — fixed same day, ahead of schedule:**

- [x] `services/api/app/research/evaluation.py:41-56` **and the identical
      live-product query at `services/api/app/main.py:762-783`** —
      `run_keyword_search`'s Cypher did
      `toLower(n.name) CONTAINS toLower($query)`, which required a short
      node field to contain an entire multi-word query sentence and
      therefore never matched. Fixed with word-tokenized matching (split
      the query, check whether any word > 2 chars appears in the node's
      fields). Re-ran the full benchmark after fixing: Keyword Search now
      scores 0.92P/0.67R/0.78F1 (was 0%), and GraphRAG now genuinely
      differs from Vector RAG (0.88P/0.81R vs 0.80P/0.90R — was identical)
      since graph traversal finally has real Pod/Incident seeds to run on.
      Full before/after in `experiments/notes/day1_real_vs_simulated.md`.
      **Open follow-up, not yet decided:** Keyword Search's label filter
      excludes `Log`/`Metric` nodes, where most tag-bearing evidence text
      lives, capping its recall structurally — decide and document whether
      that's an intentional "weak baseline" design choice or should widen.

---

## Day 2 — Self-consistency baseline (the core publishable contribution)

**Objective.** Build the comparison `HALLUCINATION_SCORING_DESIGN.md`
already specifies as "not optional" but was never implemented — this is
Contribution 2 in `NOVEL_CONTRIBUTIONS.md` and the single most citable result
this sprint can produce.

- [x] Add `pandas` and `matplotlib` to `services/api/requirements.txt`.
- [x] Create `services/api/app/research/self_consistency.py`:
  - [x] `generate_and_score(scenario, n_samples=3, temperature=0.8)` — calls
        the real orchestrator LLM path `n_samples` times. **Required adding
        temperature plumbing that didn't exist**: `call_llm` in
        `agent-orchestrator/main.py` had `temperature` hardcoded to `0.1` in
        every provider payload with no parameter to change it — threaded a
        `temperature` param through `call_llm` → `ConsensusEngine.
        resolve_incident` → the `/orchestrate` HTTP handler (`llm_temperature`
        in the request body).
  - [x] Extract claims from each generation using
        `GraphProvenanceClaimScorer.extract_claims` — identical extractor to
        GPCS, verified by construction (same method, same input dict).
  - [x] Recurrence check via the existing `SentenceTransformerEmbedder`
        cosine similarity (threshold 0.8), across generations 2..n.
  - [x] Flags unsupported if recurrence rate < 0.5 across the other
        `n_samples - 1` generations. Returns `None` (not 0.0) for
        `unsupported_claim_rate` when there are no claims to score.
  - [x] **Added a hard safety rail not in the original spec**: a new
        `generation_source: "llm" | "rule_based_fallback"` field on
        `ConsensusEngine`'s response, and `self_consistency.py` raises
        `SelfConsistencyUnavailableError` (excludes the scenario, never
        fabricates) if a generation didn't actually come from the LLM. The
        rule-based fallback is fully deterministic — silently accepting it
        as a "sample" would make every claim trivially recur at 100%,
        which is not a measurement of anything.
  - [x] 4 unit tests (`tests/test_self_consistency.py`), all passing —
        verifies recurring vs. novel claim detection, rejection of the
        rule-based fallback, and orchestrator-unreachable handling.
- [x] `services/api/scripts/run_day2_self_consistency.py` — runs GPCS and
      self-consistency on the same real generation per scenario (seeds/tears
      down telemetry per scenario like Day 1's harness), writes
      `experiments/results/day2_claims.csv`,
      `experiments/results/day2_agreement_crosstab.csv` (via
      `pandas.crosstab`, stratified by claim type), and
      `experiments/results/day2_excluded_scenarios.json` for any scenario
      that couldn't get a real LLM generation. **Smoke-tested end to end
      against all 25 scenarios — runs cleanly, correctly excludes all 25
      with no fabricated data** (see blocker below).
- [x] **Key added via Settings UI (Gemini) — found and fixed four more real
      bugs getting it to actually work, in order of discovery:**
  1. Nothing read the Settings-UI-stored key at all. Added
     `app/research/llm_settings.py` (shared helper reading the same Neo4j
     node `GET /api/v1/settings` uses) and wired it into both
     `self_consistency.py` and Day 1's `_run_agents_step` — the key now
     travels UI -> Neo4j -> here -> orchestrator request, never through a
     chat session or a hand-set env var.
  2. **Default Gemini model was dead.** `gemini-1.5-flash` (hardcoded
     fallback in 3 files: `agent-orchestrator/main.py`,
     `investigation-engine/main.py`, `gpcs.py`) returned `404 Not Found` —
     retired. Verified the real current model list via the API itself
     (didn't guess a replacement) and switched the default to
     `gemini-flash-latest`, an alias Google keeps pointed at their current
     flash model so this doesn't go stale again. Also fixed the misleading
     placeholder text in `settings.html`.
  3. **Investigation-engine crashed uncaught** (`ValueError: could not
     convert string to float: 'High'`) — `run_log_agent` and 4 other
     specialist functions did `float(llm_res["confidence"])` assuming the
     LLM always returns a clean number; Gemini sometimes returned a
     qualitative label instead. This is what was actually causing
     "unreachable orchestrator" symptoms — the engine wasn't down, it
     crashed. Added a `_coerce_confidence()` helper (numeric string ->
     float, qualitative label -> mapped float, anything else -> safe
     default) and replaced all 6 unsafe call sites (5 in
     investigation-engine, 1 in agent-orchestrator's `ConsensusEngine`).
  4. **Timeouts were tuned for the instant rule-based fallback path, not a
     real LLM chain.** The orchestrator chains 5 sequential specialist LLM
     calls + 1 consensus call; its own wait for investigation-engine was
     `12s` (raised to `90s`), and both `self_consistency.py`'s and Day 1's
     `_run_agents_step`'s client timeouts were `25s`/`6s` (both raised to
     `120s`). Added bounded retry (3 attempts) to both call sites too —
     ordinary API flakiness on any 1 of 6 sequential calls shouldn't sour
     an entire sample; each retry is still a real, non-fabricated attempt.
  - [x] Verified the fully-fixed path end to end: a real generation with
        `generation_source: "llm"` and genuine model-authored text was
        obtained more than once during debugging, proving every piece of
        this chain now works correctly.
- [ ] **Currently blocked on something no amount of further debugging fixes:
      the Gemini free-tier daily quota (20 requests/day) is exhausted.**
      Confirmed directly from the API's own error body
      (`RESOURCE_EXHAUSTED`, `limit: 20`,
      `GenerateRequestsPerDayPerProjectPerModel-FreeTier`) — not a guess.
      A full self-consistency run needs ~450 LLM calls (25 scenarios × 3
      samples × 6 sequential calls per sample), ~22x the free daily quota,
      so this was never going to fit regardless of code correctness.
      `experiments/results/day2_excluded_scenarios.json` currently holds an
      honest "all 25 excluded, quota exhausted" record from the last run —
      not fabricated data. **Needs the user to decide**: wait for the daily
      quota reset and run a scaled-down pilot, upgrade to a paid tier, or
      switch provider — see chat for options.
- [ ] Once quota allows a real run: `scripts/run_day2_self_consistency.py`,
      then manually read every disagreement case and label GPCS-right /
      self-consistency-right / both-wrong / ambiguous — save to
      `experiments/results/day2_disagreements.md`.

**Deliverable:** `day2_claims.csv`, the cross-tab, and the hand-annotated
disagreement table — this is effectively the Results section of a workshop
paper in raw form.

---

## Day 3 — Raw-context control + neuro-symbolic ablation (cheap, high value)

**Objective.** Two controls that answer the two questions any reviewer asks
first — "does structure help at all" and "does the graph earn its
complexity" — for near-zero new code, reusing what already exists.

- [ ] **Raw-context control.** For each scenario, pull all evidence nodes in
      the incident window with an unfiltered Cypher query (no ranking/
      filtering) + all matching Qdrant docs, concatenate into one prompt,
      generate RCA text the same way as Day 2, run GPCS + self-consistency on
      it too. Save to `experiments/results/day3_raw_context.csv`.
- [ ] **Neuro-symbolic ablation (Contribution 3, `NOVEL_CONTRIBUTIONS.md`).**
      Using Day 1's real harness, re-run and tag the three existing retrieval
      modes by their symbolic/neural character:
      - `keyword` → near-pure symbolic/lexical
      - `vector` → near-pure neural/semantic
      - `hybrid` → neuro-symbolic
      Don't just compare aggregate F1 — read the *failure cases* per mode and
      categorize qualitatively (e.g. does `keyword` fail on paraphrased
      incidents that `vector` catches; does `vector` fail on multi-hop
      dependency chains that `hybrid`/`keyword`-via-graph catches). Save to
      `experiments/results/day3_neurosymbolic_failure_modes.md`.
- [ ] Sanity-check: if `hybrid` doesn't clearly beat `keyword`/`vector` on
      this dataset, say so — do not adjust the harness to flatter the result
      (guardrail #5). Pivot framing toward Day 2's stronger, more novel GPCS
      result if needed.

**Deliverable:** raw-context comparison table + a qualitative neuro-symbolic
failure-mode table — both drop directly into a results/discussion chapter.

---

## Day 4 — Statistics + matched-compute control (calibration deferred)

**Objective.** Statistical rigor is expected of any empirical ML paper — the
significance testing and matched-compute control below are close to
mandatory for a credible comparative result, and both are cheap. **Full
calibration analysis (Brier score, reliability diagrams) is scoped out of
this pass** — per `OXBRIDGE_READINESS.md`'s own framing, that work is
specifically for Oxford/Cambridge uncertainty-quantification-adjacent PhD
groups, not a workshop-paper requirement:

> "Complete Phase 4's GCP calibration work if targeting
> uncertainty-quantification-adjacent groups; otherwise this can be
> deferred to the PhD itself as a first-year project seed."

`PUBLICATION_STRATEGY.md` confirms the workshop paper only needs "Phase 2"
(the GPCS-vs-self-consistency result itself, Days 1-3) — calibration isn't
on that critical path. Deferred to a later, PhD-application-specific pass
if/when targeting those groups specifically — see
`research/DEFERRED_CALIBRATION_WORK.md` (create when picked back up).

- [ ] `scripts/paired_bootstrap.py` — paired bootstrap CI:

  ```python
  def paired_bootstrap_ci(deltas: np.ndarray, n_resamples=10000, seed=42):
      rng = np.random.default_rng(seed)
      means = [rng.choice(deltas, size=len(deltas), replace=True).mean()
               for _ in range(n_resamples)]
      return np.percentile(means, [2.5, 97.5])
  ```

  Apply to: hybrid-vs-keyword F1 delta, GPCS-vs-self-consistency
  unsupported-rate delta, hybrid-vs-raw-context delta.
- [ ] `scipy.stats.wilcoxon` as a secondary confirmatory test on the same
      paired deltas.
- [ ] Report explicitly: n=25 gives wide CIs — do not overclaim
      significance. This honesty is expected and rewarded in review
      (guardrail #3).
- [ ] **Matched-compute control (cheap slice of Contribution 5).** Run
      Day 2's self-consistency generator at `n_samples=5` (matching the
      5-specialist-agent call count) as a single-LLM baseline, compare its
      accuracy/hallucination-rate to the real 5-agent consensus from Day 1.
      This directly controls for the "more LLM calls = better" confound that
      `NOVEL_CONTRIBUTIONS.md` Contribution 5 flags as usually uncontrolled
      in multi-agent RCA papers. Save to
      `experiments/results/day4_matched_compute.md`. If the agents don't
      beat matched-compute self-consistency, report that honestly — it's a
      valid, publishable negative result per Contribution 5's own framing.
- [ ] Alongside the matched-compute result, record each condition's LLM
      call count (not a full latency/cost table — just enough to show the
      compute was actually matched, since that's the whole point of the
      control and a reviewer will ask).

**Deliverable:** bootstrap CIs + Wilcoxon results, and the matched-compute
control result with its call-count comparison. **Not** in this pass:
calibration plots/Brier scores — deferred, see above.

---

## Day 5 — Necessary figures only (trimmed)

**Objective.** Produce the minimum figures the Day 1-4 results actually need
to be reviewable — not the full reproducibility/polish pass. Trimmed
specifically because calibration (Day 4) is deferred, so its two reliability
diagrams don't exist yet either.

- [ ] `scripts/make_figures.py` (script-generated, not hand-edited):
  1. Bar chart: retrieval F1 by method with bootstrap CI error bars.
  2. Grouped bar chart: unsupported-claim-rate — GPCS vs self-consistency vs
     raw-context, by claim type.
  3. Heatmap: the Day 2 agreement/disagreement cross-tab.
- [ ] Fix all random seeds used across the week's scripts (cheap, and
      undermines every other result here if skipped).

**Explicitly deferred, not required for the workshop submission:** the two
Day 4 calibration reliability diagrams (no calibration work done to plot),
the full latency/cost table across all 9 conditions (the matched-compute
call-count note above covers what's actually load-bearing), pinning
`requirements-lock.txt`, and the `run_all.sh` one-command-reproduction
script. Revisit these if reviewer feedback asks for them, or before the
second (journal/applied-venue) submission where reproducibility scrutiny is
higher.

**Deliverable:** `experiments/figures/*.png` (3 figures, not the original
4) — nothing else from the original Day 5 scope.

---

## Day 6 — Repo/docs accuracy pass + minimal security fix

**Objective.** Make the public-facing artifact match reality exactly. Per
`OXBRIDGE_READINESS.md`: "overstated documentation... is a liability, not
just cosmetic" — this is cheap, unconditional, and high-leverage before
anyone at Imperial or a reviewer opens the repo.

- [ ] `README.md:329` — "React / Vue / Svelte" claim does not match the
      actual static HTML/CSS/vanilla-JS UI in `services/ui/static`. Rewrite
      to describe the real frontend, or add a small real D3 enhancement to
      `topology.js` to make the claim true (rewrite is faster given the time
      budget).
  - [ ] Grep-check the rest of the repo for the same class of drift:
        `grep -rn "LangGraph" --include=*.md .` and fix or annotate as
        historical/superseded everywhere it appears outside
        `docs/week-1/architecture-design.md` (which already has the
        annotation).
- [ ] Add a **"Design Evolution / Deviations from Initial Design"** note
      (README or a new `docs/design-evolution.md`) explicitly covering:
      AWS → Helm/kubeadm, LangGraph → custom HTTP orchestrator, planned SPA →
      static UI. Framed as engineering decisions with reasons, not omissions
      — this becomes a Methodology/Discussion subsection later.
- [ ] **Minimal API auth** (`services/api/app/main.py:77` currently
      `allow_origins=["*"]` with zero auth anywhere, including the settings
      endpoint that stores LLM API keys in Neo4j in plaintext). Add a simple
      API-key header check — this is explicitly scoped as "small effort,
      removes red flags" in `TODO.md`, not full OAuth2 (that's v2/Phase 4+).
- [ ] Update `PROJECT_STATUS.md`, `TODO.md`, and `audit.new.md` to reflect
      what's now actually true after this week (they currently disagree with
      each other and with the code — reconcile all three into one accurate
      status).
- [ ] Commit and push everything from Days 1–6: code fixes, `experiments/`,
      doc fixes. (`run_all.sh`/`requirements-lock.txt` were deferred out of
      Day 5's trimmed scope — nothing to push there yet.)

**Deliverable:** a public repo where every doc claim is checkable against the
code, and no unauthenticated credential-storage endpoint.

---

## Day 7 — Consolidate into a citable draft + Oxbridge outreach package

**Objective.** Turn the week's raw results into a form you can actually cite
in an application or send to a supervisor, and hand off cleanly into
dissertation writing starting Day 8.

- [ ] Write a short (4–8 page) standalone results write-up —
      `paper/gpcs_workshop_draft.md` or `.tex` — covering: motivation, GPCS
      method (formula from `HALLUCINATION_SCORING_DESIGN.md`), self-
      consistency baseline procedure, experimental setup (25 scenarios,
      explicitly stated as a small-scale pilot), results (Days 1–4), and a
      limitations section covering: small n, single domain (Kubernetes),
      hand-set (not learned) GPCS/GCP weights, **no calibration analysis
      performed** (Brier score/reliability diagrams deferred — out of scope
      for this submission, see Day 4) — flagged as future work pointing at
      Phase 3/4 of `IMPLEMENTATION_ROADMAP.md`, no comparison yet
      to MetaRCA/Cui et al. (Phase 5, also future work). This is not a
      polished submission — it's the citable artifact `OXBRIDGE_READINESS.md`
      says is worth more than a promise of future work.
- [ ] Adapt `research/OXBRIDGE_READINESS.md`'s positioning paragraph into a
      1-page research-fit statement, re-angled toward "trustworthy AI" (the
      Frontier AI Lab's actual mission) rather than generic AIOps — lead with
      Day 2's GPCS-vs-self-consistency result as your evidence of feasibility.
- [ ] Update `shivam-shashank.me` to link the cleaned repo and reflect the
      same accurate framing as the README.
- [ ] Final self-check against `research/OXBRIDGE_READINESS.md`'s "pre-
      application checklist" — confirm items 1–3 are now done (real
      evaluation, a citable draft, accurate documentation).
- [ ] Send the CV + research-fit statement + repo link to the Frontier AI Lab
      per the process already discussed (Centre Manager first, optionally
      one targeted researcher). This is a "send a message on your behalf"
      action — do it yourself once you're happy with the draft.

**Deliverable:** a draft write-up, a 1-page fit statement, an updated
personal site, and (if you're ready) the outreach email sent.

---

## What "more ML/AI concepts" means, concretely, in this sprint

Beyond the engineering fixes, this week adds real research-methodology
substance that wasn't in the codebase before:

- **Self-consistency hallucination detection** (Wang et al.-style) as a
  head-to-head baseline for GPCS — Day 2.
- **Neuro-symbolic ablation framing** with qualitative failure-mode analysis,
  not just aggregate metrics — Day 3.
- **Paired bootstrap confidence intervals + Wilcoxon signed-rank testing** —
  Day 4.
- **Matched-compute control** isolating whether multi-agent gains come from
  genuine interaction/specialization or just more LLM calls — Day 4.
- **Calibration analysis** (Brier score, reliability diagrams) for both GCP
  and GPCS confidence outputs — **deferred, not in this sprint's scope**.
  This is the single item `OXBRIDGE_READINESS.md` names as most likely to be
  probed by uncertainty-quantification-adjacent groups specifically, but per
  that same doc it's conditional on targeting those groups — not required
  for the workshop paper this sprint targets. Revisit if/when pursuing that
  specific application angle.
- **Claim-type-stratified analysis** (temporal/causal/entity_relationship/
  state) instead of a single aggregate hallucination number — Day 2.

## Explicitly out of scope for these 7 days (do not attempt)

- Dataset scaling to 100+ scenarios (`IMPLEMENTATION_ROADMAP.md` Phase 3) —
  the 25-scenario dataset is sufficient for a pilot/workshop-scale draft if
  every number is real and n is honestly reported.
- Any calibration analysis at all, lightweight or full (Phase 4) — deferred
  out of this sprint entirely, not just the full weight-fitting version.
  Specifically relevant only for uncertainty-quantification-adjacent PhD
  applications, not the workshop paper this sprint targets — see Day 4.
- Multi-agent cross-critique orchestration mode (Phase 4) — the matched-
  compute control (Day 4) is the cheap substitute this week; the full
  critique round is a Phase 4 item for after dissertation submission.
- Comparison/reproduction of MetaRCA or Cui et al. (Phase 5).
- Any UI/frontend work beyond the Day 6 doc-accuracy fix.
- Any Helm/Kubernetes deployment hardening beyond the Day 6 API-key check.

These remain correctly sequenced in `IMPLEMENTATION_ROADMAP.md` for after
dissertation submission.

## Handoff to dissertation writing (Day 8+)

Everything produced this week maps directly onto `TODO.md`'s V1 dissertation
plan, section 6:

| Dissertation chapter | Sourced from |
|---|---|
| Methodology (real evaluation protocol) | Day 1 note, Day 2–4 scripts |
| Evaluation | `experiments/results/*.csv`, Day 5 figures |
| Discussion (negative results) | Day 4 matched-compute findings |
| Threats to Validity / Limitations | n=25 caveats, hand-set weights, no calibration analysis performed, single-domain scope — stated throughout the week, not written fresh |
| Design Evolution subsection | Day 6 `docs/design-evolution.md` |
| Future Work | The "Out of scope" list above, verbatim |

Nothing in this sprint should require re-deriving evidence once dissertation
writing starts — only prose around what's already measured and saved.
