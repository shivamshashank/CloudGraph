# DRAFT — target venue: NORA 2026, "Workshop on Knowledge Graphs & Agentic

Systems Interplay" (AACL-IJCNLP 2026)

> **STALE — DO NOT SUBMIT.** Same underlying benchmark leakage as
> `research/paper/DRAFT.md` (see that file's header for the exact
> confirmed cause). This draft's numbers are invalid until the fix
> roadmap completes and experiments are re-run. The figures this
> draft referenced have been deleted along with the invalid results. Structure and citations
> are a reasonable starting point for the rewrite; the results are not.

**Status:** first full content draft, not yet fitted to the ACL LaTeX
template. Deadline: Sept 9, 2026. Submission: OpenReview, double-blind,
research papers up to 8 pages (references/appendices unlimited).

**Important — do not submit this alongside the NeurIPS "Who Verifies the
Agents?" paper unmodified.** NORA's CFP explicitly prohibits concurrent
submission of "identical or substantially similar manuscripts" to another
peer-reviewed venue. This draft is deliberately structured around a
different primary question and a different headline result than
`research/paper/DRAFT.md` — see the note at the end of this file for
exactly what's shared vs. different. Read that note before submitting
either paper to confirm the differentiation is real, not cosmetic.

**Before submitting:**

1. Port into the official ACL style template (fetch from the ACL
   Anthology / ACL-org style-files repo, not the NeurIPS one used for the
   other paper).
2. Already anonymized in the body below — no author name, institution, or
   identifying repo URL. Keep it that way; real identity goes on
   OpenReview's form only.
3. Insert the 3 figures from `experiments/figures/` at the marked
   `[FIGURE]` points, plus the neuro-symbolic detail table if space
   allows (8-page limit is tighter than the NeurIPS paper's 4-9).
4. Every number is sourced from `experiments/results/*.md` — do not adjust
   without re-running `scripts/paired_bootstrap.py` and updating both
   places.

---

## Title

**Does Graph Structure Earn Its Keep? Grounding Agent Memory in a Live
Operational Knowledge Graph for Hallucination Mitigation**

*(working alt title: "Knowledge-Graph-Grounded Claim Verification for
Multi-Agent Reasoning: A Live-System Study")*

## Abstract (≈200 words)

Agentic systems that reason over knowledge graphs are typically evaluated
on static, once-built graphs constructed from a fixed document corpus.
We study a different setting — a knowledge graph that is continuously
mutating operational infrastructure telemetry — and ask two questions
central to grounding agent memory in such graphs: does the graph's
structure (multi-hop traversal, ranked retrieval) earn its complexity
over unranked or absent retrieval, and does grounding an agent's claims
explicitly in retrieved graph evidence catch hallucinations that a
purely behavioral signal misses? We introduce Graph-Provenance Claim
Scoring (GPCS), which scores each atomic claim in an agent-generated
report by its semantic and graph-topological proximity to retrieved
evidence, and evaluate it on a real (non-simulated) multi-agent
root-cause-analysis system built over a live Kubernetes knowledge graph.
Across 25 real incident scenarios and three retrieval-context conditions,
we find structured, ranked graph retrieval measurably outperforms both
unranked and absent retrieval on every measured column, and that
graph-grounded claim verification disagrees with a self-consistency
baseline on 36% of claims — each independently catching failures the
other misses. A neuro-symbolic ablation further shows keyword (symbolic)
and vector (neural) retrieval fail in different, complementary ways,
suggesting the value of graph structure for agent memory is not fully
captured by either retrieval paradigm alone. All results are from a real,
live system with real LLM calls logged end-to-end, not an offline replay.

## 1. Introduction

Agentic systems increasingly use knowledge graphs as external memory:
structured, queryable stores of entities and relationships that ground an
agent's reasoning beyond its parametric knowledge. Most evaluations of
this pattern, following the GraphRAG line of work, assume a static graph
built once from a fixed document corpus, and ask whether graph-structured
retrieval improves the quality of generated answers. Two questions in
this space are comparatively underexplored, and are the focus of this
paper: first, does graph structure retain its value in a *continuously
mutating* operational setting, where the graph is not a fixed knowledge
base but live infrastructure telemetry updated in real time; and second,
once an agent has generated a claim grounded (in principle) in such a
graph, how do we verify that the claim is actually supported by what was
retrieved, rather than merely plausible-sounding?

We study both questions on a real, deployed multi-agent
root-cause-analysis (RCA) system for Kubernetes incidents, which we refer
to throughout as the *RCA system* to preserve anonymity. The system
ingests live cluster telemetry into a Neo4j knowledge graph, retrieves
evidence via three modes (keyword, vector, and a hybrid graph-traversal
mode), and reasons over that evidence with LLM-backed agents. We use it
as a live testbed, not a simulation, for:

**RQ1 (does graph structure earn its keep for agent memory?).** Does
ranked, graph-structured retrieval over this live knowledge graph
outperform unranked retrieval or no retrieval at all, for the purpose of
grounding an agent's subsequent claims?

**RQ2 (how do we verify graph-grounded claims?).** Given a claim an agent
makes after consulting the graph, does an evidence-grounded verification
signal — Graph-Provenance Claim Scoring (GPCS), which we introduce —
agree with a purely behavioral verification signal (self-consistency
across resampled generations), or do the two catch different failures?

We report both as measured on real, live-system data: 25 incident
scenarios, three retrieval-context conditions, 1,777 extracted claims,
and full LLM request/response logging throughout. A supplementary,
narrower question — whether a specific 5-agent architecture built on top
of this graph earns its computational complexity — is discussed briefly
in Section 7 as a caveat on architecture design, not this paper's central
contribution.

**Contributions.**

1. GPCS, a claim-verification mechanism that grounds agent claims in
   explicit graph provenance (semantic alignment, graph hop-distance,
   source reliability, and a path-length trust penalty), contrasted
   against a self-consistency baseline on 1,685 scored claims (Section
   4).
2. A controlled, three-condition ablation isolating whether graph
   structure earns its complexity for grounding agent memory, on a live,
   continuously-mutating operational graph rather than a static corpus
   (Section 5.1).
3. A neuro-symbolic ablation decomposing retrieval into its symbolic
   (keyword), neural (vector), and combined (graph-hybrid) components,
   showing where each fails and where graph structure adds value beyond
   either alone (Section 5.3).
4. All results are from a real, deployed system: real Kubernetes
   telemetry, a real Neo4j-backed knowledge graph under continuous
   mutation, and real LLM API calls logged end-to-end.

## 2. Related Work

**Knowledge graphs as agent memory.** Work on grounding LLM agents in
knowledge graphs, and on knowledge-graph-augmented retrieval more
broadly (GraphRAG and its variants), typically assumes a graph built
once from a static document collection. Our setting differs in a way we
believe is relevant to agent memory specifically: the graph here is
live operational telemetry, continuously extended as new evidence
arrives, and retrieval must respect a temporal-window constraint (an
evidence item is only relevant if it falls within the incident's time
window) in addition to topical relevance — a constraint with no direct
analogue when the underlying corpus is fixed.

**Hallucination mitigation via grounding.** Grounding claims in
retrieved evidence is a standard hallucination-mitigation strategy, but
verifying that a generated claim is actually supported by what was
retrieved — as opposed to merely retrieving relevant-looking evidence and
hoping the generation respects it — is a distinct problem. The dominant
alternative family, self-consistency, is model-internal: it samples
repeatedly and flags claims that do not recur, without reference to any
external evidence store at all. GPCS is evidence-grounded instead,
scoring each claim's proximity to the specific graph evidence retrieved
for it. Section 4 provides, to our knowledge, one of the few head-to-head
comparisons of an evidence-grounded and a self-consistency-based
verifier on the same claim set with paired statistical testing.

**Multi-agent reasoning over graphs.** Surveys of multi-agent LLM systems
note that architectural claims (e.g., that decomposing reasoning across
specialist agents improves quality) are rarely tested against a
compute-matched control. This paper's primary contributions concern
graph-grounded memory and verification rather than multi-agent
architecture per se; we return to a brief, secondary finding on this
point in Section 7.

## 3. System

The RCA system ingests Kubernetes telemetry (pod/deployment/node state,
logs, metrics, events) into a Neo4j property graph and indexes evidence
documents in Qdrant for dense retrieval. Three retrieval modes answer
incident-investigation queries: keyword (lexical, symbolic), vector
(dense semantic, neural), and hybrid (vector similarity + graph
hop-proximity + recency decay — a neuro-symbolic combination we term
GraphRAG-style retrieval in this operational setting). Investigation
requests are handled by LLM-backed specialist agents whose findings are
combined into a single report (title, cause, recommendation, severity,
evidence); the agents' internal architecture is orthogonal to this
paper's questions and is described only as needed for reproducibility in
Section 4.

### 3.1 Graph-Provenance Claim Scoring (GPCS)

Given a generated report, GPCS: (A) extracts atomic factual claims via a
structured-output LLM call, typed as `temporal`, `causal`,
`entity_relationship`, or `state`; (B) for each claim, retrieves candidate
supporting evidence via semantic search over the claim embedding and
graph traversal seeded from any named entities in the claim; (C) scores
each claim:

```text
trust_score = w1 * semantic_alignment + w2 * graph_proximity
            + w3 * source_reliability - w4 * path_length_penalty
```

`semantic_alignment` is cosine similarity to the best-matching evidence
embedding; `graph_proximity = 1 / (1 + hop_distance)` rewards claims
whose supporting evidence is graph-topologically close to the incident;
`source_reliability` is a fixed per-evidence-type weight (a metric or
event reading is weighted above a free-text log line); and
`path_length_penalty` — the one component with no analogue in the
system's existing retrieval-ranking formula — discounts claims resting
on long inferential chains through the graph even when the final hop is
a strong match, reflecting that verification (unlike retrieval ranking)
should treat a long chain of weak intermediate relationships as grounds
for lower trust. Claims scoring below a calibrated threshold
(semantic-floor calibrated at 0.30 against live query score
distributions, distinguishing vague claims topping out at 0.16-0.30 from
genuine matches at 0.33-0.87) are labeled unsupported.

### 3.2 Self-consistency baseline

For contrast, the system also generates 3 samples at elevated
temperature per incident, extracts claims from each identically to GPCS
Step A, and flags a claim from the primary generation as unsupported if
it does not recur across the other samples. This signal requires no
graph at all — it is purely behavioral, making it the natural baseline
for asking whether graph-grounded verification adds something a
model-internal signal does not.

## 4. Experimental Setup

**Benchmark.** 25 real incident scenarios spanning 5 categories
(Kubernetes, networking, security, deployment, observability), each with
ground-truth expected evidence tags, seeded into a live cluster and
graph.

**Conditions (for RQ1).** Each scenario is run under 3 retrieval-context
conditions: `none` (agents reason from raw error logs alone, no graph
consulted), `raw` (every seeded evidence item for the scenario,
concatenated, unranked — the graph is consulted but its structure is
discarded), and `hybrid` (the graph's own ranked, structure-aware
retrieval). This isolates whether the graph's *structure* — not just its
existence as a data source — is what earns any observed benefit.

**Statistics.** All headline deltas use paired bootstrap confidence
intervals (10,000 resamples, seed=42) and the Wilcoxon signed-rank test,
computed per-scenario or per scenario x condition pair to respect the
paired design, given the small sample (n=25 scenarios; n=75 pooled).

**Provenance.** Every LLM request/response is logged end-to-end
(credentials redacted); this is a live-system run, not a replay over
cached outputs.

## 5. Results

### 5.1 Does graph structure earn its keep for agent memory? (RQ1)

| context condition | n claims | GPCS<->SC agreement | GPCS unsupported | SC unsupported |
|---|---|---|---|---|
| `hybrid` (ranked graph retrieval) | 578 | **66.1%** | **42.0%** | **47.9%** |
| `none` (no graph consulted) | 550 | 65.1% | 42.5% | 54.5% |
| `raw` (graph consulted, structure discarded) | 557 | 60.9% | 46.5% | 52.2% |

`hybrid` wins on every column; `raw` — consulting the graph but ignoring
its structure — is worst on every column, including *worse than not
consulting the graph at all*. This is the paper's central answer to RQ1:
graph structure is not incidental to why grounding in a knowledge graph
helps; discarding it while still nominally "using" the graph is actively
harmful, because unranked evidence gives the generating agent more
surface area to produce claims that sound evidence-backed without being
tied to what is actually relevant. `[FIGURE: retrieval_recall.png]`

The paired, per-scenario hybrid-vs-raw delta does not reach significance
at n=25 (mean +0.050, 95% CI [-0.017, +0.114], Wilcoxon p=0.15) — we
report the direction as real and measured but the magnitude as not yet
statistically settled. A separate, purely retrieval-quality metric (tag
recall) does reach significance: hybrid vs. keyword tag-recall delta
+0.150, 95% CI [+0.060, +0.240], p=0.0055.

### 5.2 Graph-grounded verification catches different failures than behavioral verification (RQ2)

Across all 75 scenario x condition passes, 1,777 claims were extracted;
GPCS scored 1,685 (94.8%; the remainder is a known claim-segmentation
mismatch between two independent extraction calls, discussed in Section
6). Overall agreement between GPCS and self-consistency: **1,079/1,685
(64.0%)**. Paired bootstrap over all 75 groups: mean delta -0.087, 95%
CI [-0.119, -0.055] (excludes zero), Wilcoxon p<0.0001 — the divergence
is statistically robust.

GPCS flags 43.7% of claims unsupported; self-consistency flags 51.5%.
Self-consistency is the stricter signal (median recurrence rate 0.0 —
more than half of all claims never recur verbatim across 3 samples at
all); GPCS is more lenient, passing any claim clearing the semantic
floor with reasonable graph proximity regardless of recurrence. Of the
606 disagreement cases, 60.9% are GPCS-supported-but-SC-unsupported and
39.1% the reverse: each signal independently catches cases the other
misses, in both directions. `[FIGURE: unsupported_rate_by_claim_type.png]`
`[FIGURE: agreement_heatmap.png]`

By claim type, agreement is lowest (60.4%) for `general` process-
commentary claims and highest (76.9%, n=26) for `temporal` claims —
claims about *when* something happened are easier for both signals to
agree on than claims about the investigation process itself.

**Implication for agent memory design.** A system that verifies agent
claims with only one signal — the common case in current practice — will
silently miss a substantial fraction, comparable in size to what it
catches, of the failures the other signal would flag. Grounding in graph
provenance and checking behavioral consistency are complementary
memory-verification strategies, not substitutes.

### 5.3 A neuro-symbolic decomposition of retrieval

Re-framing the three retrieval modes by symbolic/neural character
(keyword = symbolic, vector = neural, hybrid = neuro-symbolic),
retrieval-quality scores (does the method surface >=50% of a scenario's
expected evidence tags) are near-ceiling for all three (vector 25/25,
keyword 24/25, hybrid 24/25) — at this coarse bar, hybrid does not
clearly beat either half. The qualitative pattern is more informative:
keyword's misses concentrate on paraphrased or synonym-shifted concepts
(e.g., missing "memory;killed" when the evidence literally says
"OOMKilled"); vector generalizes past these but still struggles with
numeric/status-code-style tags (e.g., `http_429`); hybrid does not
clearly correct keyword's specific misses, plausibly because its
recency-decay term can suppress otherwise-relevant older evidence. This
suggests that for agent memory grounded in operational graphs, symbolic
and neural retrieval fail in different, complementary ways that a naive
combination does not automatically resolve — a finding relevant to
designing memory-retrieval mechanisms for graph-grounded agents more
generally, not specific to this system.

## 6. Limitations

- **n=25 scenarios** — every interval above is correspondingly wide;
  treat point estimates as approximate even where directions are
  significant.
- **Single LLM provider** across all conditions; cross-provider
  replication is future work.
- **5.2% of claims lack a GPCS score**, due to independent claim
  segmentation between two separate extraction calls at nonzero sampling
  temperature — excluded from the joined count, not miscounted, but
  shrinking the effective sample.
- **GPCS's verification scope is intentionally narrow**: it asks whether
  a claim is supported by the specific evidence this graph retrieved, not
  whether the claim is true in any general sense. Section 5.2's 36%
  disagreement rate with an independent signal is itself evidence that
  GPCS has its own blind spots as a verifier, not a settled ground truth.
- **The neuro-symbolic ablation (Section 5.3) is suggestive, not
  conclusive**, at n=25 with only one scenario failing the retrieval bar
  outright.

## 7. Discussion

Two findings speak directly to designing agent memory over operational
knowledge graphs. First, structure is not incidental: an agent that
consults a knowledge graph but discards its structure (Section 5.1's
`raw` condition) performs *worse* than an agent that never consults the
graph at all, because unranked evidence expands the surface area for
plausible-but-ungrounded claims. Memory systems for graph-grounded agents
should treat structured retrieval as load-bearing, not optional
polish. Second, no single verification signal available to us — graph
provenance or behavioral consistency — is sufficient alone; each misses
a comparably-sized set of real failures the other catches (Section 5.2).

A narrower, secondary finding, orthogonal to this paper's main questions
but worth reporting: when we separately tested whether this system's
specific 5-specialist-agent architecture earns its computational
complexity over a matched-compute single-LLM baseline (same retrieved
graph evidence, same GPCS verification, only generation architecture
differing), the single-LLM baseline had a *lower* hallucination rate
(31.5% vs. 44.2% mean unsupported-claim rate, paired 95% CI [+0.053,
+0.201], Wilcoxon p=0.0018). We do not centre this result here — it
concerns agent architecture, not graph-grounded memory or verification —
but it is a relevant caution for this workshop's broader interest in
agentic systems: adding agents on top of a well-grounded memory system is
not automatically an improvement, and the aggregation step deserves the
same scrutiny as the memory and retrieval layers this paper focuses on.

## 8. Conclusion

We studied a live, continuously-mutating operational knowledge graph as
agent memory, and found that its structure earns its complexity for
grounding agent claims — discarding structure while still nominally
consulting the graph is actively harmful, not neutral. We introduced
GPCS, a graph-provenance claim-verification mechanism, and showed it
diverges substantially from a self-consistency baseline, indicating the
two are complementary rather than redundant verification signals for
graph-grounded agent memory. A neuro-symbolic decomposition of retrieval
further suggests symbolic and neural retrieval modes fail in different
ways that naive combination does not automatically resolve. We hope
these findings are useful to the broader question of how to design and
verify agent memory grounded in knowledge graphs.

## References

- Edge, D. et al. "From Local to Global: A Graph RAG Approach to
  Query-Focused Summarization." arXiv:2404.16130, 2024.
- Wang, X. et al. "Self-Consistency Improves Chain of Thought Reasoning
  in Language Models." ICLR 2023, arXiv:2203.11171.
- Guo, T. et al. "Large Language Model based Multi-Agents: A Survey of
  Progress and Challenges." IJCAI 2024, arXiv:2402.01680.

---

## Differentiation note (read before submitting either paper)

Both papers draw on the same underlying CloudGraph experiment run
(`experiments/results/`), which is legitimate — they are two distinct
analyses of one real dataset, not duplicate publication, as long as each
paper's *primary contribution and headline result* differ. Concretely:

| | NeurIPS "Who Verifies the Agents?" | NORA (this draft) |
|---|---|---|
| Primary RQ | Does a 5-agent architecture earn its complexity over matched-compute? | Does graph structure earn its complexity for agent memory grounding? |
| Headline result | Matched-compute negative result (5-agent hallucinates *more*) | Structured retrieval beats unranked/no retrieval; graph-grounded vs. behavioral verification diverge |
| Matched-compute result | Section 5.3, the paper's central finding | Section 7, one brief paragraph, explicitly framed as secondary/orthogonal |
| Neuro-symbolic ablation | Section 5.4, brief | Section 5.3, expanded with more qualitative detail |
| Framing | Verifying multi-agent systems (aggregation-step scrutiny) | Grounding agent memory in knowledge graphs (retrieval-structure and claim-verification) |

If NORA's reviewers or organizers would read the two side by side and
conclude they are "substantially similar," that is a real risk under
their explicit dual-submission policy — re-read both drafts once final
and, if in doubt, cut the matched-compute paragraph from this draft
entirely rather than risk it.
