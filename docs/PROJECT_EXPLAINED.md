# CloudGraph, explained

What the system does, what was asked of it, and what the measurements said.

Every figure here comes from `experiment-1-benchmark/results/` — `significance_tests.md`,
`correctness_labels.md`, `summary.txt` and `claims.csv`. Nothing is estimated.

---

## Contents

1. [The problem](#1-the-problem)
2. [The idea](#2-the-idea)
3. [How the system works](#3-how-the-system-works)
4. [The two original mechanisms](#4-the-two-original-mechanisms)
5. [What "supported" and "unsupported" actually mean](#5-what-supported-and-unsupported-actually-mean)
6. [How it was evaluated](#6-how-it-was-evaluated)
7. [The seven research questions](#7-the-seven-research-questions)
8. [Results in full](#8-results-in-full)
9. [Why the negative result is the useful one](#9-why-the-negative-result-is-the-useful-one)
10. [What the evaluation cannot tell you](#10-what-the-evaluation-cannot-tell-you)
11. [Evaluation controls](#11-evaluation-controls)
12. [What comes next](#12-what-comes-next)

---

## 1. The problem

When a service fails in Kubernetes, the evidence explaining why already exists —
it is just scattered. Metrics live in Prometheus, application logs in Loki,
object and lifecycle state in the Kubernetes API, deployment history in the
GitOps controller. Each store has its own query language, its own retention
window, and its own idea of what an "entity" is.

An engineer on call joins that up by hand, under time pressure, by holding the
service topology in their head and moving between consoles until the pieces line
up. It is not conceptually hard. It is a search problem across sources that were
never designed to be joined.

Language models suit that shape of problem: they read messy heterogeneous text
and produce a written explanation rather than a ranked list. Retrieval-augmented
generation makes the fit concrete — retrieve the evidence for the incident
window, put it in context, ask for a diagnosis.

**The difficulty is that a generated explanation reads exactly the same whether
or not it is true.** In an incident, a confident wrong answer is worse than no
answer: it sends someone to fix the wrong service while the outage continues.

The standard defence is *self-consistency* — sample the model several times and
keep what recurs. It needs nothing but the model. Its weakness is what it
measures: recurrence is **stability**, and a model that is confidently wrong is
stably wrong.

---

## 2. The idea

An operational system has something an open-domain text task does not: **a real,
machine-readable dependency graph**, produced as a by-product of running the
system rather than at extra cost. Services call services, pods run on nodes,
deployments come from commits.

The hypothesis was a chain of four claims:

```text
1. An operational system already has a real dependency graph, free.
        ↓
2. That graph should retrieve better evidence than embeddings alone.
        ↓
3. That graph should verify generated claims — provenance is checkable.
        ↓
4. A claim traceable to nearby evidence is more likely to be TRUE.
```

Claim 1 is infrastructure, not a hypothesis. **Claims 2, 3 and 4 are what the
project actually tested.**

---

## 3. How the system works

CloudGraph is four services on Kubernetes.

| Service | Responsibility |
|---|---|
| `api` | Graph construction, retrieval, GCP, GPCS, evaluation harness. The only service that talks to either datastore |
| `investigation-engine` | The five specialist diagnostic agents |
| `agent-orchestrator` | Consensus aggregation over agent findings |
| `ui` | Operator interface and reverse proxy |

### The two datastores, and why both

**Neo4j holds structure.** Eight node labels — `Service`, `Pod`, `Node`,
`Deployment`, `Incident`, `Commit`, `Log`, `Metric` — connected by typed
relationships: `GENERATES`, `BELONGS_TO`, `CALLS`, `RUNS_ON`, `MANAGES`,
`UPDATED_BY`. This is what makes *hop distance* a real path through real
topology.

**Qdrant holds meaning.** Evidence is embedded with `all-MiniLM-L6-v2` into
384-dimensional vectors indexed under cosine distance. This is what makes
*semantic similarity* computable.

GPCS combines both in a single score, so it needs both. Semantic match alone
cannot tell you whether evidence is causally near the incident; graph proximity
alone cannot tell you whether it is about the same thing.

### The pipeline

```text
ingest    build a temporal knowledge graph from live cluster telemetry
retrieve  select evidence relevant to the incident window
diagnose  five specialist agents, then a consensus stage
verify    score every claim in the generated explanation
serve     operator UI, CLI, evaluation harness
```

Stages 1–3 and 5 are engineering. **Stage 4 is the research contribution**, and
the rest is subordinate to it — they exist to produce a graph and a generated
explanation for stage 4 to be measured against.

### Retrieval

Three methods, and the choice between them is the independent variable in the
neuro-symbolic ablation:

- **keyword** — lexical matching, predominantly symbolic
- **vector** — dense nearest-neighbour search, predominantly neural
- **hybrid** — both, fused with graph structure and time

```text
score = 0.50·vector_similarity + 0.30·graph_proximity + 0.20·recency
```

where graph proximity is `1/(1 + hop_distance)` from the incident seed. The
weights are validated to sum to 1.0 at construction so a future change cannot
silently rescale the score.

### Diagnosis

Five specialists — `monitoring`, `logs`, `deployments`, `topology`, `security` —
each see the same evidence but are prompted to look for different things. Their
outputs are combined by fixed weights: logs 0.30, monitoring 0.20, deployments
0.20, topology 0.15, security 0.15.

> **Be precise about "multi-agent".** The consensus stage is a **static weighted
> aggregation**. Agents do not communicate, critique one another, or iterate.
> There is no debate round and no message passing. Structurally this is an
> ensemble of independent classifiers, not an interacting multi-agent system, and
> it is described that way throughout.

One measured detail worth knowing: the **security agent only calls the model when
it has already detected a threat**. In `investigation-engine/main.py` the LLM
call sits inside `if threat_detected:`; otherwise the agent falls back to a rules
path and still returns a finding. On a CPU-exhaustion scenario it never calls the
model. So the architecture is five specialists, but the runtime cost is often
four calls plus consensus.

---

## 4. The two original mechanisms

### Graph Confidence Propagation (GCP)

GCP spreads belief from observed symptoms to candidate causes across the incident
graph.

Evidence nodes receive an initial confidence by type — security threats 0.90,
error logs 0.85, metric anomalies 0.80, deployment rollouts 0.75, commit
regressions 0.70. Structural nodes start at zero.

Confidence along a path `P = (v₀ … v_k)` attenuates by the product of typed edge
weights and an exponential hop decay γ = 0.85:

```text
c(P) = c₀(v₀) × Π w(vᵢ₋₁, vᵢ) × γᵏ
```

Edge weights encode how strongly a relationship transmits blame: `GENERATES`
0.95, `UPDATED_BY` 0.90, `MANAGES` 0.85, `BELONGS_TO` 0.80, `CALLS` 0.75,
`RUNS_ON` 0.60.

Where a node receives confidence along several independent paths, contributions
combine under a Noisy-OR gate:

```text
C(u) = 1 − Π (1 − c(Pⱼ))
```

so several weak independent indicators accumulate into a stronger signal — the
behaviour an operator applies informally when three unrelated symptoms all point
at one service.

> **What these numbers are not.** The outputs are **not probabilities**. Every
> edge weight and initial confidence is hand-set from operational judgement, not
> fitted to data, and has never been checked against observed correctness rates.
> A score of 0.8 does not mean "correct 80% of the time". The word *calibrated*
> appears nowhere in this project as a description of the system.

**Important scope note.** GCP is **not part of the evaluation path.** The
benchmark harness runs seed → retrieve → generate → GPCS.
> `GraphConfidencePropagator` is used by the live investigation endpoint
> (`app/main.py`) and by `evaluation.py`. So the reported numbers test GPCS
> against self-consistency; GCP belongs to the product and is untested.

### Graph-Provenance Claim Scoring (GPCS)

GPCS is the core contribution. Where GCP asks *which entity is responsible*, GPCS
asks a different question: **is this particular sentence supported by anything in
the graph?**

**Step 1 — Claim extraction.** The generated explanation is decomposed into
atomic claims by a structured-output LLM call. Each is one verifiable assertion,
typed `causal`, `state`, `temporal`, `entity_relationship` or `general`.
Recommendations are excluded — they are prescriptive, and nothing in the graph
could confirm or refute them.

**Step 2 — Evidence retrieval.** For each claim, entities named in the claim text
seed a scoped search over the graph and the vector index.

**Step 3 — Trust scoring.**

```text
trust = 0.45·semantic + 0.35·proximity + 0.25·reliability − 0.15·(min_hop × 0.05)
proximity = 1 / (1 + min_hop_distance)
unsupported  ⟺  trust < 0.50
```

| Term | Meaning |
|---|---|
| **Semantic alignment** | Cosine similarity between the claim and the best-matching evidence chunk |
| **Graph proximity** | `1/(1+hops)` from the claim's subject entity to the supporting evidence |
| **Source reliability** | Fixed weight per evidence type: structural objects 0.90, metrics 0.85, logs 0.80, nodes 0.75 |
| **Path-length penalty** | **Subtracted.** For retrieval a longer path means less relevant; for *verification* it means the claim rests on a longer inferential chain, and each hop is another step where the connection could fail |

The path penalty is the one component with no direct precedent in the retrieval
literature, and it is where the "verification, not retrieval" idea is encoded.

**The evidence floor.** Nearest-neighbour search over a populated index never
returns empty — it always yields its top-*k* regardless of true relevance. An
unfiltered score therefore cannot distinguish "the closest available match" from
"no real match". Evidence scoring below cosine **0.30** is discarded before it
can contribute. That threshold came from the observed distribution: vague claims
topped out around 0.16–0.30, genuine matches scored 0.33–0.87.

**Absent provenance is not adjacency.** When evidence arrives from semantic search
with no path back into the graph, `min_hop` is `None` and the proximity term is
set to **0**, not treated as zero hops. Conflating them once gave full graph
credit to 29.5% of claims and floored every score near 0.485, leaving the 0.50
threshold to adjudicate one claim in 616.

**Every parameter is hand-set.** The four coefficients, the 0.50 threshold, the
0.30 floor, the ranker split, the edge weights and γ are all operational
judgement. None is fitted. The evaluation therefore measures one
*parameterisation*, not the mechanism at its best.

---

## 5. What "supported" and "unsupported" actually mean

This is the single easiest thing to misread, so it is worth stating plainly.

### GPCS asks: *can I find proof?*

| Verdict | Means |
|---|---|
| supported | Found evidence, close by in the graph, and it matches. Score ≥ 0.50 |
| unsupported | Could not find good enough evidence. Score < 0.50 |

It is a fact-checker with a filing cabinet. It is **not** judging whether the
sentence is true — only whether it can find a document backing it.

### Self-consistency asks: *did you say it again?*

| Verdict | Means |
|---|---|
| supported | The model repeated this in at least half the other samples |
| unsupported | The model said it once and did not repeat it |

Three diagnoses are generated at temperature 0.8; a claim recurs if a
semantically equivalent claim (cosine ≥ 0.8) appears in the others. It never
looks at evidence — only at the model repeating itself.

### The trap

**"Unsupported" does not mean "false."** From a live trace of scenario
`rcaeval-01`:

| Claim | GPCS | Reality |
|---|---|---|
| "CPU mean increased 42.6× from 0.4289 to 18.29" | **0.000 — unsupported** | Copied verbatim from the input. **True** |
| "noisy_neighbors flag associated with node-worker-01" | **0.720 — supported** | An *inference* |

So:

- **GPCS unsupported** = "I could not verify this", not "this is wrong"
- **Self-consistency supported** = "the model was consistent", not "the model was right"

A model that is confidently wrong is wrong in all three samples, and
self-consistency calls that **supported**.

---

## 6. How it was evaluated

### Corpus

**RCAEval RE2** — a published benchmark of chaos-injected failures in real,
running microservice systems. MIT licensed, archived at
`10.5281/zenodo.14590730`.

It was chosen over a hand-authored incident set for a decisive reason: an earlier
version of this project used a hand-written benchmark whose incident descriptions
embedded the answer in retrievable text, making every retrieval method appear to
succeed. That dataset was discarded rather than repaired.

**36 scenarios**, drawn deterministically, balanced two per (system × fault type):

- 3 systems — Online Boutique, Sock Shop, Train Ticket
- 6 fault types — cpu, mem, disk, delay, loss, socket
- 18 cells, 2 replicates each

The balance is deliberate. An unbalanced draw would confound fault type with
system, and any per-system effect would be uninterpretable.

Fault labels come from RCAEval's own metadata, so the ground truth is independent
of anything CloudGraph produces.

### Design

Each scenario runs under **three context conditions** crossed with **three
retrieval methods** — nine investigations per scenario:

| Condition | Evidence supplied |
|---|---|
| `none` | Nothing. The floor |
| `raw` | Everything seeded, unranked. **The long-context control** |
| `hybrid` | Ranked by the hybrid retriever |

`raw` is the control that makes the project honest. Without it you could report
"graph retrieval works!" — but the real question is *compared to just giving the
model everything?* Modern context windows swallow 60 items easily. If ranking to
5 does not beat dumping all 60, the ranker is complexity that is not paying for
itself.

### Scale

```text
runs                   18   (6 scenarios x 3 retrieval conditions)
LLM calls per run      18   (4 specialists + 1 consensus) x 3 generations
                            + 3 claim extractions
claims extracted      661   scored independently by BOTH verifiers
  none                218
  raw                 241
  hybrid              202
```

All generations use one model through one provider at temperature 0.8, with no
fallbacks: every sample reached the model.

### How results are reported

Six scenarios with one sample per cell is not enough for inferential statistics,
so results are reported as **counts and rates**, not intervals or significance
tests. Where a difference is described as consistent, it means it held in every
run; where it is described as a null, it means the direction did not favour the
condition under test.

Retrieval is non-deterministic at temperature 0.8, so a re-run lands near, not
on, these figures.

## 7. The seven research questions

| RQ | Question | Verdict |
|---|---|---|
| **RQ1** | Does GPCS behave differently from self-consistency, and does either flag track claim correctness? | **Partly against** |
| **RQ2** | Is the measured result real end-to-end, not an artefact of a simulated scorer? | **Answered — yes** |
| **RQ3** | Does graph-structured retrieval beat dumping all evidence into context? | **Null** |
| **RQ4** | Is any retrieval benefit symbolic-structural or neural-semantic? | **Against** |
| **RQ5** | Does the five-agent architecture beat a single model at matched compute? | Deferred |
| **RQ6** | Are the confidence scores calibrated, and would fitted weights beat hand-set ones? | Deferred |
| **RQ7** | Which claim types are each verifier's blind spot? | Deferred |

RQ2 is a prerequisite rather than a contribution: it asks whether the pipeline
being measured is the pipeline being described. It is stated as a research
question because that property does not hold automatically, and its failure is
not visible from the results alone.

One question is out of scope: the effect on mean time to resolution. Measuring
it needs human operators working real incidents, which this project cannot
arrange, and no proxy would be honest.

**Three of the four answered questions went against the design's predictions.**
The falsification criteria were fixed before measurement and were not revised
once the results were known.

---

## 8. Results in full

### RQ2 — is the measured result real?

**Yes, and smaller than the earlier simulated numbers implied.**

Every baseline invokes the real pipeline: real retrieval against live stores,
real agents making real model calls, real GPCS scoring. No stand-in heuristic
substitutes for any measured step.

### Does GPCS behave differently from self-consistency? **Yes.**

GPCS flags **80.8%** of claims unsupported (534 of 661) against self-consistency's
**52.3%** (346). It flags more in every one of the 18 runs, at no additional
inference cost — GPCS adds no model calls, while self-consistency needs two extra
full generations.

The verifiers agree on **61.9%** of claims (409 of 661) and disagree on 252. They
are measurably different instruments rather than two implementations of the same
judgement, which is the necessary condition for the comparison to be interesting
at all.

| Joint verdict | Claims |
|---|---:|
| Both accept | 95 |
| Both flag | 314 |
| GPCS flags only | 220 |
| Self-consistency flags only | 32 |

**The score distribution matters more than the rate.** GPCS trust takes six
distinct values across all 661 claims:

```text
0.000  0.700  0.708  0.710  0.713  0.720
```

and **80.8% of claims sit at exactly `0.000`** — an early return when no evidence
clears the 0.30 semantic floor. GPCS is a gate, not a graded confidence: it finds
either enough evidence or none. No claim exceeds `0.720` against a formula whose
positive terms sum to 1.05, so the 0.50 threshold sits far higher relative to the
real distribution than its nominal position suggests.

### Does either flag track correctness? **Not demonstrably.**

This is the central negative result. Only **22 of 661 claims (3.3%)** carry a
correctness label at all — 11 consistent, 11 contradicted. On those 22:

| Verifier | Flags incorrect | Flags correct | Gap |
|---|---|---|---|
| GPCS | 90.9% | 81.8% | **+9.1 pp** |
| Self-consistency | 81.8% | 81.8% | **0.0 pp** |

Self-consistency's gap is exactly zero: it flags correct and incorrect claims at
the same rate, so its verdict carries no information about correctness. GPCS's
gap points the right way, but on 22 claims that is a difference of **one claim**,
and its precision (52.6%) sits on a 50.0% base rate.

**The honest reading: GPCS is stricter, and cannot be shown to be better aimed.**
Flagging more claims is not evidence of flagging the right ones. Establishing
that would need a substantially larger labelled set.

### RQ3 — does graph retrieval beat a raw context dump? **Null.**

| Comparison | Mean Δ | 95% CI | *p* |
|---|---|---|---|
| Hybrid vs raw (agreement) | +0.0240 | [−0.0280, +0.0773] | 0.302 |

The interval spans zero. Ranked retrieval did not measurably outperform handing
the agents all the seeded evidence unranked.

Reported as a null rather than omitted or described as a near-miss. Be precise
about what a null means at this sample size: the interval rules out a **large**
effect — anything above roughly +7.7 percentage points — but does not exclude a
small one.

### RQ4 — symbolic or neural? **Entirely neural.**

Mean expected-tag recall across all 36 scenarios:

| Method | Mean recall |
|---|---|
| keyword | 0.4167 |
| vector | **0.6065** |
| hybrid | **0.6065** |

Hybrid beats keyword by +0.1898, CI [+0.1157, +0.2685], *p* = 0.0003 — the
largest effect anywhere in the study. Read alone, that supports the design.

It does not survive the next comparison. **Vector and hybrid retrieval are
byte-identical on all 36 scenarios** — same expected tags, same hit tags, same
recall to four decimal places. The entire improvement over keyword comes from the
embedding component. **The graph contributes nothing to retrieval on this
benchmark.**

Dense embeddings apparently already co-locate causally linked evidence, so
hop-distance ranking surfaces no candidate semantic similarity had not. The
symbolic component is redundant here, not harmful.

This does not make the graph inert. It remains load-bearing for claim *scoring*,
where GPCS's proximity and hop-decay terms have no embedding equivalent. But
scoring and retrieval are different mechanisms, and evidence for one is not
evidence for the other. **The defensible claim is narrower than the design
assumed: the graph's value in this system is verification, not retrieval.**

### Where the hypothesis stood at the end

```text
1. Operational systems have a real graph, free.       ✅ true by construction
2. The graph retrieves better than embeddings.        ❌ FAILED (RQ3 null, RQ4 against)
3. The graph can verify generated claims.             ✅ HELD  (RQ1 first half)
4. Traceable evidence means the claim is TRUE.        ❌ FAILED (RQ1 second half)
```

What survived is that GPCS is **distinct**, not that it is **better**.

---

## 9. Why the negative result is the useful one

A verifier that flags 70% of claims will be right about many of them, simply
because many claims in a generated explanation are unsupported. Reporting that
flag rate, or its agreement with a second verifier, produces numbers that look
like validation. Neither quantity is evidence that the verifier is discerning.

The generalisable point is methodological:

> **Where the class balance is skewed, aggregate detection metrics can be
> satisfied by an indiscriminate detector. A pipeline can measure traceability
> while believing it is measuring correctness.**

Only the differential flag rate between correct and incorrect claims can
distinguish a working verifier from a merely strict one, and on that measure both
methods return approximately zero.

This matters beyond incident analysis. Any evidence-grounded verification scheme
— including proposals to ground clinical or legal generation in structured
knowledge — can exhibit the same pattern. **A claim can be traceable to evidence
and still be wrong.**

### Why GPCS fails, mechanically

Its failure mode is not mis-scoring. It is that for most claims it finds **no
qualifying evidence at all** — an early return before any term is computed. On a
live trace, only four distinct trust scores occurred across 31 claims: `0.000`,
`0.703`, `0.713`, `0.720`.

And when it does find evidence, it rewards claims that *name graph entities* and
rejects claims that *quote measurements*. Entity-shaped is not the same as
correct.

---

## 10. What the evaluation cannot tell you

**Label coverage — the binding constraint.** Correctness labels derive from
RCAEval metadata, which can adjudicate *causal* claims naming a mechanism and
nothing else:

| Label | Claims |
|---|---|
| Contradicted | 11 |
| Consistent | 11 |
| Unverifiable — not a causal claim | 506 |
| Unverifiable — no mechanism identifiable | 133 |
| **Evaluable** | **22 (3.3%)** |

Descriptive claims — that a pod restarted, that latency rose — are true or false
about the telemetry rather than about the cause, and metadata cannot settle them.

So the correct statement is **no evidence of discrimination at this coverage**,
not proof of its absence.

**Other bounds:**

- **One model, one provider, one temperature.** Nothing separates properties of
  the verifiers from properties of this generator.
- **Resource and network faults only.** RE2's six fault types contain no
  configuration errors, security events, DNS faults or certificate expiry.
  Results generalise to resource and network faults in microservice systems, not
  Kubernetes incidents in general.
- **The affected service is given, not inferred.** The system is asked *why* a
  known service failed, never *which* service failed. **No result here
  demonstrates root-cause localisation.**
- **Sample size.** 36 scenarios produce wide intervals.
- **Recall, not F1.** The retrieval measure counts hit and missed expected tags
  but not false positives.
- **Concordance is not accuracy.** The most-reported quantity measures whether
  two verifiers reached the same verdict. Both can be wrong about the same claim
  and it still counts as agreement.

---

## 11. Evaluation controls

The evaluation enforces the following, and each is pinned by a regression test in
`services/api/tests/test_evaluation_integrity.py`:

| Control | What it guarantees |
|---|---|
| **Ground truth is held out** | The faulted service and fault type never appear in observations or prompts. Tests reject both the claim text and the bare fault phrase |
| **Observations span all services** | Metric deltas are emitted for every service, not filtered to the faulted one — showing only the anomalous service would be leakage by selection |
| **Retrieval is scenario-scoped** | A `scenario_id` filter on the Neo4j query, the Qdrant search and the file-fallback path confines each run to its own seeded evidence |
| **Scenarios do not overlap** | Benchmark nodes are torn down between runs, and every log prints the store census before and after seeding |
| **Call counts are measured** | LLM requests are counted from the bodies the services actually sent, captured from pod output rather than inferred |
| **Fallbacks are disclosed** | A generation that did not reach the model is reported, not silently counted as a sample |

Two limits are worth stating plainly. `assert_semantic_store_isolated()` inspects
a collection the evaluation does not write to, so isolation rests on the
query-time filter rather than on that assertion. And `claim_text` in
`results/claims.csv` is truncated to 52 characters — full text is in the logs.

---

## 12. What comes next

The three deferred questions have a natural order, because one unblocks the
others.

**RQ7 first — widen the labelled set.** Every correctness statement rests on 22
claims because automatic labels reach only causal ones. Human annotation of a
stratified sample would raise coverage, give usable per-claim-type intervals, and
complete the unanswered half of RQ1. **This is the highest-value remaining work,
and everything else is worth less until it is done.**

**RQ5 next — the matched-compute control.** Five specialist calls plus a consensus
call cost the same as six samples from one model. Whether the architecture earns
that cost is untested here: the control has only ever run against the pre-fix
pipeline, so its numbers are invalid and are not reported. Re-running it needs no
new code and is the cheapest remaining closure.

**RQ6 last — calibration.** Every weight and threshold is hand-set. No reliability
diagram and no Brier score exist. Fitting the weights on a labelled set and
comparing against the hand-set defaults would establish whether the null and
negative results are properties of the mechanism or of this particular
parameterisation.

Beyond the research register, two extensions would broaden what can be claimed.
Running against RCAEval's **RE3** suite would introduce fault types the present
corpus lacks. Removing the assumption that the affected service is given would
turn the task from fault-type diagnosis into **root-cause localisation** — the
harder and more useful problem.

---

## In one paragraph

CloudGraph builds a temporal knowledge graph from Kubernetes telemetry, generates
a root-cause explanation with an ensemble of specialist agents, and then verifies
that explanation claim by claim against the graph. Measured against a
self-consistency baseline over six chaos-injected failures and 661 extracted
claims, the verifier is consistently stricter — 80.8% against 52.3%, in all 18
runs, at no additional inference cost — but on the 22 claims whose correctness can
be adjudicated it cannot be shown to be better aimed. **Graph provenance produces
a verifier that is stricter, not sharper.** The more general finding is the
coverage itself: only **3.3%** of the claims a model makes about an incident can
be adjudicated by standard benchmark metadata at all, so a pipeline can measure
traceability while believing it is measuring correctness.
