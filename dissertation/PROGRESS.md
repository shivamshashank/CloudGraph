# CloudGraph — Weekly Progress Log (Week 1 – Week 8)

Written retrospectively from the project's actual git history
(`git log`, first commit 2026-06-09, this log's cutoff 2026-08-08) and the
per-week deliverable packs in `dissertation/week-1/` through
`dissertation/week-4/`, cross-checked against `docs/STATUS.md` (current
implementation status) rather than restated from memory. Where the
project's original 8-week plan (`dissertation/OLD_8_WEEK_ROADMAP.md`)
diverged from what actually got built, that is stated plainly here — this
log reports what happened, not what was planned to happen.

Real elapsed time was closer to 9 weeks than 8 (see Week 8 note at the
end) — the final research/evaluation push ran past the nominal Week 8
boundary. That extension is included here rather than hidden, consistent
with how every other results document in this repository is written.

---

## Week 1 (2026-06-09 – 2026-06-15) — Research & System Design

**Commits:** `df48078` (2026-06-09, repository docs + architecture
diagrams), `8e8118f` (2026-06-10, research scope + 8-week roadmap).

Defined the dissertation's scope and initial research questions, completed
a literature review (GraphRAG, AIOps, multi-agent systems, RCA techniques,
knowledge-graph approaches), and produced the first system design:
high-level architecture, graph schema, agent design, and an AWS deployment
plan (later revised — see Week 2). Also produced the initial open-source
data-collection strategy (Prometheus, Loki, OpenTelemetry, Falco, Argo CD,
Git webhooks) and the dissertation's evidence-collection plan.

**Artifacts:** `dissertation/week-1/literature-review.md`,
`research-methodology.md`, `architecture-design.md`,
`data-collection-strategy.md`, `dissertation-evidence.md`, `references.md`.

## Week 2 (2026-06-16 – 2026-06-22) — Infrastructure & Observability

No commits landed in this exact calendar window — the work that was later
packaged as "Week 2" deliverables (`fcc0b11`, `6fbde78` on 2026-06-23;
`2673643`, `29d6173` on 2026-06-28/30; `97ef50f` on 2026-06-30) actually
lands across late June, immediately after Week 1's design work and a short
gap. Delivered: Terraform scaffolding for AWS EKS (VPC, security groups),
CI/CD pipeline scaffolding, and — the deliverable that stuck — raw
Kubernetes manifests + a custom Helm chart for a sample application with
Prometheus/OTel instrumentation, plus the observability stack itself
(Prometheus, Grafana, Loki, OpenTelemetry Collector).

**Honest deviation from plan, stated at the time (`dissertation/week-2/README.md`):**
the original roadmap's AWS EKS/IAM/VPC provisioning was not actually
executed against a live account — the project pivoted to a Helm +
kubeadm/Rancher deployment path instead, which is what shipped and is what
`docs/guides/INSTALLATION.md` documents today. The Terraform modules exist
in history but were not the path taken forward.

**Artifacts:** `deployments/kubernetes/observability/`,
`deployments/helm/sample-app/`, `deployments/kubernetes/argocd-applications.yaml`,
`tests/observability/observability_test.go`.

## Week 3 (2026-06-23 – 2026-06-29) — Knowledge Graph Development

**Commits:** `4e24ee6`/`fcd25f9` (merge, 2026-06-28), `2673643` (2026-06-28).

Stood up Neo4j (community edition + APOC, via `docker-compose.yml`) and
Qdrant locally, defined the Cypher schema (`graph/schema.cypher` — node
labels, uniqueness constraints, indexes), and built the first ingestion
adapters: Prometheus (metrics), Loki (logs), and a webhook receiver mapping
Git/Argo CD events to `(:Commit)-[:TRIGGERED_BY]->(:Deployment)` edges. The
FastAPI backend (`services/api/app/main.py`) went up with ingestion
endpoints, health checks, and lifespan-managed Neo4j connections. A
`graph_constructor.py` module handles entity linking and dependency
mapping. Verified via `tests/test_graph.py` (schema integrity, payload
mapping, uniqueness constraints, and a 100ms traversal-latency budget).

**Note:** a Tempo tracing adapter was scaffolded as a placeholder for
compatibility but Tempo itself was never deployed in the observability
stack — trace-driven `CALLS` edges fall back to naming-convention
heuristics instead of live trace data. Still true as of `docs/STATUS.md`.

**Artifacts:** `graph/schema.cypher`, `services/api/app/database/neo4j_client.py`,
`services/api/app/adapters/{prometheus,loki,webhooks,graph_constructor}.py`.

## Week 4 (2026-06-30 – 2026-07-06) — GraphRAG Retrieval Engine

**Commits:** `fe003d0`, `09ac3d0`, `2284e41` (2026-07-01); `fb3fa0b`,
`e9bb19c`, `b973329` (2026-07-02); `f3bc134`, `e38c0fa` (2026-07-04);
`fc7569b`, `626f2f1`, `f0521d2` (2026-07-05).

The heaviest infrastructure week. Migrated the CLI from shell scripts to a
proper Go implementation (`cmd/cloudgraph`), restructured the backend into
`services/api`, and built the actual GraphRAG retrieval stack:

- **Embedding pipeline** — local `sentence-transformers/all-MiniLM-L6-v2`
  (384-dim, no hosted embedding API dependency), with a Qdrant primary
  store and a deterministic hashed-file fallback if the model can't load.
- **Graph traversal retrieval** — `GraphTraversalRetriever`, multi-hop
  (1-4 hops, default 2) Cypher traversal from an `Incident`/`Pod` seed
  across `BELONGS_TO`/`RUNS_ON`/`MANAGES`/`GENERATES`/`CALLS`/`DEPENDS_ON`
  and others, with a time-window constraint derived from the incident seed.
- **Hybrid ranking** — `hybrid_score = 0.50·vector_similarity +
  0.30·graph_proximity + 0.20·recency`, all components normalized to
  [0,1], every result carrying a `score_breakdown` for explainability.
- **API surface** — `keyword`/`vector`/`hybrid` all selectable via one
  `method` parameter on `/api/v1/graphrag/search`.

Also migrated the release pipeline to a compiled Go CLI binary and merged a
GitLab-tracked branch back into the primary history (`b973329`).

**Artifacts:** `services/api/app/retrieval/{graph_traversal,hybrid_ranker}.py`,
`services/api/app/services/{semantic_store,embeddings}.py`,
`cmd/cloudgraph/`.

## Week 5 (2026-07-07 – 2026-07-13) — Multi-Agent Framework

**Commits:** `84f0d13`, `f087d19`, `08c2324`, `f0dade5`, `6d3640b`,
`8bff5e0` (all 2026-07-08); `b020537` (2026-07-09 — the largest single
commit of the project: "implement full GraphRAG stack, multi-agent
orchestration, and comprehensive incident investigation UI workbench");
`a7f635c`, `c6829e3` (2026-07-10).

Built the five specialist agents (Monitoring, Log, Deployment, Topology,
Security) in `investigation-engine`, each an LLM-backed reasoner with a
deterministic rule-based fallback when no LLM provider is connected, and
the `ConsensusEngine` in `agent-orchestrator` that aggregates their
findings into one report (title, cause, recommendation, severity,
evidence). Delivered the incident-investigation UI workbench end-to-end
against these live endpoints, and — after an initial pass — removed an
authentication layer that had been added, reverting to the project's
current no-auth-by-default posture (still true; see `docs/STATUS.md`'s
"Still Left" section on API auth).

**Artifacts:** `services/investigation-engine/main.py`,
`services/agent-orchestrator/main.py`, `services/ui/static/diagnosis.html`/`.js`.

## Week 6 (2026-07-14 – 2026-07-20) — RCA & Recommendation Engine

**Commits:** `af76db4` (2026-07-15, Graph Confidence Propagation);
`42af387` (2026-07-17); `e54894a`, `f80f914`, `d1e9945` (2026-07-18);
`6eefca9`, `433de75`, `615d452` (2026-07-19).

Implemented **Graph Confidence Propagation (GCP)** — a Noisy-OR,
BFS-based belief-propagation algorithm over the knowledge graph that
assigns initial confidence to telemetry/evidence nodes and propagates it
along weighted edges with hop-decay, aggregating multiple independent
paths via the Noisy-OR gate (full formulation in `docs/design/GCP_DESIGN.md`).
Wired into `_investigate_pod`. Then, in the same week, initiated the
dissertation completion plan and implemented the first version of
**Graph-Provenance Claim Scoring (GPCS)** — the evidence-grounded claim
verification mechanism that would become the project's central research
contribution (full design in `docs/design/GPCS_DESIGN.md`) — plus the
first benchmark-comparison UI. Also added incident CRUD endpoints and
expanded observability integration.

**Artifacts:** `services/api/app/research/gcp.py`, `services/api/app/research/gpcs.py`,
`docs/design/GCP_DESIGN.md`, `docs/design/GPCS_DESIGN.md`.

## Week 7 (2026-07-21 – 2026-07-27) — Experimental Evaluation (infrastructure)

**Commits:** `c19ea09` (2026-07-22, dynamic benchmark evaluation system,
Redis removal, cluster-metrics UI); `b3fb5f6` (2026-07-25, removed stale
docs/checklists, updated Helm chart dependencies).

Built the *evaluation infrastructure* — the dynamic 6-baseline benchmark
engine (Keyword / Vector / GraphRAG / +Agents / +GCP / +GPCS) and its UI —
though at this point the baselines still used fabricated heuristic offsets
(`_calc_kw`, `_calc_vector`, etc.) rather than real pipeline invocations;
replacing those with real evaluation calls was Week 8/9's work, not this
week's. Redis was fully removed from the chart as an unneeded dependency.

**Artifacts:** `services/api/app/routers/benchmark.py`,
`services/ui/static/benchmark.html`/`.js`.

## Week 8 (2026-07-28 – 2026-08-08) — Real Evaluation, Statistical Rigor, and Dissertation Writing (extended)

**Commits:** `4844d0c` (2026-07-31); `5dcc05f`, `afc733f` (2026-08-01);
`88f81a5` (2026-08-03); `959922f`, `cf5e1d2` (2026-08-05); `dfdbd11`,
`d6ab4ee` (2026-08-06); `6be53d8` (2026-08-07); `277e82f`, `9d1d16a`
(2026-08-08).

This was the longest and most consequential week, and it ran past the
original 8-week boundary rather than finishing inside it — reported here
honestly rather than compressed to fit the plan. Three phases:

**Phase A — LLM integration hardening.** Added LLM settings management and
support for real cloud providers (OpenAI, Gemini, Meta's Llama API),
selected per-request via stored settings rather than an environment
variable. A same-week experiment replaced this with a fully local,
Ollama-only integration (including a `cloudgraph deploy llm` CLI command
and an in-cluster Ollama Helm deployment); this was reverted the same day
(`88f81a5`) after real-world request timeouts made local CPU inference
impractical for this workload — a real, documented design reversal, not a
hidden dead end.

**Phase B — the real (non-heuristic) evaluation.** Replaced every
fabricated benchmark heuristic with real pipeline invocations end-to-end:
`evaluate_scenario()` now genuinely runs retrieval, the 5-agent
orchestrator, GCP, and GPCS for all 6 baselines against the 25-scenario
ground-truth dataset. Built the GPCS-vs-self-consistency comparison (the
project's central H3/RQ1 metric), the 3-condition context ablation
(none/raw/hybrid), the neuro-symbolic retrieval ablation, paired-bootstrap
and Wilcoxon significance testing, and the matched-compute control isolating
whether the 5-agent architecture earns its complexity over a single LLM at
matched compute cost. Getting a valid run required finding and fixing five
real bugs in GPCS's evidence retrieval (truncated entity extraction, an
excluded `Deployment` graph label, a dead semantic-search callback, an
unthresholded vector-search relevance floor, and a `Node`-prefix regex
gap) — full account in `experiments/README.md`.

**Headline results** (25/25 scenarios, 0 excluded; full detail and
statistics in `experiments/README.md` and `experiments/results/`):

> **Correction (Week 9): these specific numbers are known invalid — see
> the Week 9 entry below.** A benchmark data-leakage bug meant every
> condition received the ground-truth answer as its input observation.
> Kept here unedited as an accurate record of what was reported at the
> time; do not cite these numbers going forward.

- GPCS and self-consistency agree on 64.0% of 1,685 scored claims;
  where they disagree, each independently catches cases the other misses.
- Structured GraphRAG retrieval (`hybrid`) beats both no-context and
  unranked raw-context on every measured column, though the hybrid-vs-raw
  delta itself is not yet significant at n=25 (p=0.15) — reported as a
  real but not-yet-settled effect, not oversold.
- **The 5-specialist-agent architecture does not earn its complexity over
  a matched-compute single-LLM baseline** — it hallucinates significantly
  *more* (44.2% vs. 31.5% unsupported-claim rate, Wilcoxon p=0.0018). This
  is the project's most important negative result, reported as measured.

**Phase C — writing and packaging.** Generated the three result figures,
restructured `testing/` into a clean, numbered, reproducible script suite,
removed all VM/hypervisor-specific tooling references in favor of a
generic Linux-server target, eliminated every `pylint: disable` suppression
in the project's own code via genuine refactoring rather than silencing
the linter, reorganized the entire documentation tree into the
publication-oriented structure now in place (`docs/`, `research/`,
`experiments/`, `dissertation/`), and drafted the project's first
submission-ready paper (`research/paper/DRAFT.md`), targeting a currently
open verification-focused workshop.

## Week 9 (2026-08-09 – ) — Benchmark leakage found and fixed

An external code review (via GitHub Copilot's review mode, independently
verified line-by-line against the actual source before acting on it — see
below) identified that the benchmark's `ground_truth_claims` — the answer
key each scenario's diagnosis was supposed to be independently checked
against — was leaking directly into the system's input at three separate
points:

1. `seeding.py` wrote `ground_truth_claims` verbatim into seeded Neo4j
   `Log` nodes and Qdrant documents, and wrote the bare `root_cause`
   string directly into the seeded commit message.
2. `self_consistency.py`'s `_request_one_sample` set
   `error_logs = scenario["ground_truth_claims"]` **unconditionally,
   across all three context conditions** (`none`, `raw`, `hybrid`) — the
   generating agents were handed the answer as their primary observation
   before reasoning about anything.
3. `evaluation.py`'s `_request_agents_step` and
   `self_consistency.py`'s `_build_single_llm_prompt` (the matched-compute
   control's single-LLM arm) did the same.

This plausibly explains a pattern that should have been caught earlier:
the `none` (no-retrieval) condition scored 65.1% GPCS/self-consistency
agreement, nearly identical to `hybrid`'s 66.1% — if retrieval were the
real signal, `none` should have looked meaningfully worse. It didn't,
because the real signal in all three conditions was the leaked
`error_logs`, not retrieval.

**Fix**, verified independently against the source rather than taken on
trust from the review that raised it:

- Added a new `observed_symptoms` field to all 25 scenarios in
  `benchmark_dataset.py` — realistic, low-level telemetry text (log
  lines, metric readings, event/probe output) that requires inference to
  reach the diagnosis, not the diagnosis itself. `ground_truth_claims`
  remains, now used only as a held-out scoring reference, never as
  system input.
- `seeding.py` now seeds `observed_symptoms`, not `ground_truth_claims`;
  the seeded commit message no longer names the root cause.
- All three leakage call sites now read `scenario["observed_symptoms"]`.
- Added two permanent regression tests:
  `test_benchmark_dataset_has_no_ground_truth_leakage` (static: no
  `ground_truth_claims` sentence may appear verbatim in
  `observed_symptoms`) and
  `test_matched_compute_prompt_uses_observed_symptoms_not_ground_truth`
  (runtime: the matched-compute single-LLM prompt is built from the
  right field). Both pass; full suite re-verified green after the change.

### Secondary integrity fixes (same week)

Three further issues found while fixing the leak, each capable of
producing a plausible-looking number that measured nothing:

1. **The recency signal was inert.** Seeding wrote every `Log`/`Metric`
   timestamp as `1600000000` and retrieval passed `reference_time=
   1600000000`, so evidence age was always 0 and the recency term was
   `exp(0) = 1.0` for every candidate. The advertised three-signal
   hybrid score (`0.50·vector + 0.30·graph + 0.20·recency`) was
   effectively two signals plus a constant — in a paper whose central
   question is whether structured retrieval earns its complexity. Fixed:
   timestamps now step back from a per-scenario incident time
   (`scenario_incident_time`), real for RCAEval cases and a fixed
   constant for authored ones. Measured recency spread went from exactly
   0.000 to 0.251 on real data (0.023 on synthetic, where only three
   tightly-clustered evidence items exist — reported as-is rather than
   widening the spacing to manufacture a larger number).
2. **GCP fabricated confidence.** `run_propagation` returned a hard-coded
   `{"root_cause": 0.80}` whenever Neo4j was unreachable, and again when
   no topology was found, and again as the default if the target pod was
   missing from the propagated set. Since `GCP_CORRECTNESS_THRESHOLD =
   0.50`, **an unreachable database scored as a correct GCP result.**
   `_run_gcp_step`'s docstring already claimed it returned 0.0 in that
   case; it never did, because the key was always present. Now raises
   `GraphUnavailableError` and the callers report 0.0.
3. **The matched-compute control's arms didn't share evidence.** The
   script fetched hybrid results once, but `evaluate_scenario` re-queried
   internally, so the two arms used separate fetches while the docstring
   claimed "fetched once, passed to both". `evaluate_scenario` now
   accepts `retrieval_results`; the override deliberately applies only to
   the hybrid path, since the keyword and vector baselines are defined by
   their own retrieval mode.

Nine regression tests (`tests/test_evaluation_integrity.py`) pin all
three, plus the rename of `_run_gcp_step` to public `run_gcp_step`
(matching the earlier `_calculate_fp` → `calculate_fp` precedent rather
than reaching into a private name from tests).

**What this means for the two paper drafts** (`research/paper/DRAFT.md`,
`research/paper_nora/DRAFT.md`) and their compiled sources: every number
in both is now known invalid and both are marked stale at the top of
each file. The experiments need a full re-run on the corrected pipeline
before either paper can be submitted — see the fix-and-resubmit roadmap
for the Aug 25 target (short of the real Aug 29 NeurIPS deadline, to
leave buffer).

---

## What's genuinely left (see `docs/STATUS.md` for the live version)

- Dissertation chapter writing — 0% at the time of this log; only
  structural outlines exist (`dissertation/week-1/`).
- `dissertation/literature_review.md` and `dissertation/references.md` —
  to be written next, consolidating `dissertation/week-1/literature-review.md`
  and `references.md` plus everything cited in `research/paper/DRAFT.md`'s
  related-work section.
- API authentication on `/api/v1/settings` and other routes — a real
  credential-exposure risk now that settings stores a live provider API
  key, not yet addressed.
- Calibration analysis (Brier score, reliability diagrams for GCP/GPCS
  confidence) — deliberately deferred past the workshop-paper deadline,
  earmarked for the PhD-track extension instead.
- Human evaluation of RCA usefulness/trust — not started.
