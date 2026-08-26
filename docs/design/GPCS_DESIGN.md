# Graph-Provenance Claim Scoring (GPCS): Design Doc

**Purpose:** This is the design for CloudGraph's **RQ1/H3** contribution: the
mechanism that makes "we reduce hallucinations" a measured, named, citable
claim instead of an assertion.

> **Outcome (v1):** RQ1 is answered, and only half in this design's favour.
> GPCS does behave distinctly from self-consistency: it flags 80.8% of claims
> unsupported against 52.3%. But on the 3.3% of claims carrying
> correctness labels, **neither verifier separates correct claims from
> incorrect ones** (both gaps −0.8 pp). GPCS is *stricter, not sharper*. The
> weights and thresholds below remain **hand-set and uncalibrated**: fitting
> them is RQ6, deferred to v2. See
> [`research/README.md`](../../research/README.md). It reuses primitives that already exist in
the codebase (`hybrid_ranker.py`'s distance-decay scoring, `graph_traversal.py`'s
hop-distance retrieval, `semantic_store.py`'s embedding search) repurposed
for claim verification instead of evidence retrieval.

**Name:** Graph-Provenance Claim Scoring (GPCS). Use this name consistently
in the dissertation, code, and docs: a named, specified mechanism is what
turns a feature into a citable artifact.

---

## 1. Problem framing

An LLM-generated RCA report is a block of natural-language text making
several factual assertions ("the deployment occurred 6 minutes before the
crash," "the secret was modified," "checkout depends on payment"). Some of
these are directly grounded in retrieved graph/vector evidence; others may be
plausible-sounding LLM fabrication not actually present in the evidence
CloudGraph retrieved. GPCS's job: for each claim, decide how well-grounded it
is in the actual evidence graph, and produce a report-level unsupported-claim
rate as the H3 metric.

This is deliberately narrower than general hallucination detection: it is
not asking "is this claim true," it is asking "is this claim supported by
the specific evidence CloudGraph retrieved for this incident." That framing
is both more tractable and more relevant to the dissertation's actual claim
(graph grounding reduces hallucination), so keep it framed this way
throughout — do not overclaim general factuality checking.

---

## 2. Pipeline

```text
Generated RCA text
      │
      ▼
Step A: Claim Extraction
      │  (LLM call: decompose RCA into atomic claims)
      ▼
List[Claim]
      │
      ▼
Step B: Evidence Alignment (per claim)
      │  (reuse graph_traversal_retriever + semantic_store.search)
      ▼
List[(Claim, [supporting_evidence_candidates])]
      │
      ▼
Step C: Graph-Provenance Trust Scoring (per claim)
      │  (new module — the core contribution)
      ▼
List[(Claim, trust_score, supporting_path)]
      │
      ▼
Step D: Report-Level Aggregation
      │
      ▼
unsupported_claim_rate, per-claim annotations for UI/evidence chain
```

### Step A — Claim extraction

- Input: the generated RCA text (title, cause, recommendation fields already
  produced by the agent/consensus layer).
- Method: one LLM call with a structured-output prompt asking for a JSON list
  of atomic factual claims, each claim being a single verifiable assertion
  (not an opinion or recommendation: recommendations are explicitly
  excluded from scoring, since they are prescriptive, not factual).
- Output schema per claim: `{claim_id, text, claim_type}` where
  `claim_type ∈ {temporal, causal, entity_relationship, state}`: typing
  claims lets you report hallucination rate broken down by claim type in
  the results chapter (e.g., "causal claims were more prone to
  unsupported assertions than entity-relationship claims"), which is
  exactly the kind of category-level finding that reads as real analysis.

### Step B — Evidence alignment

For each claim, retrieve the top-k candidate evidence items that could
support it:

- Embed the claim text using the existing `SentenceTransformerEmbedder`
  and run it through `semantic_store.search()`: reuses infrastructure
  as-is.
- Separately, extract any named entities in the claim (pod/service/
  deployment names) and run `graph_traversal_retriever.retrieve()` seeded
  from those entities if they exist as graph nodes.
- Merge both candidate sets, deduplicated by source ID: same pattern as
  `hybrid_ranker.py`'s candidate merging logic, reused directly.

### Step C — Graph-provenance trust scoring (the core contribution)

This is the part that needs to be genuinely designed, not just glued
together from existing pieces. Score formula:

```text
trust_score = w1 * semantic_alignment
            + w2 * graph_proximity
            + w3 * source_reliability
            - w4 * path_length_penalty
```

- **semantic_alignment**: cosine similarity between the claim embedding and
  the best-matching evidence document embedding (same primitive as
  `HybridRanker._unit_score`, reused).
- **graph_proximity**: `1 / (1 + hop_distance)` from the incident seed node
  to the evidence node supporting the claim: identical formula to
  `hybrid_ranker.py`'s existing `graph_proximity`, reused directly since it
  is already justified and documented.
- **source_reliability**: a fixed weight per evidence type reflecting how
  directly it constitutes ground truth (e.g., a Kubernetes event or metric
  reading is more reliable evidence than a free-text log line, which is
  more reliable than another LLM-generated artifact). This is new: define
  a small lookup table and justify each weight in the writeup; this is
  where genuine methodological judgment is visible to an examiner.
- **path_length_penalty**: unlike retrieval ranking (where a longer path is
  just "less relevant"), for claim *verification* a long inferential chain
  between claim and evidence is grounds for lower trust even if the final
  hop is a strong match: a claim resting on a 4-hop chain of weak
  intermediate relationships is less trustworthy than one directly backed
  by a 1-hop metric reading. This penalty is the one piece of GPCS that is
  not a repurposed existing formula: it is new, and it is the strongest
  candidate for the dissertation's "novel mechanism" framing.

Threshold: claims scoring below a cutoff are labeled unsupported.

**Status: not calibrated.** The shipped default is 0.50, hand-set, with the
semantic-evidence floor at 0.30 chosen by inspecting live query score
distributions. Neither was fitted on a held-out split. The requirement below
stands and is unmet — describe these as fixed defaults, never as calibrated,
in any write-up.

### Step D — Report-level aggregation

- `unsupported_claim_rate = unsupported_claims / total_claims` per RCA
  report — this is the primary H3 metric.
- Also report it broken down by `claim_type` (from Step A) and by
  incident category — this is what feeds the ablation study's
  per-category hallucination table.
- Surface per-claim trust scores and supporting paths in the API response
  and UI evidence chain (the UI already has the rendering surface for this
  — `evidence.js` / the evidence-chain components in the investigation UI (`services/ui/static/`) just
  need the new per-claim data instead of the current coarse evidence list).

---

## 3. The comparison baseline (do not skip this)

To make GPCS a contribution rather than a feature, implement one general-
purpose hallucination-detection baseline and report both side by side:

**Self-consistency baseline:** generate the same RCA twice (or three times)
at a higher temperature, extract claims from each generation the same way,
and flag as "unsupported" any claim that doesn't recur consistently across
generations. This requires no new infrastructure beyond an extra LLM call
and reuses the same claim extraction from Step A.

Report: does GPCS catch unsupported claims that self-consistency misses (and
vice versa)? Do they agree more on some claim types than others? This
comparison table is the single highest-value addition in the whole design —
it's what separates "we built a hallucination checker" from "we show
graph-grounded verification outperforms a generic method, and here's where
each one's blind spots are."

---

## 4. What to implement vs. what to design and discuss

Given time constraints, be deliberate about depth vs. breadth here too:

- [ ] **Must implement:** Steps A–D end to end, functioning on real
      generated RCA output, for the full incident dataset.
- [ ] **Must implement:** the self-consistency comparison baseline (Step 3)
      — this is not optional if GPCS is the centerpiece.
- [ ] **Must implement:** threshold calibration on a held-out split, not
      hand-tuned on the full set.
- [ ] **Can be simpler than production-grade:** the source-reliability
      lookup table does not need to be exhaustively researched: a
      justified, reasonable set of weights with the reasoning documented is
      sufficient for a dissertation; it does not need to be empirically
      optimized via grid search unless time allows.
- [ ] **Explicitly out of scope, and say so:** general factuality checking
      against external knowledge, multi-incident cross-referencing, and
      automatic threshold adaptation per incident category: name these as
      future work in the discussion chapter rather than attempting them.

---

## 5. Where this shows up in the dissertation

- **Methodology chapter:** the GPCS formula and its justification: mirror the
  style used for the hybrid ranker in
  `services/api/app/retrieval/hybrid_ranker.py`, which documents a weighted
  scoring formula component by component.
- **Evaluation chapter:** unsupported-claim rate per baseline (keyword /
  vector / GraphRAG / GraphRAG+agents), per claim type, per incident
  category, plus the GPCS-vs-self-consistency comparison table.
- **Discussion chapter:** where GPCS's graph-grounding advantage held vs.
  where it didn't (e.g., likely weaker on causal claims requiring
  multi-hop inference than on simple entity-relationship claims: state
  this as a hypothesis to test, not an assumption): this is exactly the
  kind of "one place where the result was weaker than expected" that the
  95+ checklist calls for.
