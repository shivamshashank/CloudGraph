# RESEARCH_GAPS.md

## CloudGraph vs. the current research landscape

For each area: what exists in the literature, what CloudGraph has, and where the gap: i.e., the opportunity — sits.

> The literature positioning below still holds. The **18-scenario evaluation** in `experiment-1-benchmark/` bears on
> three gaps, and the results are recorded inline where they land:
>
> | Gap | Bears on | Outcome |
> |---|---|---|
> | Real evaluation loop (was blocking) | **RQ2** | Closed: every baseline now invokes the real pipeline |
> | Long-context / raw-context control | **RQ3** | Partly addressed: ranked retrieval is **51.9% cheaper**; no correctness advantage shown |
> | Neuro-symbolic ablation | **RQ4** | **Still open** — no retrieval ablation is run |
>
> The evaluation computes **no inferential statistics**: one sample per cell does
> not support them. Nothing below should be read as a significance
> result. The remaining gaps map to **RQ4–RQ7** and to the limitations section
> of the root `README.md`. See
> [`README.md`](README.md) for what the evaluation establishes.

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

1. ~~A "raw context" / long-context baseline.~~ **Run under RQ3; the answer is a cost win, not an accuracy win.** Hybrid (ranked) context versus a raw unranked dump: **51.9% smaller request payloads** and 11.9% fewer claims (619 vs 703), at verifier concordance of 62.4% against RAW's 61.5%. Structured retrieval is materially cheaper and no worse on agreement. Whether it is *more accurate* is unresolved: on the 93 adjudicable claims HYBRID has the worst consistent:contradicted ratio (12:26) and NONE the best (14:16). No interval or *p*-value is reported, because this pilot does not support one.
2. **Still open.** Allowing the orchestrator to *choose* which specialist agents to invoke and in what order based on early evidence, rather than always running all five: reframing orchestration as a planning problem. Not in the seven-RQ register.

### 6. Root Cause Reasoning / AI for Systems

**Literature.** MetaRCA (Liang et al., 2026) and agentic structured graph traversal for RCA (Cui et al., 2025) are close, recent competitors: both target graph-based RCA with agentic elements.

**CloudGraph today.** Directly overlaps with this niche. Its own evaluation is now real: an 18-scenario RCAEval RE2 evaluation (`experiment-1-benchmark/README.md`), but it has still not been benchmarked against either system or their datasets.

**Gap.** The most direct competitive gap: CloudGraph must, at minimum, cite and ideally reproduce a comparison against these two systems (or their reported numbers on a shared or adapted dataset) to establish it is not redundant with existing 2025–2026 work. This is a literature-positioning risk, not just an implementation gap: a paper submission without this comparison will likely be rejected as incremental.

### 7. AI-Assisted Diagnosis (general, cross-domain)

**Literature.** Diagnosis-under-uncertainty work in clinical AI and industrial fault diagnosis provides methodology (calibration, human-AI trust studies, uncertainty quantification) that AIOps papers rarely adopt.

**CloudGraph today.** Confidence scores exist (GCP root-cause confidence, GPCS trust score) but are never calibrated (no reliability diagrams, no Brier score, no coverage-vs-accuracy curves).

**Gap.** Borrowing calibration methodology from clinical/industrial diagnosis AI is a low-effort, high-credibility addition: it costs little beyond the already-existing confidence outputs and immediately answers "are these confidence numbers meaningful," a question every RCA reviewer will ask.

### 8. Neuro-Symbolic AI

**Literature.** Neuro-symbolic systems combine learned components (LLMs, embeddings) with symbolic structure (graphs, logic rules) and reason about the *interface* between the two: a very active 2024–2026 direction.

**CloudGraph today.** Is, in effect, already a neuro-symbolic system (symbolic Neo4j graph + rule-based edge weights + neural embeddings + LLM reasoning). The ablation that would test the interface has **not** been run.

**Gap — open, and it is the most important one.** Separating the symbolic contribution from the neural one requires a keyword / vector / hybrid retrieval ablation scored on expected-tag recall. The evaluation does not run it, so the repo holds **no evidence either way** on whether the graph adds retrieval value over embeddings alone.

What the evaluation does show is that the graph is load-bearing for claim **scoring**: GPCS's proximity and hop-decay terms operate over graph structure and have no embedding equivalent, and in this run the semantic term is supplied entirely by graph traversal at a fixed 0.75. That supports a narrower thesis — *the graph's demonstrated value in this system is verification* — but leaves retrieval untested rather than refuted. Running this ablation is the highest-value experiment remaining, because the design's central claim depends on its outcome.

---

## Summary table: where each area stands

| Area | RQ | Status after the 18-scenario evaluation |
|---|---|---|
| Real evaluation loop (was blocking everything) | **RQ2** | ✅ **Closed.** Every baseline invokes the real pipeline; the fabricated-offset heuristics are gone. |
| GPCS vs. self-consistency baseline | **RQ1** | ✅ **Addressed, partly against.** Difference clear (79.3% vs 53.0% unsupported); advantage not — neither verifier tracks correctness on 93 claims. |
| Long-context / raw-context control | **RQ3** | ◑ **Cost win only.** Ranked retrieval is 51.9% cheaper than a raw dump; no correctness advantage shown. |
| Neuro-symbolic framing + ablation | **RQ4** | ⏭ **Open — not measured.** No retrieval ablation is run; highest-value remaining experiment. |
| Multi-agent interaction / matched-compute control | **RQ5** | ⏭ **Open.** No matched-compute control is run; it is the cheapest remaining question to answer. |
| GCP as calibrated probabilistic graphical inference | **RQ6** | ⏭ **Open.** No weight fitting, no reliability diagram, no Brier score. |
| Calibration / uncertainty quantification | **RQ6** | ⏭ **Open.** Same gap; confidence scores exist but are never checked against correctness rates. |
| Claim-type blind-spot stratification | **RQ7** | ⏭ **Open.** Blocked on label volume — 4.8% automatic coverage is still too thin to stratify. |
| Temporal/operational GraphRAG framing | — | ⏭ **Open.** No with/without ablation of the recency term was run. |
| Adaptive/learned retrieval policy | — | ⏭ **Open.** Needs a policy layer over existing scorers. |
| Agent-selection as planning | — | ⏭ **Open.** Needs new orchestration logic. |
| Comparison to MetaRCA / agentic graph-traversal RCA | — | ⏭ **v3 — positioning risk.** Cited, not reproduced. A submission claiming superiority over these would need it; v1 claims no such comparison. |

**Reading the table:** four gaps closed, and three of the four closed
against the design's expectation. The two mechanisms the architecture bet on —
graph retrieval (RQ3) and symbolic structure (RQ4), did not pay off, and the
verifier that did behave distinctly (RQ1) cannot be shown to be better aimed.
What survives is narrower and better evidenced than the original programme.
