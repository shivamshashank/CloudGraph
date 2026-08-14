# NOVEL_CONTRIBUTIONS.md

Five candidate publishable contributions, each with what it is, why it is novel relative to existing work, and what would have to be true (evidence) for the claim to hold.

**The "what would have to be true" criteria were written before any valid
measurement, and are kept unedited below.** That makes them usable as stated
falsification conditions rather than post-hoc rationalisation. Judged against
those criteria, the 36-scenario RCAEval run (`experiments/`) settled two and
left three untested:

| # | Contribution | RQ | Verdict against its own stated criterion |
|---|---|---|---|
| 1 | Temporal Operational GraphRAG | RQ3 / v3 | **Partly settled, and against.** RQ3 closed the long-context control: ranked retrieval did not beat a raw evidence dump (Δ +0.024, CI [−0.028, +0.077], p=0.302). The *temporal-filtering* ablation specifically was never run — recency was fixed from inert (spread 0.000) to real (0.251), so the term now *does* something, but no with/without comparison exists and the "recent = relevant" confound the criterion demands be controlled has not been controlled. Carried to v3. |
| 2 | GPCS as a distinct family from self-consistency | RQ1 / RQ7 | **Not established.** The two methods do behave differently and significantly so (70.3% vs 57.9% flagged, p<0.0001). But the criterion asks whether GPCS is better *aimed*, and on the labelled subset neither verifier separates correct claims from incorrect ones — both precision figures sit exactly on the base rate. Difference is demonstrated; advantage is not. The claim-type-stratified blind-spot analysis (**RQ7**, blocked on human labels) and a GPCS per-term ablation (semantic / proximity / reliability / path penalty) both remain undone. |
| 3 | Neuro-symbolic ablation framing | RQ4 | **Falsified as stated.** The criterion was explicit: "If both ablations fail identically, the 'symbolic structure adds distinct value' claim is unsupported." Vector and hybrid retrieval were **byte-identical on all 36 scenarios** — same expected tags, same hit tags, mean recall 0.6065 each. The framing survives only for *claim scoring*, where the graph is load-bearing — not for retrieval. |
| 4 | Calibrated GCP | RQ6 | **Untested — deferred to v2.** No weight fitting, no reliability diagram, no Brier score. Unchanged from when this was written. |
| 5 | Multi-agent interaction vs independent ensemble | RQ5 | **Untested on valid data — deferred to v2.** The matched-compute control ran only under the pipeline later found to leak ground truth, so its numbers are not reported. Note the contribution already anticipates the negative result as publishable — that framing still holds. Cheapest of the three to close. |

Two of five landing negative or null is the state of the work, and the negative on
Contribution 3 is a real finding rather than an absence of one: it says the
graph's value in this system is verification, not retrieval. That is a
narrower and more defensible thesis than the original five combined.

---

## Contribution 1 — Temporal Operational GraphRAG

**What.** A GraphRAG variant specialized for continuously-mutating, time-indexed operational graphs (infrastructure telemetry) rather than static document corpora, where retrieval must respect causal/temporal ordering (evidence must precede or coincide with the incident window) in addition to topical and structural relevance.

**Why novel.** GraphRAG (Edge et al. 2024) and its many follow-ons assume a largely static graph built once from a fixed document set. CloudGraph's graph is rebuilt/extended continuously and retrieval already includes a temporal-window constraint (`graph_traversal.py`'s `start_time`/`end_time` derivation) and a recency-decay term in the ranker: these are not present in the canonical GraphRAG formulation. The contribution is to make this explicit and study it: does temporal filtering change retrieval quality, and does it change what "relevant" means for causal (as opposed to topical) queries?

**What would have to be true.** Temporal-filtered/decayed retrieval must measurably outperform temporally-naive retrieval (same graph, no time constraint) on incidents where root cause and symptom are separated by a nontrivial time gap, and the effect must be shown to *not* just be a proxy for "recent things are usually more relevant" (a confound to control for explicitly).

## Contribution 2 — Graph-Provenance Claim Scoring (GPCS) as a Distinct Family from Self-Consistency Hallucination Detection

**What.** A hallucination-detection mechanism for generated RCA text that scores each atomic claim by proximity/reliability in an explicit evidence graph (semantic alignment + graph hop-distance + source-reliability weighting + a path-length trust penalty), contrasted directly against the dominant self-consistency family (Wang et al.-style repeated-sampling agreement).

**Why novel.** Most hallucination-detection work is model-internal (self-consistency, log-prob-based, or a second LLM as judge) and domain-agnostic. GPCS is *evidence-grounded* rather than model-internal, and specific to the operational/AIOps setting where a structured evidence graph already exists as a byproduct of the system (not an added cost). The path-length trust penalty (long inferential chains reduce trust even when the endpoint match is strong) is, per the repo's own design doc, the one component that is not a repurposed existing formula: this is the most defensible "new mechanism" claim in the codebase.

**What would have to be true.** GPCS must (a) achieve lower unsupported-claim rate than self-consistency at matched compute cost, and/or (b) catch a disjoint set of unsupported claims (i.e., have a different blind spot), demonstrated on claim-type-stratified data. If GPCS and self-consistency simply agree on everything, the contribution collapses to "yet another hallucination detector" with no differentiation.

## Contribution 3 — Neuro-Symbolic Ablation Framing for Graph-Grounded RCA

**What.** An explicit neuro-symbolic decomposition of CloudGraph: symbolic component (typed graph + traversal + GCP's probabilistic edge propagation) vs. neural component (dense embeddings + LLM reasoning): with a controlled ablation removing each in turn, positioned within the active neuro-symbolic AI literature rather than as an incidental systems detail.

**Why novel.** CloudGraph already *is* a neuro-symbolic system by construction, but nothing in the repo frames or evaluates it that way. The contribution is not new code (the `keyword`/`vector`/`hybrid` methods already exist) but a rigorous ablation and a theoretical framing that asks *where* symbolic structure earns its keep versus where it is redundant with what embeddings already capture: a question the neuro-symbolic community actively cares about and one CloudGraph is unusually well-instrumented to answer cheaply.

**What would have to be true.** The symbolic-only and neural-only ablations must show *different failure modes* (not just different aggregate scores): e.g., symbolic-only should fail on paraphrased/novel-vocabulary incidents, neural-only should fail on multi-hop dependency chains not co-mentioned in text. If both ablations fail identically, the "symbolic structure adds distinct value" claim is unsupported.

## Contribution 4 — Calibrated Graph Confidence Propagation (Calibrated GCP)

**What.** Graph Confidence Propagation, reformulated explicitly as an instance of Noisy-OR probabilistic graphical inference (rather than an ad hoc heuristic), with edge weights fit to labeled incident outcomes instead of hand-set, and evaluated for calibration (not just top-1/top-3 accuracy).

**Why novel.** GCP as currently implemented is structurally sound (a legitimate Noisy-OR BFS propagation) but has zero learned or calibrated parameters, and its confidence outputs are never checked against actual correctness rates. The contribution is to (a) situate GCP formally against the probabilistic soft logic / Markov Logic Network literature it structurally resembles, (b) fit edge weights from data, and (c) report calibration curves (reliability diagrams, Brier score, coverage-vs-accuracy): a standard in diagnosis-under-uncertainty research (clinical/industrial AI) but essentially absent from current AIOps papers, which is itself a gap worth exploiting.

**What would have to be true.** Fitted weights must outperform hand-set weights on held-out incidents (not just fit the training incidents better: the fitting procedure must generalize), and the resulting confidence scores must show materially better calibration than the current unfit baseline.

## Contribution 5 — Multi-Agent Interaction vs. Independent-Ensemble Ablation for RCA

**What.** A controlled comparison isolating whether CloudGraph's five-specialist architecture derives its value from (a) genuine multi-agent interaction, (b) mere ensembling/specialization without interaction, or (c) simply more LLM calls (compute), by comparing: single LLM with full evidence → independent specialists + static vote (current system) → specialists + one round of cross-agent critique (new) → self-consistency ensemble of the single LLM at matched call-count.

**Why novel.** Multi-agent LLM system papers (Guo et al. 2024 survey) rarely control for the "more calls = better" confound, and AIOps papers claiming "multi-agent" benefit almost never compare against a matched-compute single-agent or ensemble baseline. CloudGraph's existing five-function architecture is a ready-made ensemble baseline; adding one interaction round and one matched-compute control turns an implicit, unverified claim ("multi-agent is better") into a controlled, falsifiable one.

**What would have to be true.** The interaction condition must beat both the independent-ensemble and the matched-compute self-consistency baselines on accuracy or hallucination rate: if independent ensembling or matched-compute self-consistency perform equally well, the "agentic interaction" framing is not earning its complexity and the honest finding is that CloudGraph's gains (if any) come from evidence quality (GraphRAG) and ensembling, not from agency per se. This negative-result framing is itself publishable as a "does multi-agent structure help X" finding, consistent with the 95+ checklist's expectation that dissertations report where a hypothesis is *not* supported.

---

## Cross-cutting note on novelty discipline

*Written before v1's results; the prioritisation held.* Contributions 1, 2, and 3 required the least new code (primarily evaluation/framing work over what already existed) and were prioritised accordingly: all three are now settled. Contributions 4 and 5 require new experimental infrastructure (weight fitting, an interaction round) and were correctly sequenced to follow once the evaluation loop (**RQ2**) was real, which it now is. None of the five contributions require inventing a new model architecture or training a new LLM: all are evaluation, ablation, and calibration studies over an existing, real system, which is the correct scope for a dissertation-to-first-paper trajectory.

## What v1 actually established

Judged against criteria fixed in advance, **two of five contributions are
settled and both landed negative or null**, and a third (RQ3) closed null on
its retrieval half. That is the state of the work, and it is not an absence of
findings:

> The graph's value in this system is **verification, not retrieval**.

That single sentence is narrower than the five contributions combined and
better evidenced than any of them individually. It is the thesis v1 supports,
and the three deferred questions (**RQ5–RQ7**) are precisely what would be
needed to extend it — see
[`RESEARCH_QUESTIONS.md`](RESEARCH_QUESTIONS.md).
