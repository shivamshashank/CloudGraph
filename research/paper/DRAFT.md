# DRAFT — target venue: "Who Verifies the Agents?" (NeurIPS 2026 Workshop)

> **STALE — DO NOT SUBMIT.** Every number below was computed from a
> benchmark pipeline confirmed to leak `ground_truth_claims` into
> `error_logs` (`self_consistency.py:120`, `evaluation.py:334`) and into
> the seeded Neo4j/Qdrant evidence itself (`seeding.py`), uniformly across
> all three context conditions. This invalidates the headline comparisons
> as currently reported. See the fix roadmap (targeting a corrected
> re-submission by Aug 25, 2026) before touching this file's numbers or
> claims. The structure, related work, and citations below remain a
> reasonable starting point for the rewrite — the results do not.

**Status:** first full draft, content-complete, not yet fitted to the NeurIPS
LaTeX template or page-trimmed. Deadline: Aug 29, 2026. Submission: OpenReview,
double-blind, 4-9 pages excluding references/appendices.

**Before submitting:**

1. Port into the NeurIPS 2026 `\documentclass` template (2-column).
2. This draft is already anonymized — no author name, institution, or
   identifying repo URL appears in the body below. Do not add them back
   into the body; they go on OpenReview's separate submission form only.
3. Trim to fit 4-9 pages once typeset — this draft is written comprehensive-
   first (~9-page-equivalent) so cutting is easier than padding.
4. Insert the 3 figures from `experiments/figures/` (retrieval_recall.png,
   unsupported_rate_by_claim_type.png, agreement_heatmap.png) at the
   marked `[FIGURE]` points once in LaTeX.
5. Every number below is sourced from `experiments/results/*.md` and
   `experiments/results/significance_tests.md` — do not adjust any of them
   without re-running `scripts/paired_bootstrap.py` and updating both places.

---

## Title

**Does More Agents Mean More Verification? A Matched-Compute Study of
Multi-Agent Hallucination and Graph-Grounded Claim Verification**

*(working alt title: "Who Verifies the Specialists? Evidence-Grounded Claim
Scoring and a Negative Result for Multi-Agent RCA")*

## Abstract (≈200 words)

Multi-agent LLM systems are increasingly deployed for real-world diagnostic
tasks, on the implicit assumption that decomposing a problem across
specialist agents improves both accuracy and trustworthiness. We test this
assumption on a real (non-simulated) multi-agent root-cause-analysis (RCA)
system built over a live Kubernetes knowledge graph, and introduce
Graph-Provenance Claim Scoring (GPCS), an evidence-grounded verification
mechanism that scores each atomic claim in a generated report by its
semantic and graph-topological proximity to retrieved evidence, contrasted
against a self-consistency baseline. Across 25 real incident scenarios we
find: (1) GPCS and self-consistency disagree on 36% of claims, indicating
the two verification signals have materially different blind spots rather
than being redundant; (2) structured, ranked retrieval measurably
outperforms both no-context and unranked raw-context conditions; and (3),
most importantly for verifying multi-agent systems specifically, a
matched-compute control shows the real 5-specialist-agent architecture is
*more* hallucination-prone than a single LLM sampled the same number of
times (44.2% vs. 31.5% unsupported-claim rate, paired 95% CI
[+0.053, +0.201], Wilcoxon p=0.0018) — a statistically significant negative
result. We argue this demonstrates that verifying multi-agent systems
requires scrutinizing the aggregation step itself, not just the individual
agents, and that no single verification signal available to us caught this
failure mode in isolation.

## 1. Introduction

Multi-agent LLM architectures are being deployed for increasingly
consequential, real-world tasks — code review, financial analysis,
infrastructure incident response — under the assumption, often implicit and
rarely tested against a compute-matched control, that decomposing a task
across specialist agents with a consensus step improves both accuracy and
trustworthiness over a single model call. Separately, a growing body of
work asks how such systems should be *verified*: current evaluation
practice largely tests isolated models rather than interactive, multi-agent
settings, and even the auditing mechanisms proposed for agentic systems can
themselves be corrupted or miscalibrated, since they are frequently
themselves LLM-based agents subject to the same failure modes they are
meant to detect [Oxford AIGI, 2026; Anthropic Alignment Science, 2026].

This paper reports on a real, deployed multi-agent system — CloudGraph, a
GraphRAG-powered root-cause-analysis platform for Kubernetes incidents —
built and evaluated not as a simulation but against live infrastructure
telemetry, a real knowledge graph, and real LLM calls throughout. We use it
as a testbed for two questions directly relevant to verifying agentic
systems:

**RQ1 (verifying claims).** Given a generated diagnostic report, does an
evidence-grounded verification signal (GPCS) agree with a purely behavioral
one (self-consistency across resampled generations), or do they catch
different failures? If they diverge substantially, relying on either one
alone under-verifies the system.

**RQ2 (verifying architecture).** Does a real multi-agent architecture
(five specialist agents plus a consensus step) actually reduce
hallucination relative to a matched-compute single-LLM baseline, or does
the added structure introduce new, unverified failure surface — specifically,
an unaudited aggregation step where a single weak specialist's error can be
woven into the final consensus without correction?

We report both as measured, including where the results are unflattering to
the system we built: **the real 5-agent architecture is significantly worse
than its own matched-compute single-LLM baseline on this benchmark.** We
believe this negative result is itself the paper's main contribution to
the "who verifies the agents" question — it is direct empirical evidence
that adding agents is not verification-neutral, and that the aggregation
step of a multi-agent system needs to be an explicit object of verification,
not an assumed-safe glue layer.

**Contributions:**

1. GPCS, an evidence-grounded claim-verification mechanism for graph-backed
   RAG systems, contrasted head-to-head against a self-consistency baseline
   on the same 1,685 scored claims (Section 4, 5.1).
2. A controlled, three-condition retrieval ablation (no context / unranked
   raw context / ranked GraphRAG context) isolating whether structured
   retrieval earns its complexity for claim grounding (Section 5.2).
3. A matched-compute control isolating whether a real multi-agent
   architecture's benefit (if any) comes from genuine multi-agent structure
   or is confounded with simply making more LLM calls — with a negative
   result reported as measured (Section 5.3).
4. All results are from a real, non-simulated system: real Kubernetes
   telemetry, a real Neo4j/Qdrant-backed knowledge graph, and real LLM API
   calls logged end-to-end, not a synthetic or offline-replay benchmark.

## 2. Related Work

**GraphRAG and structured retrieval.** GraphRAG [Edge et al., 2024] and
follow-on work typically assume a static, once-built graph over a fixed
document corpus. Our setting differs in that the graph is continuously
mutating operational telemetry, and retrieval already incorporates a
temporal-window constraint and recency-decay term not present in the
canonical formulation — we do not centre this distinction in the present
paper (it is out of scope for a verification-focused workshop) but note it
as context for why our retrieval ablation (Section 5.2) is a live system
comparison, not a replay over a fixed corpus.

**Hallucination detection.** The dominant self-consistency family
[Wang et al., 2023-class approaches: sample repeatedly, flag claims that do
not recur] is model-internal and domain-agnostic. GPCS is evidence-grounded
rather than model-internal, and specific to settings — like ours — where a
structured evidence graph already exists as a byproduct of the system
rather than as an added verification cost. We are not aware of prior work
directly comparing an evidence-grounded and a self-consistency-based
verifier head-to-head on the same claim set with paired statistical
testing, which is the comparison Section 5.1 provides.

**Multi-agent LLM systems and matched-compute controls.** Surveys of
multi-agent LLM systems [Guo et al., 2024] note that few papers claiming a
multi-agent benefit control for the "more LLM calls = better" confound.
AIOps papers claiming multi-agent benefits in particular rarely compare
against a matched-compute single-agent or ensemble baseline. Our matched-
compute control (Section 5.3) is a direct, real-system instance of this
missing comparison.

**Verifying agentic systems.** Current evaluation practice for agentic
systems is reported to concentrate on isolated-model benchmarks, with
interactive multi-agent evaluation "underdeveloped" [Oxford Martin AI
Governance Institute, *Open Problems in Frontier AI Risk Management*,
2026]. Separately, recent work on agentic misalignment has surfaced a
specific failure mode directly relevant to this paper: an auditing agent
can itself produce a corrupted evaluation, e.g. by sharing the objection of
the agent it is meant to be auditing and declining to flag it [Anthropic
Alignment Science Blog, Summer 2026]. Our matched-compute result is an
instance of the same underlying concern from a different angle — not an
auditor being corrupted, but a *consensus* step compounding rather than
correcting specialist error, which is invisible unless a matched-compute
control is explicitly run.

## 3. System

CloudGraph ingests Kubernetes telemetry (pod/deployment/node state, logs,
metrics, events) into a Neo4j property graph, indexes evidence documents in
Qdrant for dense retrieval, and answers incident-investigation queries via
three retrieval modes — keyword (lexical), vector (dense semantic), and
hybrid (vector similarity + graph hop-proximity + recency decay, i.e.
GraphRAG). Investigation requests are handled by five LLM-backed specialist
agents (monitoring, logs, deployment, topology, security), each producing
an independent finding, combined by a static-weight consensus engine into a
single report (title, cause, recommendation, severity, evidence).

### 3.1 Graph-Provenance Claim Scoring (GPCS)

Given a generated report, GPCS: (A) extracts atomic factual claims via a
structured-output LLM call, typed as `temporal`, `causal`,
`entity_relationship`, or `state`; (B) for each claim, retrieves candidate
supporting evidence via semantic search over the claim embedding and graph
traversal seeded from any named entities in the claim; (C) scores each
claim:

```text
trust_score = w1·semantic_alignment + w2·graph_proximity
            + w3·source_reliability - w4·path_length_penalty
```

where `semantic_alignment` is cosine similarity to the best-matching
evidence embedding, `graph_proximity = 1/(1+hop_distance)`, `source_
reliability` is a fixed per-evidence-type weight (metric/event readings
weighted above free-text logs), and `path_length_penalty` — the one
component with no analogue in CloudGraph's existing retrieval-ranking
formula — discounts claims resting on long inferential chains even when the
final hop is a strong match. Claims scoring below a calibrated threshold
(semantic-floor calibrated at 0.30 against live query score distributions,
distinguishing vague claims topping out at 0.16-0.30 from genuine matches
at 0.33-0.87) are labeled unsupported. (D) Report-level
`unsupported_claim_rate` is aggregated overall and by claim type.

### 3.2 Self-consistency baseline

For the same incident, the system generates 3 samples at elevated
temperature, extracts claims from each identically to GPCS Step A, and
flags a claim from the primary generation as unsupported if it does not
recur (by semantic match) across the other samples. This is model-internal
and requires no evidence graph, making it the natural behavioral-signal
contrast to GPCS's evidence-grounded signal.

## 4. Experimental Setup

**Benchmark.** 25 real incident scenarios spanning 5 categories
(Kubernetes, networking, security, deployment, observability), each with
ground-truth expected evidence tags, seeded into a live cluster and graph.

**Conditions.** Each scenario is run under 3 retrieval-context conditions —
`none` (agents reason from raw error logs alone, no retrieval),
`raw` (every seeded evidence item, concatenated, unranked), and `hybrid`
(GraphRAG's own ranked retrieval) — giving 75 (scenario × condition)
generation-and-scoring passes.

**Matched-compute control.** For the multi-agent-vs-single-LLM comparison
(Section 5.3), the *same* hybrid-retrieved evidence is given to two arms
per scenario: the real 5-agent-plus-consensus system (6 LLM calls: 5
specialists + 1 consensus), and a single LLM given the same evidence,
sampled 5 times and self-consistency-checked (5 LLM calls), with the
primary sample's claims scored by the identical GPCS instance used for the
agent arm — the verification method is held constant, only generation
architecture and call count vary (150 vs. 125 total calls across 25
scenarios — close, not identical, and we report this gap rather than
claim exact parity).

**Statistics.** All headline deltas are evaluated with paired bootstrap
confidence intervals (10,000 resamples, seed=42) and the Wilcoxon
signed-rank test, computed per-scenario (or per scenario×condition pair)
to respect the paired structure of the design, given the small sample
(n=25 scenarios; n=75 for the pooled scenario×condition comparison).

**Provenance.** Every LLM request/response for this run is logged
end-to-end (redacting credentials); this is a live-system run, not a
replay over cached model outputs.

## 5. Results

### 5.1 GPCS vs. self-consistency: divergent verification signals (RQ1)

Across all 75 scenario×condition passes, 1,777 claims were extracted;
GPCS scored 1,685 of them (94.8% — the remainder is a known claim-
segmentation mismatch between two independent extraction calls, not a
correctness bug, discussed in Section 6). Overall agreement between GPCS
and self-consistency: **1,079/1,685 (64.0%)**.

The two methods are not simply redundant. GPCS flags 43.7% of claims as
unsupported; self-consistency flags 51.5% — self-consistency is the
stricter signal, with median `recurrence_rate` of 0.0 (more than half of
all claims never recur verbatim across 3 samples at all). GPCS is more
lenient: any claim clearing the ~0.30 semantic-relevance floor with
reasonable graph proximity passes, regardless of whether it happens to
recur across samples. Of the 606 cases where the two methods disagree,
60.9% are GPCS-supported-but-self-consistency-unsupported, and 39.1% the
reverse — i.e. each method independently catches cases the other misses,
in both directions, not just one.

Paired bootstrap over all 75 groups: mean delta -0.087, 95% CI
**[-0.119, -0.055]** (excludes zero), Wilcoxon p≈0.0000 — the divergence is
statistically robust, not sampling noise.

By claim type, agreement clusters at 63-65% for causal/entity-relationship/
state claims, reaches 76.9% for temporal claims (n=26, small sample), and
is lowest — 60.4% — for `general` process-commentary claims ("the finding
is inconclusive"), which are inherently hardest to ground since they are
about the investigation process itself rather than a checkable fact.
`[FIGURE: unsupported_rate_by_claim_type.png]` `[FIGURE: agreement_heatmap.png]`

**Implication for verification design.** Neither signal dominates. A system
relying on only one — the common case in current practice — will silently
miss a substantial fraction (comparable in size to what it catches) of the
failures the other signal would flag.

### 5.2 Structured retrieval earns its complexity for claim grounding (RQ1, supporting)

| context condition | n claims | GPCS↔SC agreement | GPCS unsupported | SC unsupported |
|---|---|---|---|---|
| `hybrid` (ranked GraphRAG) | 578 | **66.1%** | **42.0%** | **47.9%** |
| `none` (no context) | 550 | 65.1% | 42.5% | 54.5% |
| `raw` (unranked dump) | 557 | 60.9% | 46.5% | 52.2% |

`hybrid` wins on every column; `raw` is worst on every column, *including*
agreement — worse than giving agents no retrieved context at all. Unranked
evidence is not neutral, it is actively harmful: more raw material gives
the generator more surface area to produce claims that sound
evidence-backed without being tied to the actually-relevant evidence.

The paired, per-scenario hybrid-vs-raw delta does not reach significance at
n=25 (mean +0.050, 95% CI **[-0.017, +0.114]**, Wilcoxon p=0.15) — we report
the direction as real and measured but the magnitude as not yet
statistically settled, consistent with our small-sample honesty policy
throughout this paper. A separate, purely retrieval-quality metric (tag
recall, not claim-level grounding) *does* reach significance: hybrid vs.
keyword tag-recall delta +0.150, 95% CI **[+0.060, +0.240]**, p=0.0055.
`[FIGURE: retrieval_recall.png]`

### 5.3 Matched-compute control: a negative result for multi-agent architecture (RQ2 — main finding)

| arm | LLM calls (25 scenarios) | mean unsupported rate | median |
|---|---|---|---|
| Real 5-agent consensus | 150 (6×25) | **44.2%** | 44.4% |
| Single-LLM (5-sample self-consistency) | 125 (5×25) | **31.5%** | 31.2% |

The single-LLM baseline had a *lower* hallucination rate in **19 of 25
scenarios** (agents won in 6, no ties). Paired per-scenario delta
(agents − single-LLM): mean **+0.127**, 95% CI **[+0.053, +0.201]**
(excludes zero), Wilcoxon p=**0.0018** — significant, not sampling noise.

**On this benchmark, the 5-specialist-agent architecture does not earn its
complexity over a matched-compute single-LLM baseline — it is measurably
more hallucination-prone, not less.** We report this as measured, per our
own pre-registered honesty guardrail against adjusting the evaluation
harness to flatter the system we built.

A plausible (not yet confirmed) mechanism: the five specialists report
independently and are combined by a static-weight consensus vote with no
cross-agent critique or correction step. A single low-confidence or
mistaken specialist finding can be woven into the final narrative without
being caught or revised. The single-LLM baseline has no such aggregation
step to introduce compounding error — it reasons over the same evidence
once, directly. This is, we argue, exactly the kind of failure mode
"verifying the agents" needs to target: not the individual specialist
calls, which are individually unremarkable, but the *aggregation step*,
which is where the architecture's own untested assumption (that combining
specialists helps) breaks down.

We note two limitations on this comparison specifically (see Section 6 for
the full list): call counts are close but not identical (150 vs. 125,
a small residual compute advantage for the single-LLM arm that does not
plausibly explain a 12.7-point gap), and claim-count asymmetry between arms
was not separately controlled for in this pass.

### 5.4 Neuro-symbolic retrieval ablation

Re-framing the three retrieval modes by symbolic/neural character (keyword
= symbolic, vector = neural, hybrid = neuro-symbolic), retrieval-quality
scores (does the method surface ≥50% of a scenario's expected evidence
tags) are near-ceiling for all three (vector 25/25, keyword 24/25, hybrid
24/25) — hybrid does not clearly beat either half on this metric, a result
we report plainly rather than adjust for. The qualitative pattern is more
informative than the aggregate: keyword's misses concentrate on
paraphrased/synonym-shifted concepts (e.g. missing "memory;killed" when the
evidence says "OOMKilled" verbatim); vector generalizes past these but
still struggles with numeric/status-code-style tags (e.g. `http_429`);
hybrid does not clearly correct keyword's specific misses, plausibly
because its recency-decay term can suppress otherwise-relevant older
evidence. With n=25 and only one scenario failing the retrieval-quality bar
outright, this is a suggestive pattern for a larger-sample follow-up, not a
settled finding.

## 6. Limitations

- **n=25 scenarios.** Every interval above is correspondingly wide; treat
  point estimates (e.g. "44.2% vs. 31.5%") as approximate even where the
  direction is statistically significant.
- **Single LLM provider** across all conditions in this run; cross-provider
  replication is future work.
- **5.2% of claims lack a GPCS score** due to independent claim
  segmentation between two separate extraction calls (self-consistency's
  and GPCS's) at nonzero sampling temperature — excluded from the joined
  agreement count, not miscounted, but shrinking the effective sample.
- **Matched-compute call counts are close, not identical** (150 vs. 125);
  we report the gap rather than claim exact parity.
- **GPCS's own verification is intentionally narrow** — it asks whether a
  claim is supported by *the specific evidence CloudGraph retrieved*, not
  whether it is true in any general sense. This is a deliberate scope
  choice (Section 3.1) but is itself a limitation on how far "verified by
  GPCS" can be read as "verified, full stop" — a point directly relevant to
  a workshop on verifying agents, since GPCS is itself an imperfect
  verifier with its own known blind spot (Section 5.1's 36% disagreement
  rate with an independent signal is direct evidence of this).

## 7. Discussion: implications for "who verifies the agents"

Two results in this paper speak directly to the workshop's central
question. First, two independent, reasonable verification signals for the
same claims disagree more than a third of the time — verifying an agentic
system's outputs with only one signal available today leaves a
comparably-sized blind spot, whichever one is chosen. Second, and more
consequentially, a real multi-agent architecture that was assumed (by its
own designers, prior to this control) to be more trustworthy than a single
model turned out, under a fair matched-compute comparison, to be
significantly *less* trustworthy — and no per-agent inspection would have
surfaced this, since each specialist's individual output is unremarkable;
the failure is emergent in the aggregation step. We think this is a
concrete, empirical argument that verifying multi-agent systems cannot
stop at verifying the agents' individual outputs or even the final report's
claims — it has to include a matched-compute, architecture-level check of
whether the *multi-agent structure itself* is earning its complexity, run
as a standard part of evaluating any such system before deployment.

## 8. Conclusion

We presented a real, deployed multi-agent RCA system, an evidence-grounded
claim verifier (GPCS) contrasted against a self-consistency baseline, and —
the paper's central empirical contribution — a matched-compute control
showing that adding agents made this particular system measurably *more*
hallucination-prone, not less. We report this as a genuine negative result,
consistent with treating honest measurement as the actual deliverable of
this line of work rather than a system-promotion exercise. We hope both the
method (matched-compute controls as a standard verification tool for
multi-agent claims) and the finding (aggregation, not just agent quality,
needs verification) are useful to the broader question this workshop is
organized around.

## References

*(to be formatted in the NeurIPS style once ported to LaTeX — draft list
below, add DOIs/arXiv IDs before submission)*

- Edge, D. et al. "From Local to Global: A Graph RAG Approach to
  Query-Focused Summarization." 2024.
- Guo, T. et al. "Large Language Model based Multi-Agents: A Survey of
  Progress and Challenges." 2024.
- Wang, X. et al. "Self-Consistency Improves Chain of Thought Reasoning in
  Language Models." 2023.
- Oxford Martin AI Governance Institute. "Open Problems in Frontier AI Risk
  Management." 2026.
- Anthropic Alignment Science Blog. "Agentic Misalignment in Summer 2026."
  2026.
- Google DeepMind. "Strengthening our Frontier Safety Framework." 2026.

---

## Appendix (if space allows / supplementary material)

- Full per-claim-type breakdown table (from `agreement_crosstab.csv`).
- Full matched-compute per-scenario raw numbers (`matched_compute_raw.csv`).
- The 5 real evidence-retrieval bugs fixed to get a valid run (entity-name
  truncation, excluded `Deployment` graph labels, mis-wired semantic-search
  callback, unthresholded Qdrant relevance floor, `Node`-prefix regex gap)
  — useful as a reproducibility/robustness appendix showing results are
  from a debugged, real pipeline, not a first-pass number.
