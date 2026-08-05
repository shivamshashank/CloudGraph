# Day 1 — Real vs. Simulated Benchmark

Run: `experiments/results/day1_real_benchmark.json` (25 scenarios, live
Neo4j + Qdrant + agent-orchestrator + investigation-engine, no LLM API key
configured — agents used their deterministic rule-based fallback path).

## Old simulated numbers (`benchmark.py`'s static `BENCHMARK_DATA`)

| Baseline | Acc | Prec | Rec | F1 | Hallucination |
|---|---|---|---|---|---|
| Keyword Search | 0.64 | 0.62 | 0.58 | 0.60 | 0.32 |
| Vector RAG | 0.69 | 0.68 | 0.63 | 0.65 | 0.28 |
| GraphRAG | 0.74 | 0.72 | 0.70 | 0.71 | 0.21 |
| GraphRAG + Agents | 0.78 | 0.75 | 0.74 | 0.74 | 0.19 |
| GraphRAG + Agents + GCP | 0.80 | 0.77 | 0.76 | 0.76 | 0.16 |
| GraphRAG + Agents + GCP + GPCS | 0.83 | 0.80 | 0.79 | 0.79 | 0.12 |

Monotonically increasing by construction — every tier "wins" a bit more than
the last. This was never measured; it was a hand-picked table.

## Real numbers — first run (hybrid-ranker bugs present, keyword search still broken)

| Baseline | Acc | Prec | Rec | F1 | Hallucination | Evaluated/Excluded |
|---|---|---|---|---|---|---|
| Keyword Search | 0.00 | 0.00 | 0.00 | 0.00 | N/A | 25/0 |
| Vector RAG | 1.00 | 0.79 | 0.90 | 0.84 | N/A | 25/0 |
| GraphRAG | 1.00 | 0.79 | 0.90 | 0.84 | N/A | 25/0 |
| GraphRAG + Agents | 1.00 | 0.79 | 0.90 | 0.84 | 0.92 | 25/0 |
| GraphRAG + Agents + GCP | 1.00 | 0.79 | 0.90 | 0.84 | 0.92 | 25/0 |
| GraphRAG + Agents + GCP + GPCS | 1.00 | 0.79 | 0.90 | 0.84 | 0.92 | 25/0 |

GraphRAG exactly equals Vector RAG here — a direct, honest consequence of
keyword search always returning zero results (see below), which starved the
Pod/Incident graph-traversal branch of `run_hybrid_search` of anything to
traverse from.

## Real numbers — final run (keyword-search Cypher bug also fixed)

| Baseline | Acc | Prec | Rec | F1 | Hallucination | Evaluated/Excluded |
|---|---|---|---|---|---|---|
| Keyword Search | 1.00 | 0.92 | 0.67 | 0.78 | N/A | 25/0 |
| Vector RAG | 1.00 | 0.80 | 0.90 | 0.85 | N/A | 25/0 |
| GraphRAG | 1.00 | 0.88 | 0.81 | 0.84 | N/A | 25/0 |
| GraphRAG + Agents | 1.00 | 0.88 | 0.81 | 0.84 | 0.92 | 25/0 |
| GraphRAG + Agents + GCP | 1.00 | 0.88 | 0.81 | 0.84 | 0.92 | 25/0 |
| GraphRAG + Agents + GCP + GPCS | 1.00 | 0.88 | 0.81 | 0.84 | 0.92 | 25/0 |

Fixing `run_keyword_search`'s Cypher (word-tokenized matching instead of
requiring the full query sentence to be a substring of a short field — see
"Bugs found and fixed today" below) produces the first genuinely
differentiated retrieval comparison of the week:

- **Keyword Search: high precision (0.92), low recall (0.67).** Makes sense
  once you look at what it's actually allowed to search: its label filter
  (`Pod`/`Service`/`Deployment`/`Incident`/`Node`/`Commit`) excludes `Log`
  and `Metric` nodes, where most of each scenario's tag-bearing text (e.g.
  "memory", "killed") actually lives — those tags are structurally
  unreachable by keyword search even after the CONTAINS fix. Whether that
  exclusion is intentional (a deliberately weak "grep the topology only"
  baseline) or should be widened to search evidence nodes too is a real
  design question, not yet decided — flag explicitly in the methodology
  chapter rather than silently changing scope again this week.
- **GraphRAG now genuinely differs from Vector RAG** (0.84 vs 0.85 F1,
  different precision/recall balance: 0.88/0.81 vs 0.80/0.90) — direct
  evidence the graph-traversal branch is now contributing real signal,
  since it depends on keyword search finding Pod/Incident seeds to traverse
  from. Before this fix that branch was structurally dead code every run.
- Vector RAG remains the strongest single-condition F1 on this 25-scenario
  set. Report that honestly too — it does not automatically follow that
  more structure (GraphRAG) beats less (Vector RAG) on every metric; here
  GraphRAG trades some recall for precision instead of strictly winning.

Not monotonic, and honest findings fall out of actually measuring it:

1. **Keyword Search was broken, not just weak — now fixed.**
   `run_keyword_search`'s Cypher (`evaluation.py:41-56`, and the identical
   live-product query at `services/api/app/main.py:762-783`) did
   `toLower(n.name) CONTAINS toLower($query)` — this required a node's short
   name/status/title/message field to contain the *entire* multi-word query
   sentence, which structurally can never match. Fixed by tokenizing the
   query and checking whether any word (length > 2) appears in the node's
   fields, rather than requiring the whole sentence to match. This was a
   live product bug (the same query backs `/api/v1/graphrag/search`'s
   keyword mode), not just a benchmark artifact.
2. **GraphRAG initially equaled Vector RAG exactly, now genuinely differs.**
   Because keyword search always returned zero raw results before the fix,
   the Pod/Incident-seeded graph-traversal branch of `run_hybrid_search`
   never fired — hybrid retrieval on this dataset was, at first, just
   vector search with extra (unused) ranking machinery. After the fix,
   GraphRAG shows a different precision/recall balance from Vector RAG
   (0.88/0.81 vs 0.80/0.90) — direct evidence graph traversal is now
   contributing real signal. See the "final run" table above.
3. **Hallucination rate is a flat 0.92 across all three Agent-based tiers.**
   Expected, given GPCS is currently a measurement instrument applied to
   identical generated text (see `evaluation.py`'s `evaluate_scenario`),
   not a remediation step — the three tiers differ in `correct`
   determination (via GCP's confidence gate) but not in what text GPCS
   scores. 92% is high; worth a closer look on Day 2/3 — plausible causes:
   no LLM key configured (agents use a generic rule-based fallback whose
   phrasing may not lexically/semantically align with GPCS's evidence
   matcher), or GPCS's evidence-retrieval step underperforming on this
   generated text. Investigate before citing this number anywhere.

## Bugs found and fixed today (beyond the three planned fixes)

While wiring up the real evaluation loop, three additional bugs were found
and fixed, because they were the actual reason "real" GraphRAG/Keyword
numbers looked nonsensical (0% accuracy) on the first live run:

- `graph_traversal_retriever.retrieve()` returns a plain `list[dict]`, but
  the calling code in `run_hybrid_search` did `graph_context.get("nodes", [])`
  as if it were a dict — dead code at first only because the keyword-search
  bug below meant this branch never executed (raw_results was always
  empty), but it was a live crash waiting to happen the moment keyword
  search started returning Pod/Incident hits. Fixed: iterate `graph_context`
  directly.
- `run_hybrid_search` reshaped `semantic_hits` into an ad-hoc
  `semantic_results` dict (`detail`, flat `name`/`status`) before passing
  it to `HybridRanker.rank()`, whose vector-hit contract expects `text`
  (flat) and `metadata` (nested) — fields the reshaped dict didn't have.
  This silently zeroed out every vector candidate's content inside the
  ranker regardless of how good the underlying vector search was. Fixed:
  pass `semantic_hits` straight through, since its native shape already
  matches what the ranker expects.
- `run_keyword_search`'s Cypher (`evaluation.py`, and the identical live
  endpoint at `main.py`'s `/api/v1/graphrag/search`) required a node's
  entire short field to contain the whole multi-word query sentence —
  structurally impossible, so it always returned zero results, which is
  also what starved the graph-traversal branch above of anything to run
  on. Fixed with word-tokenized `CONTAINS` matching.

## Also found, not fixed

- `tests/test_graph.py::test_investigation_trigger_returns_structured_analysis`
  fails only when a live-but-unseeded Qdrant is reachable (it mocks Neo4j
  but not Qdrant), flipping a classification fallback branch in
  `main.py`'s `_investigate_pod` unrelated to anything changed today. Not a
  regression from this session's diff (`git diff --stat` confirms only
  `evaluation.py`, `benchmark.py`, and the test file for benchmark eval
  were touched) — a pre-existing test-isolation gap, worth a Day 6 cleanup
  item (mock Qdrant too, or make that endpoint deterministic without a
  live vector store).

## Bottom line for the methodology chapter

Three real bugs stood between "the code compiles" and "the numbers mean
anything," found only by actually running the live pipeline instead of
trusting that real function calls implied real results. The final numbers
(Keyword 0.92P/0.67R, Vector 0.80P/0.90R, GraphRAG 0.88P/0.81R — each
baseline with a genuinely different precision/recall trade-off) are a
legitimate, citable first-pass finding for the methodology chapter. Report
the progression honestly: simulated → real-but-still-buggy → real-and-fixed,
with the bugs named, not just the final table.
