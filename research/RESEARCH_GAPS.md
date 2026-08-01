# RESEARCH_GAPS.md

## CloudGraph vs. the current research landscape

For each area: what exists in the literature, what CloudGraph currently has, and where the gap — i.e., the opportunity — sits.

---

### 1. GraphRAG

**Literature.** Edge et al. (2024) build community-summarized entity graphs over a corpus and use hierarchical summarization for global sensemaking queries. Most GraphRAG follow-on work (2024–2026) focuses on static, pre-built knowledge graphs over documents.

**CloudGraph today.** A *temporal, operational* knowledge graph (Neo4j) built from live telemetry, with bounded k-hop traversal and a hand-tuned hybrid ranker fusing vector similarity, hop-distance, and recency.

**Gap.** Almost all published GraphRAG work targets static document corpora. CloudGraph's graph is continuously mutating and time-indexed, which is a genuinely different retrieval regime (queries must respect causal/temporal ordering, not just topical relevance). This "temporal operational GraphRAG" setting is under-explored and is CloudGraph's most defensible point of departure from Edge et al.

### 2. Agentic AI / Multi-Agent Systems

**Literature.** Guo et al. (2024) survey LLM multi-agent systems; common patterns are debate, role specialization, and iterative critique/refinement, generally evaluated on general reasoning or coding benchmarks.

**CloudGraph today.** Five independent specialist *functions* (not agents that communicate) each producing a finding + confidence, aggregated by one of: fixed weighted average, or a single LLM call given all findings as context (no iteration, no debate, no agent-to-agent messages).

**Gap.** There is no actual multi-agent *interaction* in the current system — it is closer to an ensemble of independent classifiers than a multi-agent system. The gap is large but tractable: implementing even one round of cross-agent critique or evidence-sharing and measuring the delta against the current static-ensemble baseline is a clean, publishable comparison that the current codebase is one step away from supporting.

### 3. Retrieval-Augmented Generation / Adaptive Retrieval

**Literature.** Adaptive-RAG and self-RAG lines of work (2023–2025) let a model decide *when* and *how much* to retrieve, or select among retrieval strategies per query, rather than using a fixed pipeline.

**CloudGraph today.** A single fixed formula (`0.5·vector + 0.3·graph + 0.2·recency`) applied identically to every query, with a `method` selector (`keyword`/`vector`/`hybrid`) chosen by the caller, not the system.

**Gap.** No query-adaptive retrieval exists. Given that CloudGraph already logs which method "wins" per incident type in principle (via the existing `score_breakdown`), this is a natural extension: learn or heuristically select retrieval strategy per incident category, and measure whether adaptivity beats the fixed hybrid formula.

### 4. Knowledge Graph Reasoning

**Literature.** KG reasoning research spans embedding-based link prediction, rule mining, and — closest to CloudGraph — probabilistic/soft-logic propagation methods (Markov Logic Networks, probabilistic soft logic) for inferring node states from partial evidence.

**CloudGraph today.** GCP is a hand-weighted, BFS-based Noisy-OR propagation — structurally similar to loopy belief propagation on a small subgraph, but not derived from or benchmarked against that literature, and its edge weights are not learned.

**Gap.** GCP is currently an *ad hoc* instance of a well-studied family (probabilistic graphical inference for evidence combination). The opportunity is to (a) formalize it explicitly as an instance of that family (giving it theoretical grounding and correctness conditions), and (b) replace hand-set weights with weights fit to labeled incidents, then compare against both the current heuristic and an off-the-shelf PSL/MLN baseline.

### 5. Long-Context Reasoning / Tool-Using LLMs / LLM Planning

**Literature.** Long-context work asks whether large context windows can substitute for retrieval; tool-use and planning work studies LLMs that decide which external calls to make and in what order.

**CloudGraph today.** No comparison against a long-context "dump everything into the prompt" baseline exists — this is a cheap, high-value control condition that is currently missing entirely (does structured graph retrieval even outperform simply pasting all evidence into context, given modern context windows?). Also, agent behavior is currently a **fixed** DAG (five specialist calls → one consensus call) rather than a planned or tool-selected sequence.

**Gap.** Two low-cost, high-value additions: (1) a "raw context" / long-context baseline for RQ1-adjacent comparisons, and (2) allowing the orchestrator to *choose* which specialist agents to invoke and in what order based on early evidence, rather than always running all five — this reframes CloudGraph's orchestration as a planning problem.

### 6. Root Cause Reasoning / AI for Systems

**Literature.** MetaRCA (Liang et al., 2026) and agentic structured graph traversal for RCA (Cui et al., 2025) are close, recent competitors: both target graph-based RCA with agentic elements.

**CloudGraph today.** Directly overlaps with this niche but has not been benchmarked against either system or their datasets, and its own evaluation is currently simulated (see `REPOSITORY_REVIEW.md`).

**Gap.** The most direct competitive gap: CloudGraph must, at minimum, cite and ideally reproduce a comparison against these two systems (or their reported numbers on a shared or adapted dataset) to establish it is not redundant with existing 2025–2026 work. This is a literature-positioning risk, not just an implementation gap — a paper submission without this comparison will likely be rejected as incremental.

### 7. AI-Assisted Diagnosis (general, cross-domain)

**Literature.** Diagnosis-under-uncertainty work in clinical AI and industrial fault diagnosis provides methodology (calibration, human-AI trust studies, uncertainty quantification) that AIOps papers rarely adopt.

**CloudGraph today.** Confidence scores exist (GCP root-cause confidence, GPCS trust score) but are never calibrated (no reliability diagrams, no Brier score, no coverage-vs-accuracy curves).

**Gap.** Borrowing calibration methodology from clinical/industrial diagnosis AI is a low-effort, high-credibility addition: it costs little beyond the already-existing confidence outputs and immediately answers "are these confidence numbers meaningful," a question every RCA reviewer will ask.

### 8. Neuro-Symbolic AI

**Literature.** Neuro-symbolic systems combine learned components (LLMs, embeddings) with symbolic structure (graphs, logic rules) and reason about the *interface* between the two — a very active 2024–2026 direction.

**CloudGraph today.** Is, in effect, already a neuro-symbolic system (symbolic Neo4j graph + rule-based edge weights + neural embeddings + LLM reasoning) but never frames or evaluates itself as one — no discussion of where symbolic structure helps vs. hurts, no ablation isolating the symbolic component's contribution.

**Gap.** Reframing CloudGraph explicitly as a neuro-symbolic RCA system, with an ablation that removes the symbolic graph component entirely (pure vector RAG) vs. removes the neural component (pure graph traversal, no LLM), is both cheap (the pieces already exist) and squarely fits an active, well-regarded subfield — this is likely CloudGraph's best positioning for venues that value theoretical framing over systems novelty.

---

## Summary table: gap size vs. tractability

| Area | Gap size | Tractability with current code | Priority |
|---|---|---|---|
| Real evaluation loop (prerequisite for all below) | N/A — currently absent entirely | High (retrieval/GCP/GPCS code already exists; just needs wiring) | **Blocking** |
| Temporal/operational GraphRAG framing | Medium | High (already the actual system) | High |
| Multi-agent interaction (debate/critique) | Large | Medium (needs new orchestration logic) | High |
| Adaptive/learned retrieval policy | Large | Medium (needs a policy layer over existing scorers) | Medium |
| GCP as calibrated probabilistic graphical inference | Medium | Medium (needs labeled data + fitting procedure) | High |
| GPCS vs. self-consistency baseline | Small (already specified in repo's own design doc) | High (mostly implementation) | **High, low-cost** |
| Comparison to MetaRCA / agentic graph-traversal RCA | Large (positioning risk) | Low–Medium (needs reproduction or dataset adaptation) | High |
| Calibration / uncertainty quantification | Medium | High (confidence scores already exist) | Medium |
| Neuro-symbolic framing + ablation | Medium (mostly conceptual + one ablation) | High | High, low-cost |
| Long-context / raw-context control baseline | Small | High | Medium, cheap control |
