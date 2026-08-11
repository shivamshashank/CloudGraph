# CloudGraph — research and PhD-readiness audit

**Audit date:** 2026-08-11. Scope was all 242 tracked project files, plus the present untracked experiment artefacts in `experiments/results/` and `experiments/figures/`. Third-party virtual environments/caches were enumerated but are not project evidence. The worktree was already dirty and was preserved. The local Python API suite and both Go suites pass.

## Executive verdict

CloudGraph is a strong research-oriented systems portfolio project, but not yet a defensible research result. Its strongest signal is research integrity: the project found, documented, fixed and regression-tested four defects that invalidated its old results. The current corrected study has good provenance but does **not** establish that GraphRAG improves RCA, that GPCS detects unsupported claims, or that multi-agent reasoning helps.

FACT: the current result has 36 balanced RCAEval RE2 cases. Hybrid beats keyword tag recall by +0.1898 (95% paired bootstrap CI [+0.1157,+0.2685], Wilcoxon p=.0003), while hybrid minus raw claim-agreement is non-significant (CI [-.0280,+.0773], p=.3021). GPCS versus self-consistency only shows different flagging rates (+.1198), not accuracy.

FACT: only 155/3,685 claims (4.2%) have automatic causal correctness labels. GPCS flags 60.4% of contradicted and 61.2% of consistent claims; self-consistency flags 72.6% and 73.5%. Neither currently discriminates error. Thus the F1 values in `experiments/results/correctness_labels.md` are dominated by a 68.4% contradiction base rate and must not be advertised as verifier validity.

## Architecture map

```text
RCAEval RE2 metrics/logs or live K8s telemetry
 -> adapters + scenario builder -> Neo4j graph + Qdrant evidence
 -> keyword | vector | hybrid retrieval
 -> 5 independent LLM specialists -> static weighted consensus
 -> claim extraction -> GPCS and sampled self-consistency
 -> per-scenario results -> paired bootstrap/Wilcoxon -> figures
```

| Area | Purpose |
|---|---|
| `services/api/app/` | FastAPI product/research harness: adapters, storage, retrieval, demo seeding, GCP/GPCS/evaluation. |
| `services/agent-orchestrator/`, `services/investigation-engine/` | Custom HTTP five-specialist pipeline and static consensus; no LangGraph and no cross-agent critique. |
| `experiments/` | RCAEval provenance, current result tables/figures and HTML findings. Current results are untracked: a release defect. |
| `research/`, `dissertation/` | Research agenda, plans, stale paper drafts, and the Week 9 leakage postmortem. |
| `deployments/`, `cmd/`, `testing/` | Strong deployment, CLI, CI, integration and research-run infrastructure. |

FACT: the generated benchmark tells the system the faulted service in `target_entity`; it assesses fault-type diagnosis, **not** service localisation. See `services/api/app/demo/rcaeval_dataset.py`, `services/api/scripts/build_rcaeval_dataset.py`, and `experiments/DATA_PROVENANCE.md`.

The repository calls its hybrid approach GraphRAG. This means local vector + property-graph + recency ranking, not canonical Microsoft GraphRAG's entity-community/global-question method. Define that distinction precisely in a paper.

## Research question and contribution audit

The final implemented question should be narrowed to: “For a known affected service in chaos-injected microservice faults, does temporal graph-aware evidence retrieval improve evidence/fault-type diagnosis over matched controls, and can provenance-aware scoring discriminate independently labelled unsupported claims?”

| Candidate contribution | Implementation status | Research judgement |
|---|---|---|
| Temporal operational hybrid retrieval | Implemented: .50 semantic + .30 hop proximity + .20 recency; temporal traversal. | Good systems mechanism; no temporal-versus-naive ablation, so not established contribution. |
| GPCS | Implemented in `services/api/app/research/gpcs.py`: claim extraction, scenario-scoped semantic search, entity traversal, linear score. | Useful prototype; similarity/proximity is not entailment; hand weights and threshold are not calibrated. |
| GCP | Noisy-OR BFS in `services/api/app/research/gcp.py`. | Heuristic score, not calibrated uncertainty; no held-out ranking/calibration evidence. |
| Hybrid “neuro-symbolic” retrieval | Keyword/vector/hybrid comparison exists. | Framing is plausible, but hybrid has no demonstrated advantage over vector. |
| Multi-agent RCA | Five independent specialists plus static vote exist. | Strong engineering; no valid current matched-compute result and no interaction. |
| Leakage and reproducibility controls | Implemented and regression tested. | Strongest signal of research maturity, not a standalone algorithmic novelty. |

**Research, not engineering:** only a validated operational provenance verifier, controlled evidence-structure result, calibrated uncertainty method, or matched-compute agent finding could become a paper contribution. FastAPI, Helm, Docker, Neo4j, Qdrant, Prometheus/Grafana/Loki/Tempo, the UI, Go CLI and LLM APIs are strong engineering/support infrastructure, not novelty.

## Evaluation and statistics audit

Dataset strengths: public MIT-licensed RCAEval RE2; deterministic balanced selection; raw telemetry rather than authored incidents; input/answer separation; redaction; SHA/provenance; scenario isolation. Limitations: 36 incidents, three apps, six resource/network faults, only metrics/logs converted, target service revealed, and magnitude-ranked metrics. Results must be scoped to known-service fault-type diagnosis in this benchmark.

Required missing baselines/ablations: graph-only; raw long-context; full downstream vector RAG; single-LLM no-context; single LLM/matched compute; independent single-model ensemble; critique round; GPCS term removal; GCP weight/decay sensitivity; NLI or LLM-judge evidence verifier; blinded human adjudication.

The bootstrap and Wilcoxon script (`services/api/scripts/paired_bootstrap.py`) is sensible but insufficient. Cluster the GPCS/self-consistency analysis by 36 scenarios rather than treating 108 scenario×context rows as independent; pre-specify a primary endpoint; Holm-correct secondary tests; report effect sizes and full CIs; repeat 3–5 stochastic generations; freeze model/prompt/configuration; fit all thresholds/weights only on development data or nested CV. Add AUPRC, AUROC, sensitivity/specificity and calibration (Brier/ECE/reliability) on human labels.

## Code-level credibility findings

1. GPCS uses best embedding relevance, min hop and fixed source reliability; it never tests textual entailment or contradiction. A semantically similar contradiction can pass.
2. `GraphProvenanceClaimScorer` defaults to .45/.35/.25/.15 weights and threshold .50. The design doc promises a held-out calibrated cutoff; the code does not provide it. Remove “calibrated” everywhere.
3. GCP makes relationships bidirectional, applies subjective weights, and returns a score for an already-known target. Do not call it root-cause probability; no benchmark supports the claimed confidence.
4. Current retrieval `correct` was saturated; `strict_correct`/recall are still tag string matching, not evidence relevance or diagnosis.
5. The old 25-case matched-compute multi-agent result is withdrawn. There is no current `matched_compute_raw.csv`, and current significance output does not test agents.
6. Product and experiment code share live external services. Add an immutable experiment container/replay mode and versioned prompts/configurations.

## Visual, documentation and paper audit

The diagrams are polished but misleading if shown as a current implementation. The README raster architecture depicts AWS/EKS/RDS/S3, extra agents, external alert integrations and continuous learning. The GraphRAG/multi-agent diagrams show trace/RCA/recommendation chains absent from the actual static five-agent implementation. `docs/architecture/design-evolution.md` correctly records the AWS and LangGraph changes, but does not neutralise the README's visual claims. The newer SVGs are better but still present planned learning/multi-cluster capabilities.

The experiment retrieval figure says **n=25** while the corrected run has n=36. Regenerate every plot from a locked manifest and show vector-versus-hybrid CIs. Use one faithful paper diagram with solid implemented/evaluated elements and dashed planned elements.

All LaTeX/Markdown paper drafts explicitly say STALE/DO NOT SUBMIT because the old pipeline leaked labels. This is excellent integrity practice, but means there is no paper to submit. Do not replace 25 with 36 mechanically; write a new manuscript after the corrected experiment is complete.

## External novelty position

EXTERNAL: canonical GraphRAG builds entity graphs/community summaries for global corpus questions; CloudGraph implements local temporal hybrid evidence ranking. [Edge et al. (2024)](https://arxiv.org/abs/2404.16130)

EXTERNAL: static specialist-and-vote LLM systems are established, not novel by themselves. [Guo et al. (IJCAI 2024)](https://www.ijcai.org/proceedings/2024/0890)

EXTERNAL: graph/evidence hallucination verification is also active territory. Evidence Graph Consistency tested structured evidence signals over 5,767 RAG answers and found model-family reversals, directly motivating multi-model and labelled validation for GPCS. [Shen (2026)](https://arxiv.org/abs/2606.06748)

The defensible niche is therefore **provenance-aware verification for time-indexed operational telemetry**, conditional on robust held-out results—not graph verification or multi-agent RCA in general.

## Reviewer attack list: question -> fix

1. Why graph rather than vector RAG? -> token-matched vector, graph-only, hybrid, raw and random controls.
2. Does hybrid beat vector? -> make that a primary diagnosis/evidence test.
3. Is the graph causal? -> annotate causal ground truth or remove causal language.
4. Is GPCS just similarity? -> term ablations plus entailment baselines.
5. Is it calibrated? -> dev/test calibration and reliability plots.
6. Does it detect false claims? -> double-blind human support labels and AUROC/AUPRC.
7. Why self-consistency only? -> include NLI/citation/LLM-judge faithfulness baselines.
8. Is n=36 sufficient? -> power analysis, all eligible cases, RE3/second dataset.
9. Did it find the culprit? -> it was told service; rename task and add localisation experiment.
10. Are injected faults representative? -> scope claims and add production/second corpus.
11. Was test data used for tuning? -> pre-register, freeze weights/thresholds/prompts.
12. Does preprocessing leak? -> release manifests and fixed/random observation sensitivity.
13. Are agents better than one model? -> valid compute/token/time matched controls.
14. Are agents actually collaborative? -> critique arm or call them an ensemble.
15. Are GCP numbers probabilities? -> fitted weights and held-out calibration.
16. Are claim-level tests independent? -> scenario-clustered analysis/mixed model.
17. Why do diagrams conflict with code? -> replace all aspirational visuals before review.

## Prioritised roadmap and ideal experiment

**P0:** (1) freeze one primary RQ and split; (2) create blinded human claim-support labels with adjudication; (3) fit/freeze GPCS on development data then test once; (4) run matched retrieval controls; (5) run single-LLM/compute-matched agent controls; (6) track all current artefacts and immutable manifests.

**P1:** scale to all eligible RE2 plus RE3/second source; add GPCS/GCP/agent/retrieval ablations; repeat 3–5 runs; add one critique condition; replace stale documents and write a new honest manuscript.

**P2:** operator study, traces and second domain. **P3:** UI/cloud/product features.

Ideal study: all eligible RE2 incidents with source-system/fault-instance-held-out splits; RE3 or another corpus as OOD; conditions {none, raw, lexical, vector, graph-only, hybrid} through a fixed single LLM, then {single, self-consistency ensemble, independent specialists, critique specialists} on identical hybrid context. Measure service localisation and fault-type top-1/top-3 separately, evidence nDCG/recall@k plus human relevance, claim support AUROC/AUPRC/F1, GCP/GPCS calibration, latency/tokens/cost. Use 5 runs, scenario-cluster bootstrap/permutation tests, Holm correction and error taxonomy. Tables: data/splits, main comparisons, retrieval and verifier ablations, agents/cost, OOD. Figures: PR/reliability, paired incident effect plot, retrieval/latency frontier, error classes.

## Publication, admissions and PhD story

| Venue class | Current acceptance estimate | Why |
|---|---:|---|
| NeurIPS/ICML/ICLR/AAAI main | 0–2% | No valid main-paper experiment, unproven novelty, small/proxy labels. |
| ACL/EMNLP/NAACL main | 0–3% | Relevant verification idea, but no valid detection evaluation. |
| Applied AI systems/SE/ML | 3–10% | Excellent systems work; current evidence inadequate. |
| Workshop | 15–35% after an honest corrected narrow paper | Current drafts cannot be submitted. |
| Strong journal | 0–5% | Needs multi-dataset/multi-model study. |

| University | Current research readiness /10 | Current project /10 | After P0/P1 /10 | Largest difference |
|---|---:|---:|---:|---|
| Oxford | 6.0 | 6.5 | 8.5 | Independent validated finding + exceptional supervisor fit. |
| Cambridge | 6.0 | 6.5 | 8.5 | Novelty/evaluation beyond engineering. |
| Imperial | 6.5 | 7.0 | 8.5 | Controlled systems/ML empirical depth. |
| UCL | 6.5 | 7.0 | 8.5 | Human-labelled trustworthy-AI validation. |
| KCL | 7.0 | 7.0 | 8.5 | Rigorous thesis/paper from applied system. |
| Edinburgh | 6.5 | 7.0 | 8.5 | Generalisable AI-systems question and evidence. |

Best paper: **Does Provenance Improve Verification of LLM Incident Reports? A Controlled Study on Time-Indexed Microservice Telemetry.** Main claim: independently calibrated provenance scoring improves held-out supported/unsupported claim discrimination over evidence, self-consistency and LLM-judge baselines, or honestly does not. Main limitation: chaos-injected testbed telemetry is not production incident response.

Best PhD story: **trustworthy evidence-grounded AI for operational reasoning**, not generic multi-agent AI. Year 1: validate provenance/uncertainty across RCA data. Year 2: learned temporal/causal evidence selection plus human decision study. Year 3: serverless/security generalisation, calibrated abstention and benchmark release.

## Final scorecard

| Category | Current /10 | After work /10 |
|---|---:|---:|
| Research question | 6 | 8.5 |
| Novelty | 3.5 | 7 |
| Technical depth | 7.5 | 8.5 |
| Experimental rigor | 3.5 | 8 |
| Dataset | 5.5 | 8 |
| Baselines | 3 | 8 |
| Ablations | 2.5 | 8 |
| Statistical rigor | 4.5 | 8 |
| Reproducibility | 6.5 | 8.5 |
| Writing | 4.5 | 8 |
| Engineering quality | 8 | 8.5 |
| Research contribution | 4 | 8 |
| Publication readiness | 2.5 | 7.5 |
| PhD readiness | 6.5 | 8.5 |

**Current overall research score: 5.0/10. Potential: 8.0/10.**

Current level: strong engineering project/early MSc research artefact, not submission-ready. Potential: strong workshop or applied AI/SE paper; main-track potential only after replicated, broad positive results. Current PhD competitiveness: promising, but insufficient alone. Potential: strong portfolio component alongside grades, references, fit and ideally publication.

## THE 10 THINGS I SHOULD DO NEXT

| Rank | Action | Impact | Difficulty | Priority |
|---:|---|---|---|---|
| 1 | Freeze one RQ, hypothesis, split and protocol. | Stops moving-target claims/tuning. | Low | P0 |
| 2 | Double-blind human claim labels + adjudication. | Makes GPCS testable. | High | P0 |
| 3 | Development-only GPCS fitting and held-out test. | Makes confidence defensible. | Medium | P0 |
| 4 | Full matched retrieval baselines. | Tests whether graph earns complexity. | High | P0 |
| 5 | Valid single-LLM/ensemble/agent controls. | Separates calls, specialisation and consensus. | Medium | P0 |
| 6 | Scale/OOD test RE2+RE3/second corpus. | Addresses narrow n=36 data. | High | P1 |
| 7 | Retrieval/GPCS/GCP/agent ablations, 3–5 runs. | Supports causal attribution/variance. | High | P1 |
| 8 | Track immutable results/config/prompt manifests. | Enables review/reproduction. | Medium | P0 |
| 9 | Replace stale visuals and write new paper. | Removes reviewer trust failure. | Medium | P1 |
| 10 | Expert operator study + focused PhD proposal. | Demonstrates practical and research trajectory. | High | P2 |

If complete before September/October 2027, this becomes substantially stronger for all six target universities. Oxford/Cambridge would see a credible independent research trajectory rather than only an ambitious product; Imperial/UCL/Edinburgh a particularly strong trustworthy-AI/AI-systems profile; KCL a rigorous applied-AI portfolio. The decisive gains are human-labelled evidence, a publishable controlled result, and supervisor-specific framing—not additional product features.
