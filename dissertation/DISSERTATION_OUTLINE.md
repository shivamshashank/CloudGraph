# Dissertation Outline and Evidence Map

A chapter plan for the written dissertation, with the specific artefact that
supplies each section's evidence. Nothing in the "Evidence" column is
aspirational — every path listed exists in this repository today.

> **Confirm before writing.** The word count, chapter conventions, declaration
> wording, and submission format are set by your programme handbook, not by
> this file. The budget below is a proportional split of an assumed **15,000
> words**; rescale it once you have the real figure. See
> [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md).

---

## Front matter

| Item | Status |
|---|---|
| Title page | To write — see checklist for the fields your handbook requires |
| Declaration of originality | To write — use your institution's prescribed wording verbatim |
| Abstract (~300 words) | To write — must state the *narrow* claim, not the original ambition |
| Acknowledgements | To write |
| Table of contents, list of figures, list of tables | Generate at the end |

**Abstract must contain**, because these are the boundaries every reader will
otherwise assume away: the task is fault-type diagnosis for a *known* affected
service; the corpus is 36 RCAEval RE2 cases covering resource and network
faults only; the primary measure is inter-method concordance, not accuracy.

---

## Chapter 1 — Introduction (~1,200 words)

| Section | Content | Evidence |
|---|---|---|
| 1.1 Motivation | Incident evidence is fragmented across logs, metrics, traces, deployments, and commits | [`LITERATURE_REVIEW.md`](LITERATURE_REVIEW.md) §1 |
| 1.2 Problem statement | LLM-generated root-cause explanations are fluent but unverifiable | Lit review §7 |
| 1.3 Research questions | RQ1–RQ4, with RQ4 explicitly withdrawn as unmeasured | [`PROGRESS.md`](PROGRESS.md) — RQ and hypothesis tables |
| 1.4 Contributions | GPCS; a real-telemetry verification comparison; three documented negative/null results; a reproducible harness with integrity gates | [`experiments/FINDINGS.html`](../experiments/FINDINGS.html) |
| 1.5 Scope and non-claims | State the three boundaries from the abstract, once, explicitly | [`experiments/README.md`](../experiments/README.md) |
| 1.6 Dissertation structure | — | — |

## Chapter 2 — Background and Literature Review (~2,500 words)

Lift directly from [`LITERATURE_REVIEW.md`](LITERATURE_REVIEW.md); it is already
sectioned for this purpose.

| Section | Source section |
|---|---|
| 2.1 Retrieval-augmented generation | §2 |
| 2.2 GraphRAG and graph retrieval | §3 |
| 2.3 Knowledge graphs for incident reasoning | §4 |
| 2.4 AIOps, RCA, and benchmarking | §5 |
| 2.5 Multi-agent LLM systems | §6 |
| 2.6 Hallucination detection and claim verification | §7 |
| 2.7 Observability foundations | §8 |
| 2.8 Research gap | §9 |

## Chapter 3 — System Design (~2,500 words)

| Section | Content | Evidence |
|---|---|---|
| 3.1 Architecture overview | The evaluated pipeline end to end | [`docs/architecture/figures/current-architecture.svg`](../docs/architecture/figures/current-architecture.svg) |
| 3.2 Knowledge graph schema | Node labels, relationships, constraints | [`graph/schema.cypher`](../graph/schema.cypher), `knowledge-graph-schema.png` |
| 3.3 Ingestion adapters | Prometheus, Loki, webhooks, graph constructor | [`services/api/app/adapters/`](../services/api/app/adapters/), [`PROGRESS.md`](PROGRESS.md) Week 3 |
| 3.4 Retrieval | Traversal, embeddings, hybrid ranker and its three weights | [`retrieval/hybrid_ranker.py`](../services/api/app/retrieval/hybrid_ranker.py), [`PROGRESS.md`](PROGRESS.md) Week 4 |
| 3.5 Multi-agent investigation | The five specialists and static consensus | [`docs/architecture/figures/04-multi-agent-workflow.svg`](../docs/architecture/figures/04-multi-agent-workflow.svg) |
| 3.6 GCP | Noisy-OR propagation with hop decay | [`docs/design/GCP_DESIGN.md`](../docs/design/GCP_DESIGN.md) |
| 3.7 **GPCS** — the contribution | Claim extraction, evidence retrieval, trust score, the fixed 0.30 / 0.50 thresholds | [`docs/design/GPCS_DESIGN.md`](../docs/design/GPCS_DESIGN.md) |
| 3.8 Design evolution | What the original design promised and why it changed | [`docs/architecture/design-evolution.md`](../docs/architecture/design-evolution.md) |

**Do not describe GPCS thresholds as calibrated.** They are fixed defaults set
by inspecting live score distributions; no held-out fitting was performed. §3.7
should say so in one sentence rather than leave it to the examiner to find.

## Chapter 4 — Implementation (~2,000 words)

| Section | Content | Evidence |
|---|---|---|
| 4.1 Deployment | kubeadm/Rancher + Helm, and why Terraform/EKS was abandoned | [`docs/guides/INSTALLATION.md`](../docs/guides/INSTALLATION.md), `PROGRESS.md` W2 |
| 4.2 Services | API, investigation-engine, agent-orchestrator, UI, Go CLI | [`docs/architecture/system-overview.md`](../docs/architecture/system-overview.md) |
| 4.3 Storage | Neo4j, Qdrant, and the hashed-file fallback | `services/semantic_store.py` |
| 4.4 LLM integration | Per-request provider settings; the Ollama experiment and its reversal | `PROGRESS.md` W8 Phase A |
| 4.5 Engineering practice | CI, pre-commit, lint policy, 123-test suite | `.github/workflows/`, `services/api/tests/` |

## Chapter 5 — Evaluation Methodology (~2,000 words)

This is the chapter an examiner will read most carefully. It is also the
chapter where the project's real strength lies.

| Section | Content | Evidence |
|---|---|---|
| 5.1 Benchmark | RCAEval RE2, 36 cases, deterministic selection, MIT licence, checksums | [`experiments/DATA_PROVENANCE.md`](../experiments/DATA_PROVENANCE.md) |
| 5.2 Task definition | Fault-type diagnosis for a known affected service | §5.1 source |
| 5.3 Conditions | Retrieval context `none`/`raw`/`hybrid`; retrieval mode keyword/vector/hybrid | [`experiments/README.md`](../experiments/README.md) |
| 5.4 Verifiers | Self-consistency (3 samples, T=0.8, recurrence ≥ 0.8) vs GPCS | `research/self_consistency.py`, `research/gpcs.py` |
| 5.5 Measures | `agreement` (concordance), `strict_correct`, `recall`, `precision`, `f1` | `scripts/merge_reports.py` |
| 5.6 Statistics | Scenario-clustered paired bootstrap (seed 42) + Wilcoxon | `scripts/paired_bootstrap.py` |
| 5.7 **Evaluation integrity** | The four defects, their fixes, and the regression tests that pin them | `tests/test_evaluation_integrity.py`, `PROGRESS.md` W9 |

§5.7 is not an appendix item. Four defects each produced confident, invalid
numbers before being caught; presenting them, with the tests that now prevent
recurrence, is stronger evidence of research maturity than presenting a clean
run would be.

## Chapter 6 — Results (~2,500 words)

Every figure and number comes from
[`experiments/results/`](../experiments/results/) and
[`experiments/figures/`](../experiments/figures/); regenerate rather than
retype.

| Section | Finding | Verdict |
|---|---|---|
| 6.1 Corpus | 36 scenarios, 3,685 claims, 0 exclusions, build `9787fde`, digest `sha256:81c48641` | — |
| 6.2 GPCS vs self-consistency | 70.3% vs 57.9% unsupported; Δ +0.119, CI [+0.073, +0.163], p<0.0001 | **Significant** |
| 6.3 Retrieval recall | hybrid − keyword = +0.190, CI [+0.116, +0.269], p=0.0003 | **Significant** |
| 6.4 Retrieval context | hybrid vs raw concordance +0.024, CI [−0.028, +0.077], p=0.302 | **Null** |
| 6.5 Vector ≡ hybrid | Identical on every measure — the graph adds nothing to retrieval here | **Negative** |
| 6.6 Keyword failure is lexical | Strict 0/36; two-token fault labels (delay, loss, mem) score 0/6 while single-token labels score well | **Diagnostic** |
| 6.7 Neither verifier discriminates | Both correct-vs-incorrect gaps −0.8 pp on 155 auto-labelled claims (4.2% coverage) | **Negative** |
| 6.8 Run-to-run variance | Per-condition concordance moved 12 points across four isolated re-runs of identical scenarios | **Limitation** |

## Chapter 7 — Discussion (~1,500 words)

- 7.1 What the significant result does and does not mean — strictness is not aim.
- 7.2 Why the graph helped scoring but not retrieval.
- 7.3 The lexical retrieval failure as a benchmark-label mismatch rather than a system failure.
- 7.4 What the null and negative results are worth: three pre-registered-style comparisons that could have gone either way and were reported as they landed.
- 7.5 Threats to validity — see below.

### Threats to validity (write this section in full; the material is real)

**Construct.** The headline measure is *concordance* between two verifiers,
not accuracy against ground truth. Both verifiers can be wrong on the same
claim and it scores as agreement. Automatic correctness labels cover only 4.2%
of claims, and on that subset neither verifier discriminates.

**Internal.** Four integrity defects invalidated all earlier runs; the citable
run postdates every fix and is pinned by regression tests, but the history
means results before commit `9787fde` must not be cited. LLM sampling
temperature is 0.8 and these provider APIs expose no seed, so run-to-run
variance of up to 12 points on per-condition concordance is irreducible here —
single-condition comparisons within one batch are noise.

**Statistical.** Bootstrap resampling clusters by scenario (n=36), not by
scenario×condition (n=108); the earlier un-clustered version was
pseudo-replication and overstated precision.

**Confounding.** Each batch of six scenarios covers only two fault types while
being balanced across the three systems. Results must never be reported by
batch — batch and fault type are confounded by construction.

**External.** RE2 contains only resource and network faults: no configuration
errors, security events, deployment failures, DNS faults, or certificate
expiry. Three systems, all open-source microservice demos, none a production
workload. The affected service is given, so nothing here speaks to root-cause
localisation. GPCS thresholds are uncalibrated defaults, so the 70.3% figure
is a property of those defaults as much as of the method.

**Reproducibility.** Case selection is deterministic and the bootstrap is
seeded; the remaining variance is the provider's sampling, which is stated as
a limitation rather than worked around.

## Chapter 8 — Conclusion and Future Work (~1,000 words)

- 8.1 Contributions restated at their real size.
- 8.2 Answers to RQ1–RQ4, including the two that are not answered.
- 8.3 Future work, in priority order:
  1. Human-labelled correctness on a stratified claim sample — the only way to settle whether GPCS is better *aimed* rather than merely stricter.
  2. Re-run the matched-compute control on the corrected pipeline, closing RQ2/H2.
  3. Calibrate GPCS thresholds on held-out data; report Brier score and reliability diagrams.
  4. Extend to RCAEval RE3 (code-level faults) to widen beyond resource and network faults.
  5. API authentication before any deployment that stores a live provider key.

## Appendices

| Appendix | Content | Evidence |
|---|---|---|
| A | Graph schema in full | [`graph/schema.cypher`](../graph/schema.cypher) |
| B | GPCS formulation and worked example | [`docs/design/GPCS_DESIGN.md`](../docs/design/GPCS_DESIGN.md) |
| C | Benchmark case table and checksums | [`experiments/DATA_PROVENANCE.md`](../experiments/DATA_PROVENANCE.md) |
| D | Full significance-test output | [`experiments/results/significance_tests.md`](../experiments/results/significance_tests.md) |
| E | Evaluation-integrity defects and regression tests | `tests/test_evaluation_integrity.py` |
| F | Reproduction instructions | [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) §Artefact |
| G | Week-by-week development log | [`PROGRESS.md`](PROGRESS.md) |

---

## Word budget

| Chapter | Words | % |
|---|---|---|
| 1 Introduction | 1,200 | 8 |
| 2 Background | 2,500 | 17 |
| 3 Design | 2,500 | 17 |
| 4 Implementation | 2,000 | 13 |
| 5 Methodology | 2,000 | 13 |
| 6 Results | 2,500 | 17 |
| 7 Discussion | 1,500 | 10 |
| 8 Conclusion | 1,000 | 7 |
| **Total** | **15,200** | |

Front matter, references, and appendices are normally excluded from the count
— confirm against your handbook.

## Writing rules for this dissertation

Carried over from the documentation-honesty pass applied across the repository.

1. Never cite a number from before commit `9787fde`. Anything reporting
   "64.0% agreement", "44.2% vs 31.5%", or "n=25" refers to an invalidated run.
2. Never write "calibrated" of GPCS or GCP parameters.
3. Never describe `agreement` as accuracy.
4. Never describe the system as locating the culprit service.
5. Never report results by batch.
6. Say "five agents", not seven; "static consensus", not a consensus agent.
7. Regenerate figures and tables from `experiments/` rather than retyping them.
