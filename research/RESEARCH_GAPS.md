# RESEARCH_GAPS.md

## CloudGraph vs. the current research landscape

For each area: what exists in the literature, what CloudGraph has, and where the gap: i.e., the opportunity — sits.

> **Status: v1 complete.** The literature positioning below is unchanged and
> still holds. Three gaps have since been **closed by the 36-scenario
> evaluation**, and the results are recorded inline where they land:
>
> | Gap | Closed by | Outcome |
> |---|---|---|
> | Real evaluation loop (was blocking) | **RQ2** | Closed: every baseline now invokes the real pipeline |
> | Long-context / raw-context control | **RQ3** | Closed: **null**; structure did not beat a raw dump |
> | Neuro-symbolic ablation | **RQ4** | Closed: **negative**; the symbolic component adds nothing to retrieval |
>
> Two closed *against* the design's expectation. The remaining gaps map to
> **RQ5–RQ7** (v2) and the v3 register in
> [`docs/project/ROADMAP.md`](../docs/project/ROADMAP.md). See
> [`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md) for the full seven.

---

### 1. GraphRAG

**Literature.** Edge et al. (2024) build community-summarized entity graphs over a corpus and use hierarchical summarization for global sensemaking queries. Most GraphRAG follow-on work (2024–2026) focuses on static, pre-built knowledge graphs over documents.

**CloudGraph today.** A *temporal, operational* knowledge graph (Neo4j) built from live telemetry, with bounded k-hop traversal and a hand-tuned hybrid ranker fusing vector similarity, hop-distance, and recency.

**Gap.** Almost all published GraphRAG work targets static document corpora. CloudGraph's graph is continuously mutating and time-indexed, which is a genuinely different retrieval regime (queries must respect causal/temporal ordering, not just topical relevance). This "temporal operational GraphRAG" setting is under-explored and is CloudGraph's most defensible point of departure from Edge et al.

### 2. Agentic AI / Multi-Agent Systems

**Literature.** Guo et al. (2024) survey LLM multi-agent systems; common patterns are debate, role specialization, and iterative critique/refinement, generally evaluated on general reasoning or coding benchmarks.

**CloudGraph today.** Five independent specialist *functions* (not agents that communicate) each producing a finding + confidence, aggregated by one of: fixed weighted average, or a single LLM call given all findings as context (no iteration, no debate, no agent-to-agent messages).

**Gap.** There is no actual multi-agent *interaction* in the current system: it is closer to an ensemble of independent classifiers than a multi-agent system. The gap is large but tractable: implementing even one round of cross-agent critique or evidence-sharing and measuring the delta against the current static-ensemble baseline is a clean, publishable comparison that the current codebase is one step away from supporting.

### 3. Retrieval-Augmented Generation / Adaptive Retrieval

**Literature.** Adaptive-RAG and self-RAG lines of work (2023–2025) let a model decide *when* and *how much* to retrieve, or select among retrieval strategies per query, rather than using a fixed pipeline.

**CloudGraph today.** A single fixed formula (`0.5·vector + 0.3·graph + 0.2·recency`) applied identically to every query, with a `method` selector (`keyword`/`vector`/`hybrid`) chosen by the caller, not the system.

**Gap.** No query-adaptive retrieval exists. Given that CloudGraph already logs which method "wins" per incident type in principle (via the existing `score_breakdown`), this is a natural extension: learn or heuristically select retrieval strategy per incident category, and measure whether adaptivity beats the fixed hybrid formula.

### 4. Knowledge Graph Reasoning

**Literature.** KG reasoning research spans embedding-based link prediction, rule mining, and, closest to CloudGraph, probabilistic/soft-logic propagation methods (Markov Logic Networks, probabilistic soft logic) for inferring node states from partial evidence.

**CloudGraph today.** GCP is a hand-weighted, BFS-based Noisy-OR propagation: structurally similar to loopy belief propagation on a small subgraph, but not derived from or benchmarked against that literature, and its edge weights are not learned.

**Gap.** GCP is currently an *ad hoc* instance of a well-studied family (probabilistic graphical inference for evidence combination). The opportunity is to (a) formalize it explicitly as an instance of that family (giving it theoretical grounding and correctness conditions), and (b) replace hand-set weights with weights fit to labeled incidents, then compare against both the current heuristic and an off-the-shelf PSL/MLN baseline.

### 5. Long-Context Reasoning / Tool-Using LLMs / LLM Planning

**Literature.** Long-context work asks whether large context windows can substitute for retrieval; tool-use and planning work studies LLMs that decide which external calls to make and in what order.

**CloudGraph today.** The long-context control has been **run** (RQ3). Agent behavior remains a **fixed** DAG (five specialist calls → one consensus call) rather than a planned or tool-selected sequence.

**Gap — half closed.**

1. ~~A "raw context" / long-context baseline.~~ **Closed by RQ3, and the answer was null.** Hybrid (ranked) context vs. raw (unranked) evidence dump: Δ +0.0240, 95% CI [−0.0280, +0.0773], *p* = 0.302. The interval spans zero: structured graph retrieval did **not** measurably outperform pasting all evidence into context. This is a real finding against the design, not a missing experiment.
2. **Still open.** Allowing the orchestrator to *choose* which specialist agents to invoke and in what order based on early evidence, rather than always running all five: reframing orchestration as a planning problem. Deferred to v3 (`ROADMAP.md`); not in the seven-RQ register.

### 6. Root Cause Reasoning / AI for Systems

**Literature.** MetaRCA (Liang et al., 2026) and agentic structured graph traversal for RCA (Cui et al., 2025) are close, recent competitors: both target graph-based RCA with agentic elements.

**CloudGraph today.** Directly overlaps with this niche. Its own evaluation is now real: 36 RCAEval RE2 cases (`experiments/README.md`), but it has still not been benchmarked against either system or their datasets.

**Gap.** The most direct competitive gap: CloudGraph must, at minimum, cite and ideally reproduce a comparison against these two systems (or their reported numbers on a shared or adapted dataset) to establish it is not redundant with existing 2025–2026 work. This is a literature-positioning risk, not just an implementation gap: a paper submission without this comparison will likely be rejected as incremental.

### 7. AI-Assisted Diagnosis (general, cross-domain)

**Literature.** Diagnosis-under-uncertainty work in clinical AI and industrial fault diagnosis provides methodology (calibration, human-AI trust studies, uncertainty quantification) that AIOps papers rarely adopt.

**CloudGraph today.** Confidence scores exist (GCP root-cause confidence, GPCS trust score) but are never calibrated (no reliability diagrams, no Brier score, no coverage-vs-accuracy curves).

**Gap.** Borrowing calibration methodology from clinical/industrial diagnosis AI is a low-effort, high-credibility addition: it costs little beyond the already-existing confidence outputs and immediately answers "are these confidence numbers meaningful," a question every RCA reviewer will ask.

### 8. Neuro-Symbolic AI

**Literature.** Neuro-symbolic systems combine learned components (LLMs, embeddings) with symbolic structure (graphs, logic rules) and reason about the *interface* between the two: a very active 2024–2026 direction.

**CloudGraph today.** Is, in effect, already a neuro-symbolic system (symbolic Neo4j graph + rule-based edge weights + neural embeddings + LLM reasoning). The ablation has now been **run** (RQ4).

**Gap — closed, and the result is negative.** Mean expected-tag recall across all 36 scenarios: keyword 0.4167, vector **0.6065**, hybrid **0.6065**. Hybrid beats keyword by Δ +0.1898, CI [+0.1157, +0.2685], *p* = 0.0003, the largest effect in the study. But **vector and hybrid are byte-identical on all 36 scenarios** (same expected tags, same hit tags). The entire gain over keyword comes from the embedding component; the symbolic graph contributes **nothing to retrieval** on this benchmark.

The neuro-symbolic framing therefore survives only for claim **scoring**, where the graph is load-bearing (GPCS proximity and hop-decay terms operate over graph structure, not embeddings). That is a narrower and more defensible thesis than the original: *the graph's value in this system is verification, not retrieval.*

---

## Summary table: status after v1

| Area | RQ | Status after the 36-scenario run |
|---|---|---|
| Real evaluation loop (was blocking everything) | **RQ2** | ✅ **Closed.** Every baseline invokes the real pipeline; the fabricated-offset heuristics are gone. |
| GPCS vs. self-consistency baseline | **RQ1** | ✅ **Closed, partly against.** Difference demonstrated (p<0.0001); advantage not — neither verifier tracks correctness. |
| Long-context / raw-context control | **RQ3** | ✅ **Closed — null.** Structure did not beat a raw evidence dump. |
| Neuro-symbolic framing + ablation | **RQ4** | ✅ **Closed — negative.** Vector ≡ hybrid; the symbolic component adds nothing to retrieval. |
| Multi-agent interaction / matched-compute control | **RQ5** | ⏭ **v2.** Control ran only on the pre-fix pipeline; re-run is the cheapest remaining closure. |
| GCP as calibrated probabilistic graphical inference | **RQ6** | ⏭ **v2.** No weight fitting, no reliability diagram, no Brier score. |
| Calibration / uncertainty quantification | **RQ6** | ⏭ **v2.** Same gap; confidence scores exist but are never checked against correctness rates. |
| Claim-type blind-spot stratification | **RQ7** | ⏭ **v2.** Blocked on human labels — 4.2% automatic coverage is too thin to stratify. |
| Temporal/operational GraphRAG framing | — | ⏭ **v3.** Recency term now does real work (spread 0.251), but no with/without ablation was run. |
| Adaptive/learned retrieval policy | — | ⏭ **v3.** Needs a policy layer over existing scorers. |
| Agent-selection as planning | — | ⏭ **v3.** Needs new orchestration logic. |
| Comparison to MetaRCA / agentic graph-traversal RCA | — | ⏭ **v3 — positioning risk.** Cited, not reproduced. A submission claiming superiority over these would need it; v1 claims no such comparison. |

**Reading the table:** four gaps closed, and three of the four closed
against the design's expectation. The two mechanisms the architecture bet on —
graph retrieval (RQ3) and symbolic structure (RQ4), did not pay off, and the
verifier that did behave distinctly (RQ1) cannot be shown to be better aimed.
What survives is narrower and better evidenced than the original programme.
