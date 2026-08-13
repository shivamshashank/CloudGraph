# RESEARCH_QUESTIONS.md

18 candidate research questions, each scored on Novelty (N), Feasibility with current codebase (F), Publication potential (P), and Implementation effort (E — lower is easier), each 1–5. Ranked by a composite of N + P weighted against E.

**Scoring is the pre-evaluation judgement, kept unedited.** The status column
below records what the 36-scenario RCAEval run (`experiments/`) actually
settled. Four of the Phase-1 shortlist are now closed; two of those closed
*against* the hypothesis.

| RQ | Status after the 36-scenario run |
|---|---|
| RQ1 GPCS vs self-consistency | **Partly answered.** GPCS flags 70.3% unsupported vs 57.9%, Δ +0.119 CI [+0.073, +0.163], p<0.0001. But on the 4.2% of claims with automatic correctness labels *neither* verifier discriminates correct from incorrect (both gaps −0.8 pp). The "which blind spot" half — claim-type-stratified — is still open and needs human labels. |
| RQ2 Is the improvement real end-to-end | **Answered — yes, and smaller than the simulated numbers implied.** Every baseline now invokes the real pipeline. Four integrity defects had to be fixed first; earlier results were invalid. |
| RQ3 Multi-agent vs single LLM at matched compute | **Open.** The matched-compute control has only ever run on the leaked pipeline. Re-running it is the cheapest remaining closure. |
| RQ6 Graph retrieval vs raw context | **Answered — null.** hybrid vs raw context, Δ +0.024, CI [−0.028, +0.077], p=0.302. Structure did not beat dumping all evidence into context. |
| RQ17 Neuro-symbolic ablation | **Answered — negative.** Vector and hybrid were *identical on every measure*; the symbolic component contributed nothing to retrieval on this benchmark. It does contribute to claim scoring, which is a different mechanism. |
| RQ5, RQ9 GCP/GPCS calibration | **Not started.** Thresholds remain fixed defaults; no reliability diagram or Brier score exists. |
| RQ4, RQ7, RQ8, RQ10–RQ16, RQ18 | **Open**, as scored. |

RQ2 was the stated non-negotiable prerequisite and is now discharged, so the
remaining shortlist is genuinely actionable rather than blocked.

---

## Tier 1 — Highest priority (novel, feasible, strong publication fit)

**RQ1. Does graph-grounded claim verification (GPCS) reduce unsupported-claim rate more than a self-consistency baseline, and on which claim types does each method's blind spot lie?**
N4 F5 P5 E2 — *Already specified in the repo's own design doc as the "must implement" comparison; this is the single highest ROI research question available.*

**RQ2. Is CloudGraph's reported benchmark improvement real once retrieval, agents, GCP, and GPCS are actually invoked end-to-end (vs. the current simulated heuristic scorer)?**
N2 F5 P5 E2 — *Not itself novel, but a mandatory prerequisite finding; every other RQ's evidence depends on this being answered first and honestly (including the possibility that real numbers look worse than simulated ones).*

**RQ3. Does multi-agent specialist collaboration (independent scoring + static consensus) outperform a single LLM given the same retrieved evidence, and does the improvement come from specialization or from ensembling?**
N3 F4 P4 E3 — *Directly testable: run current 5-agent pipeline vs. one LLM call with concatenated evidence vs. self-consistency ensembling of the single LLM (controls for "more LLM calls = better" confound).*

**RQ4. Can inter-agent interaction (one round of cross-agent critique/evidence-sharing) outperform the current static independent-then-vote architecture?**
N4 F3 P5 E4 — *Requires new orchestration logic but directly answers the "is this actually agentic" question that separates CloudGraph from an ensemble classifier.*

**RQ5. Does calibrated (data-fit) GCP edge-weighting outperform the current hand-set weights, and how sensitive is root-cause accuracy to those weights?**
N4 F4 P4 E3 — *A sensitivity/ablation study over `EDGE_WEIGHTS` plus a simple weight-fitting procedure (e.g. logistic regression on labeled root causes) is directly implementable over existing code.*

**RQ6. Does graph-structured retrieval (hop-distance + traversal) provide reasoning benefit beyond what a sufficiently large context window given to an LLM directly (no retrieval) achieves?**
N4 F4 P5 E2 — *Cheap, high-value control condition; directly tests whether "graph" is doing real work vs. retrieval simply surfacing text an LLM could reason over unaided.*

## Tier 2 — Strong but requiring more new infrastructure

**RQ7. Can a learned or heuristic query-adaptive retrieval policy (choosing among keyword/vector/graph/hybrid per query) outperform the fixed hybrid formula across incident categories?**
N4 F3 P4 E4

**RQ8. How does incident-graph topology (branching factor, hop depth to root cause) affect GCP propagation accuracy, and is there a topology regime where propagation systematically fails?**
N4 F3 P4 E3 — *Requires synthetic topology generation but is a clean theoretical-empirical study using existing GCP code.*

**RQ9. Are GCP/GPCS confidence scores well-calibrated (do 80%-confidence predictions turn out correct ~80% of the time), and does calibration correlate with human-perceived trust?**
N3 F4 P4 E3

**RQ10. Does allowing the orchestrator to select which of the five specialist agents to invoke (rather than always running all five) reduce cost/latency without reducing accuracy — i.e., can RCA investigation be framed as a planning problem?**
N4 F3 P3 E4

**RQ11. How does CloudGraph's accuracy/hallucination/latency profile compare to MetaRCA (Liang et al. 2026) and agentic structured graph traversal (Cui et al. 2025) on a shared or adapted incident set?**
N3 F2 P5 E5 — *High publication value (positions CloudGraph against direct competitors) but high effort (requires reproducing or adapting external systems/datasets).*

## Tier 3 — Valuable but secondary / longer-horizon

**RQ12. Does a temporal knowledge graph (time-indexed edges, decay-weighted retrieval) outperform a static snapshot graph for RCA in systems where root causes are separated from symptoms by minutes-to-hours?**
N3 F3 P3 E3

**RQ13. Can reinforcement learning (or bandit-style online learning) improve the hybrid ranker's weights over time from operator feedback (accept/reject of RCA reports)?**
N4 F2 P4 E5 — *Highest novelty in the list but requires a feedback-loop and online-learning infrastructure that does not exist.*

**RQ14. Does explicit uncertainty propagation (GCP) improve human operator trust and decision speed compared to an unweighted evidence list, measured via a small human study?**
N3 F2 P4 E4 — *Requires a human-subjects study, which is feasible but outside pure code changes.*

**RQ15. Is CloudGraph's improvement robust across incident categories (K8s, networking, security, deployment, observability) or concentrated in a subset — i.e., does GraphRAG help uniformly or only for multi-hop dependency failures?**
N3 F4 P4 E3 — *Directly testable once the dataset is scaled to 100+, category-stratified scenarios (already planned in `data-collection-strategy.md`).*

**RQ16. How does CloudGraph scale (latency, accuracy) as the knowledge graph grows from hundreds to hundreds-of-thousands of nodes, and where does the current bounded k-hop traversal break down?**
N2 F4 P3 E3 — *A systems-flavored scalability study; useful for MLSys/USENIX framing but lower ML novelty.*

**RQ17. Can a neuro-symbolic ablation (remove the graph → pure vector RAG; remove the LLM → pure symbolic graph traversal) isolate how much of CloudGraph's benefit is symbolic-structural vs. neural-semantic?**
N4 F4 P4 E2 — *Cheap: this is largely a re-run of the existing `keyword`/`vector`/`hybrid` methods with a clean ablation framing and write-up, not new code.*

**RQ18. Does CloudGraph generalize beyond Kubernetes to a structurally different infrastructure domain (e.g., serverless/FaaS dependency graphs) without re-tuning GCP/GPCS weights?**
N4 F1 P4 E5 — *Highest long-horizon novelty (this is explicitly the user's v3/PhD-track milestone), but currently entirely unimplemented and requires a second domain's dataset and graph schema.*

---

## Ranked shortlist for immediate research program (Phase-1 candidates)

1. RQ2 (real evaluation loop) — **prerequisite, do first, non-negotiable**
2. RQ1 (GPCS vs. self-consistency)
3. RQ6 (graph retrieval vs. raw long-context control)
4. RQ17 (neuro-symbolic ablation — largely free once RQ2 is done)
5. RQ3 (multi-agent vs. single-LLM-with-same-evidence)
6. RQ5 (GCP weight sensitivity/calibration)
7. RQ9 (confidence calibration)
8. RQ4 (inter-agent interaction)
9. RQ15 (cross-category robustness, needs dataset scaling)
10. RQ11 (comparison to MetaRCA / agentic graph traversal — needed before submission, not before first experiments)

RQ13 and RQ18 are correctly positioned as PhD-track (v3) extensions rather than dissertation-scope work, consistent with the project's existing three-tier roadmap.
