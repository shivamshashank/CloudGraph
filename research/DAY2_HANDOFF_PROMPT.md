# CloudGraph — Day 2 Handoff Prompt (Self-Consistency vs. GPCS)

Use this as a standalone brief if picking this work up in a fresh session —
it assumes no prior context beyond what's written here.

---

## What CloudGraph is

A GraphRAG-powered AIOps root-cause-analysis (RCA) platform for Kubernetes:
Neo4j knowledge graph + Qdrant semantic store, a 5-specialist multi-agent
investigation pipeline (`services/investigation-engine`), a consensus
orchestrator (`services/agent-orchestrator`), and two named research
mechanisms — GCP (Graph Confidence Propagation) and GPCS (Graph-Provenance
Claim Scoring, an evidence-grounded hallucination detector) — implemented in
`services/api/app/research/`. This is the user's MSc dissertation project,
being hardened this week toward a publishable result and an Oxbridge PhD
application (see `research/OXBRIDGE_READINESS.md`,
`research/PUBLICATION_STRATEGY.md`, `research/7_DAY_SPRINT_CHECKLIST.md`).

## What's been done overall

**Day 1** (complete): fixed three correctness bugs in the benchmark harness
(`services/api/app/research/evaluation.py`) that were fabricating results —
a ground-truth-leaking fallback, a hardcoded hallucination rate, and an
inert GCP step — plus two more real bugs found while verifying the fix live
(a broken hybrid-ranker field mismatch, a dead keyword-search Cypher
query). Full writeup: `experiments/notes/day1_real_vs_simulated.md`.

**Day 2** (in progress — this document is about this): build and run the
GPCS-vs-self-consistency comparison, the sprint's single most citable
result (Contribution 2 in `research/NOVEL_CONTRIBUTIONS.md`).

---

## Day 2 objective

Self-consistency (Wang et al.-style) is the dominant model-internal
hallucination-detection baseline in the literature: generate an answer
multiple times at elevated temperature, flag claims that don't recur across
samples. GPCS is evidence-grounded instead. The dissertation needs a fair,
claim-for-claim comparison of the two on the same generated text, across
the 25-scenario benchmark dataset (`services/api/app/demo/benchmark_dataset.py`).

## How we're testing — the discipline, not just the mechanics

Every claim in this project is verified against real behavior before being
trusted, never assumed:

- **No fabricated data, ever.** If a real LLM-backed generation can't be
  obtained, the scenario is excluded and recorded as excluded
  (`experiments/results/day2_excluded_scenarios.json`) — never silently
  backfilled with a canned or rule-based answer.
- **Every fix is proven against the real system**, not just reasoned about:
  actual `curl` calls to the live orchestrator, actual pytest runs, actual
  before/after numbers. When a fix appeared to work, it was re-tested at
  the full scale it needs to work at before being called done.
- **A `generation_source: "llm" | "rule_based_fallback"` field** was added
  to the orchestrator's consensus response specifically so the self-
  consistency code can detect and reject the deterministic rule-based
  fallback — accepting it as a "sample" would make every claim trivially
  recur at 100%, which is not a measurement of anything.
- **Model/provider claims are checked against the live API**, never
  assumed from documentation or training-data knowledge (this caught a
  dead Gemini model name and a stale placeholder in the Settings UI).

## What's been built (all code complete, tested, working)

1. **`services/api/app/research/self_consistency.py`** —
   `generate_and_score(scenario, n_samples=3, temperature=0.8)`: requests 3
   real generations via the orchestrator, extracts claims with
   `GraphProvenanceClaimScorer.extract_claims` (identical extractor GPCS
   uses, so the comparison is fair by construction), flags a claim
   unsupported if it doesn't recur (cosine similarity ≥ 0.8) in at least
   half of the other generations. Raises
   `SelfConsistencyUnavailableError` — never fabricates — if a real LLM
   generation can't be obtained.
2. **`services/api/app/research/llm_settings.py`** — shared helper reading
   the Settings-UI-configured provider/key/model from Neo4j
   (`GET /api/v1/settings`'s backing store) so the key travels
   UI → Neo4j → here → orchestrator request and never has to be typed into
   a chat session or a terminal env var.
3. **`services/api/scripts/run_day2_self_consistency.py`** — runs both
   GPCS and self-consistency on the same real generation per scenario,
   writes `experiments/results/day2_claims.csv`,
   `experiments/results/day2_agreement_crosstab.csv` (pandas.crosstab by
   claim type), and `day2_excluded_scenarios.json`.
4. **`tests/test_self_consistency.py`** — 4 unit tests (recurring vs. novel
   claim detection, rejection of the rule-based fallback, orchestrator-
   unreachable handling). Full suite: 79/79 passing.
5. **Groq added as a fourth supported LLM provider** (`call_llm` in
   `agent-orchestrator/main.py`, `investigation-engine/main.py`,
   `gpcs.py`, plus a Settings UI dropdown option) — OpenAI-compatible
   endpoint, same pattern as the existing OpenAI/Gemini/Claude branches.
6. **Temperature plumbing** added end-to-end (`call_llm` → `ConsensusEngine
   .resolve_incident` → the `/orchestrate` HTTP handler) — didn't exist
   before Day 2; every provider call was hardcoded to `temperature=0.1`.
7. **Retry-with-backoff** on both `_generate_one_sample` (self-consistency)
   and `_run_agents_step` (Day 1's benchmark) — 3 attempts, increasing
   backoff, only after all attempts fail is a scenario excluded.
8. **Inter-agent pacing** in investigation-engine's `/analyze` handler — a
   configurable delay (`LLM_INTER_AGENT_DELAY_SECONDS`, default 1.5s)
   between each of the 5 specialist LLM calls, only when a real LLM key is
   configured (no-op on the rule-based path).

## Real bugs found and fixed while getting here (not hypothetical — each

confirmed against the live system before and after)

1. `run_hybrid_search`'s vector-hit reshaping silently dropped all
   retrieved content before the ranker saw it (Day 1).
2. `graph_traversal_retriever.retrieve()` return-type mismatch — a latent
   crash bug (Day 1).
3. Dead keyword-search Cypher query, live-product-affecting (Day 1).
4. **Default Gemini model (`gemini-1.5-flash`) was retired** — confirmed
   via a live 404, not assumed. Replaced with the `gemini-flash-latest`
   alias across 3 files.
5. **Investigation-engine crashed uncaught** on `float(llm_res["confidence"])`
   when a real LLM returned a qualitative label ("High") instead of a
   number — this is what looked like "orchestrator unreachable." Fixed
   with a `_coerce_confidence()` helper across 6 call sites in 2 files.
6. **Every relevant timeout was tuned for the instant rule-based fallback**,
   not a real 6-call LLM chain (12s → 90s orchestrator→engine; 6s/25s →
   120s client-side).
7. **x.ai (Grok) vs. Groq mix-up** — the user's first key was genuinely
   valid but for the wrong, non-free provider (`api.x.ai`, requires
   purchased credits, no free tier at all). Diagnosed via a direct API
   call, not assumed.
8. **Settings UI's "credentials never cached on the backend" claim was
   false** — it's stored server-side in Neo4j. Fixed the copy.
9. **Groq's 12K-tokens-per-minute free-tier limit gets burst past** by 6
   sequential LLM calls fired in under 2 seconds — confirmed via
   `x-ratelimit-*` response headers, not guessed. Partially addressed via
   retry backoff + inter-agent pacing (see "still open" below).

---

## Day 2 status: what's actually done vs. left

**Done:**

- All code above: built, unit-tested, verified working end-to-end multiple
  times via direct `curl` calls to the live orchestrator
  (`generation_source: "llm"` with genuine varying model output confirmed
  repeatedly, across Gemini and Groq).

**Not done — this is the real gap:**

- **Only 2 of 25 scenarios have ever produced real comparison data** in any
  single run (from an earlier Gemini-backed run, before its quota was
  exhausted). The most recent full-batch attempt on Groq, run *after* the
  inter-agent pacing fix, excluded **all 25** — including scenario-01/02,
  which had succeeded in an earlier, unpaced run. This is the opposite of
  what the pacing fix should have done, and **is not yet understood** —
  don't assume the pacing fix works at full scale; it hasn't been proven
  to.
- `day2_claims.csv` / `day2_agreement_crosstab.csv` currently reflect only
  6 claims from those 2 scenarios — far too small to be a finding. One
  thing worth re-checking once real data exists at scale: GPCS scored all
  6 of those claims as unsupported (trust score 0.0 uniformly), which is
  suspiciously uniform and may itself be a bug in how GPCS retrieves
  evidence, not a real finding about the system.
- `experiments/results/day2_disagreements.md` (manually reading every
  GPCS-vs-self-consistency disagreement case) — not started, blocked on
  having real data at scale first.

## Immediate next step for whoever picks this up

**Diagnose why the full batch got worse, not better, after adding
inter-agent pacing**, before just re-running it again. Concretely:

1. Check current Groq quota state first (`x-ratelimit-remaining-requests`
   / `x-ratelimit-remaining-tokens` headers on a plain test call) — rule
   out simple exhaustion before assuming it's still a burst issue.
2. The inter-agent pacing (Day 2 item 8 above) only spaces out the 5
   specialist calls *within* investigation-engine. It does **not** pace:
   the gap between investigation-engine finishing and the orchestrator's
   own consensus call firing immediately after; the gap between the 3
   samples within `generate_and_score` (currently only
   `INTER_SAMPLE_DELAY_SECONDS = 2.0`, possibly too short); or the gap
   between scenarios in `run_day2_self_consistency.py`'s main loop
   (currently none at all). Any of these could be the actual remaining
   burst source.
3. Consider running a much smaller batch (e.g. 3-5 scenarios) with verbose
   timing/logging first to actually observe where in the 18-call-per-
   scenario sequence failures happen, rather than committing to another
   full 25-scenario, ~15-minute run blind.
4. Once real data exists for a meaningful number of scenarios (aim for as
   close to 25 as practical), build the disagreement table and finish
   Day 2 per `research/7_DAY_SPRINT_CHECKLIST.md`.

## Key files reference

| File | Purpose |
|---|---|
| `services/api/app/research/self_consistency.py` | Core self-consistency logic |
| `services/api/app/research/llm_settings.py` | Reads Settings-UI-configured LLM config from Neo4j |
| `services/api/scripts/run_day2_self_consistency.py` | Runs the full comparison, writes results |
| `services/agent-orchestrator/main.py` | Consensus LLM call, `generation_source` field, Groq provider |
| `services/investigation-engine/main.py` | 5 specialist LLM calls, inter-agent pacing, confidence coercion |
| `experiments/results/day2_*` | Output artifacts (claims, crosstab, excluded scenarios) |
| `research/7_DAY_SPRINT_CHECKLIST.md` | Full week plan, Day 2 section has the original task list |
