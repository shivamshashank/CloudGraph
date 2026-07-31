# REPOSITORY_REVIEW.md

## CloudGraph — Repository Review for Research Repositioning

**Reviewer stance:** treating this as a research group intake review, not a code review. The question throughout is not "does it work" but "does it produce a defensible scientific claim."

---

## 1. What the repository actually is today

CloudGraph is a working engineering artifact: a Kubernetes AIOps root-cause-analysis (RCA) tool with

- a Go CLI (`cmd/cloudgraph`) that bootstraps kubeadm, Helm, and the stack,
- a FastAPI backend (`services/api`) that ingests telemetry (Prometheus, Loki, traces, Falco, Git/ArgoCD webhooks) into Neo4j and Qdrant,
- a hand-written **hybrid retrieval ranker** (`retrieval/hybrid_ranker.py`) combining vector similarity, graph hop-distance proximity, and exponential recency decay,
- a **multi-hop Cypher traversal retriever** (`retrieval/graph_traversal.py`) with a temporal window,
- a **custom HTTP-based "multi-agent" orchestrator** (`services/investigation-engine`, `services/agent-orchestrator`) with five rule/LLM-hybrid specialist functions (monitoring, logs, deployment, topology, security) and a weighted-vote or LLM-based consensus step,
- two named, partially-original algorithms: **Graph Confidence Propagation (GCP)** — BFS confidence propagation with Noisy-OR aggregation over typed edge weights — and **Graph-Provenance Claim Scoring (GPCS)** — claim extraction + evidence alignment + a hand-tuned trust-score formula for hallucination auditing,
- a benchmark subsystem (`app/routers/benchmark.py`) that reports precision/recall/F1/hallucination/latency across six "baselines,"
- a static HTML/JS frontend and Helm/kubeadm deployment tooling.

This is a legitimate systems project. It is **not**, in its current form, a research project: there is no experiment that isolates a variable, no comparison against literature baselines run under identical conditions, and — most importantly — the benchmark numbers are not measurements of the system at all.

## 2. Architecture, traced end to end

```text
Telemetry sources → FastAPI ingestion routers → Neo4j (typed graph) + Qdrant (dense vectors)
        ↓
GraphTraversalRetriever (bounded k-hop, temporal filter)  +  SemanticVectorStore.search()
        ↓
HybridRanker: score = 0.50·vector_sim + 0.30·(1/(1+hop)) + 0.20·exp(-ln2·age/halflife)
        ↓
investigation-engine (5 rule/LLM specialist functions) → agent-orchestrator (weighted vote or LLM consensus)
        ↓
GCP (Noisy-OR confidence propagation over the local subgraph)
        ↓
GPCS (claim extraction → evidence realignment → trust score → unsupported_claim_rate)
        ↓
UI (workbench, diagnosis, evidence, benchmark pages) + benchmark router (heuristic scorer, NOT this pipeline)
```

The pipeline above is real and instrumented with unit tests (`test_hybrid_ranker.py`, `test_graph_traversal.py`, `test_gcp.py`, `test_gpcs.py`). What is **not** real is the connection between this pipeline and the reported benchmark numbers: `benchmark.py`'s `_calc_kw`, `_calc_vector`, `_calc_graphrag`, `_calc_agents`, `_calc_gcp`, `_calc_gpcs` functions compute `tp/fp/fn` counts from **fixed offsets over tag-set overlaps** (e.g. `tp = len(tags) + 2` for the "agents" tier, `tp = len(tags) + 4` for GPCS), not from actually invoking retrieval, the orchestrator, GCP, or GPCS against the ten scenarios in `benchmark_dataset.py`. The functions do call the real modules for a side effect (e.g. `propagator.propagate_confidence_scores(...)` on a two-node toy graph) but discard the result and return the synthetic tp/fp/fn regardless. Every baseline's accuracy is monotonically increasing by construction (`GraphRAG + Agents + GCP + GPCS` always wins) — this is a simulated leaderboard, not an evaluation.

## 3. Strengths, from a research-transferability standpoint

1. **Two named algorithmic ideas exist and are documented with formulas**, not just prose: GCP (`docs/research/gcp_design.md`) has an explicit propagation equation, a Noisy-OR aggregation rule, and stated complexity ($O(V\cdot b^d)$). GPCS (`HALLUCINATION_SCORING_DESIGN.md`) has an explicit weighted trust-score formula and, critically, **already specifies a self-consistency baseline as a required comparison** — this is the single most research-literate artifact in the repo, because it anticipates the reviewer objection ("compared to what?") before it's asked.
2. **The retrieval stack is modular and swappable.** `HybridRanker`, `GraphTraversalRetriever`, and `SemanticVectorStore` are decoupled, unit-tested, and expose their scoring rationale (`score_breakdown`, `ranking_rationale`) as structured output — this is exactly the kind of interpretable intermediate representation a research paper needs for qualitative analysis and error taxonomy.
3. **A labeled dataset skeleton exists** (`benchmark_dataset.py`, 25 scenarios with `expected_tags` and `ground_truth_claims`), which is a real, if tiny, seed for a benchmark — most GraphRAG-for-ops papers do not release any dataset at all, so even a small, well-specified one is a differentiator if scaled and its provenance documented.
4. **The system has instrumentation points already wired for research telemetry**: hop distance, per-source score contribution, temporal age, and claim-level provenance are all already computed and returned by the API. Most of the plumbing needed for an ablation study already exists; it is currently just not being *called* by the benchmark.

## 4. Weaknesses that block any research claim today

1. **No real evaluation loop.** As documented above, none of the six "baselines" actually run the corresponding pipeline against the 25 scenarios. This is the single blocking issue — it must be fixed before any other research work has evidentiary value, because every downstream number currently traces back to a hand-picked constant offset, not a measurement.
2. **No comparison to literature baselines.** RAG (Lewis et al. 2020) and GraphRAG (Edge et al. 2024) are cited in `docs/week-1/literature-review.md` as motivation but never implemented as faithful reproductions — "keyword search" and "vector RAG" in the benchmark are not the retrieval-augmented generation systems from the literature, they are simulated tp/fp counters.
3. **GPCS has no baseline comparison implemented**, despite its own design doc mandating one (`HALLUCINATION_SCORING_DESIGN.md`, §3: "Must implement: the self-consistency comparison baseline — this is not optional if GPCS is the centerpiece"). This is flagged in the repo's own `GPCS_UI_Benchmark_Roadmap.md` as an open item.
4. **No statistical testing anywhere in the codebase.** `ROADMAP.md` explicitly lists T-Test/Wilcoxon and confidence intervals as unchecked. With only 25 scenarios, most standard tests will also be underpowered — the dataset itself needs to scale before statistics are meaningful.
5. **The orchestrator uses a custom Python HTTP structure rather than LangGraph.** The framework uses two custom `http.server.BaseHTTPRequestHandler` processes exchanging JSON and a consensus engine, rather than LangGraph as initially proposed in docs. The documentation framing has been aligned to match this custom Python HTTP reality.
6. **GCP and GPCS are engineering heuristics, not learned or theoretically grounded mechanisms.** Edge weights (`GENERATES: 0.95`, `CALLS: 0.75`, ...) and GPCS's semantic/graph/reliability/penalty weights are hand-set constants with no calibration procedure, no sensitivity analysis, and no ground-truth-driven fitting. This is acceptable as a first pass but is currently the weakest link scientifically — a reviewer's first question will be "why these numbers."
7. **No ablations exist in code.** There is no experiment harness that runs the same incident through {keyword, vector, graph, hybrid} × {no-agents, agents} × {no-GCP, GCP} × {no-GPCS, GPCS} and reports the delta. This is the most basic research artifact (a controlled ablation table) and it does not exist.
8. **Sample size and diversity are far below anything publishable.** Twenty-five hand-authored scenarios, five categories, no adversarial or out-of-distribution cases, no multi-incident or concurrent-incident scenarios, and no real production traces. `data-collection-strategy.md` sets a target of 100+ incidents but this has not been executed.
9. **No human evaluation.** Claimed "explainability" and "trust" benefits (RQ3/H3, RQ4/H4) require either human judgment or a validated proxy; neither exists.
10. **Documentation actively overstates the system** in places (README's LangGraph/multi-cloud/production-security claims), which is a serious liability for a dissertation or paper — examiners and reviewers cross-check claims against artifacts, and a mismatch here is worse than having fewer features.

## 5. Engineering work that does **not** advance the research program

These are legitimate, useful, but **not publication-relevant** and should be explicitly deprioritized relative to the research agenda:

- Go CLI polish (`doctor`, `status`, kubeadm bootstrap, port-forward automation)
- Helm chart hardening, RBAC, ingress, multi-environment values files
- Frontend UX (workbench triage panel, log streaming, settings page)
- CI/CD, linting, pre-commit hooks
- API authentication / production security hardening
- Multi-cluster / multi-cloud provider discovery

None of these are wasted effort for a shippable product, but time spent here has zero marginal research value and should be capped.

## 6. AI/ML components that should be expanded (the actual research surface)

1. **Retrieval policy** — currently a fixed linear combination (`0.5/0.3/0.2`) with fixed weights; the clearest research upgrade is making this policy *learned* or *adaptive* rather than hand-tuned (→ RQ on adaptive/learned retrieval).
2. **Multi-agent orchestration** — currently independent specialist functions + a static weighted vote or single LLM consensus call; the clearest upgrade is genuine inter-agent structure (debate, iterative refinement, learned weighting) that can be evaluated against the current static baseline (→ RQ on multi-agent collaboration value).
3. **GCP** — currently a fixed-weight probabilistic propagation; the clearest upgrade is calibrating or learning edge weights and decay from labeled incidents, and formally characterizing the propagation as a message-passing / belief-propagation-adjacent procedure with error bounds (→ RQ on graph-structured uncertainty propagation for RCA).
4. **GPCS** — currently a fixed-weight trust score; the clearest upgrade is (a) implementing the self-consistency baseline the design doc already specifies, and (b) calibrating the trust threshold on a held-out split as also already specified but not implemented (→ RQ on graph-grounded hallucination detection vs. self-consistency).
5. **Benchmark** — currently simulated; the clearest and highest-priority upgrade is making it real, then scaling it, then adding statistical testing (→ prerequisite for every other RQ).

## 7. Bottom line

CloudGraph has the *shape* of a good research testbed — modular retrieval, two named mechanisms with formulas, structured intermediate outputs, and a dataset skeleton — but currently produces no real evidence for any of its claims because its evaluation loop is simulated. The highest-leverage first move, before any new algorithmic work, is replacing the heuristic benchmark with real pipeline invocations (this is also independently required for the dissertation per the user's existing project memory). Everything in this roadmap is sequenced with that constraint first.
