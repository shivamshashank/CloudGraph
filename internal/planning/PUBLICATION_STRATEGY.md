# PUBLICATION_STRATEGY.md

## Target venues, ranked by fit given the current and planned scope

### Tier A — Best fit, recommend as primary target

**IEEE Cloud / IEEE Conference on Cloud Computing, or a similarly scoped applied-systems venue (e.g., NOMS, CCGrid)**
*Why it fits.* CloudGraph is fundamentally a systems contribution (AIOps RCA for Kubernetes) with an ML component layered on top; applied-cloud venues explicitly welcome this combination and do not require the theoretical depth ML-theory venues expect.
*Additional work required.* Phases 1–3 of `IMPLEMENTATION_ROADMAP.md` (real evaluation, statistics, dataset scale) are sufficient; Phase 4's calibration work strengthens but is not strictly required.
*Expected contribution framing.* "Temporal, graph-grounded AIOps RCA with calibrated confidence and evidence-grounded hallucination auditing," positioned against MetaRCA/Cui et al. as related-but-distinct work.

**Workshop track at NeurIPS/ICLR (e.g., a "Foundation Models for Systems," "GraphRAG/Retrieval," or "Trustworthy AI" workshop, exact workshop varies by year)**
*Why it fits.* Workshops accept smaller-scale, more focused contributions than the main track; the GPCS-vs-self-consistency comparison (Contribution 2) alone is a clean, self-contained workshop paper once Phase 2 is complete, and does not require the full system or dataset scale.
*Additional work required.* Phase 1 (real evaluation) and Phase 2 (self-consistency baseline) only — this is the fastest path to a first publication and should be pursued in parallel with the larger dissertation timeline, not sequentially after it.
*Expected contribution framing.* "Graph-Provenance Claim Scoring: evidence-grounded hallucination detection vs. self-consistency in an operational RAG setting."

### Tier B — Good fit with more work

**ACL Findings / EMNLP Findings (industry or applications track)**
*Why it fits.* Findings tracks accept solid, well-evaluated applied NLP/RAG work without requiring theoretical novelty; the retrieval and hallucination-detection contributions (1 and 2) fit the RAG/faithfulness literature these venues actively publish.
*Additional work required.* Full Phase 3 (100+ scenarios, statistical testing) is close to mandatory for Findings-track empirical rigor expectations; Phase 5's comparison to prior RCA-specific work strengthens but is secondary since these venues are more RAG/faithfulness-community-facing than systems-facing.
*Expected contribution framing.* Lead with Contribution 1 (temporal operational GraphRAG) and Contribution 2 (GPCS), de-emphasize the Kubernetes-specific systems framing.

**MLSys**
*Why it fits.* If the scalability evaluation (RQ16, Phase 5 stretch) is completed and shows a genuine systems-performance angle (e.g., how bounded k-hop traversal scales, latency/cost tradeoffs of the multi-agent architecture), MLSys is a strong fit for the systems-for-ML or ML-for-systems angle.
*Additional work required.* The scalability sweep is currently not scoped into Phases 1–5's core path (it's listed as a stretch item); would need dedicated additional time and is the least certain of the venue options to be ready within a standard dissertation timeline.
*Expected contribution framing.* "Systems tradeoffs in graph-grounded, multi-agent AIOps RCA at scale."

### Tier C — Reach / longer horizon

**USENIX (OSDI/NSDI/ATC)**
*Why it might fit.* If the system matures into a genuinely novel systems artifact (e.g., a production deployment story, a scale evaluation on real large clusters, and a systems-level novel mechanism beyond what's currently scoped), USENIX venues are plausible.
*Why not yet.* Current scope is an evaluation/algorithmic-rigor upgrade to an existing system category, not a new systems mechanism at USENIX's expected novelty bar; realistically a v3/PhD-track target, not a dissertation-track one.

**NeurIPS/ICLR main track**
*Why not yet.* Main-track ML venues expect either a new learning method with theoretical grounding or large-scale empirical results with strong baselines across many domains; CloudGraph's current and planned scope (evaluation rigor + two named heuristic-but-formalizable mechanisms + one Kubernetes-specific dataset) is below this bar without the v3/PhD-track extensions (learned consensus, RL-based retrieval, cross-domain generalization). Recommend workshop tracks now, main track as a v3-stage aspiration.

## Recommended sequencing

1. **First submission (fastest path, parallel to dissertation writing):** GPCS-vs-self-consistency workshop paper, ready as soon as Phase 2 completes. Low risk, self-contained, directly reuses the design doc already in the repo.
2. **Dissertation submission:** Full system + Phases 1–4 results, written per the standard dissertation structure (already scaffolded in `docs/week-1/dissertation-evidence.md`).
3. **Second submission (post-dissertation, ~1–3 months after):** Applied-systems paper (IEEE Cloud or similar) using Phase 5's full results and comparison to MetaRCA/Cui et al. — this is explicitly the user's existing "v2: post-submission journal hardening" milestone, and this plan confirms IEEE Cloud-class venues (not necessarily "journal" in the strict sense, but comparable applied-venue rigor) as the right target class for it.
4. **Longer horizon (v3/PhD-track):** Findings-track or MLSys submission once the theoretical formalization of GCP (as calibrated probabilistic inference) and any scale/generalization work is complete.

## What each venue additionally requires, summarized

| Venue class | Minimum phase needed | Key missing piece today |
|---|---|---|
| Workshop (GPCS focus) | Phase 2 | Self-consistency baseline implementation only |
| IEEE Cloud / applied-systems | Phase 3 | Real evaluation + scaled dataset + statistics |
| ACL/EMNLP Findings | Phase 3 (strict) | Statistical rigor at RAG-community standard; de-emphasize K8s framing |
| MLSys | Phase 5 + scalability stretch | Dedicated scale evaluation, currently unscoped |
| USENIX / NeurIPS main | Beyond this roadmap (v3/PhD-track) | New systems mechanism or learned/theoretical ML contribution at larger scale |
