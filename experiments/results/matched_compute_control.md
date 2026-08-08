# Matched-compute control

**Question.** Does CloudGraph's 5-specialist-agent architecture earn its
complexity, or does a single LLM sampled the same number of times perform
just as well (or better) at a roughly matched compute budget? This is the
cheap slice of `research/NOVEL_CONTRIBUTIONS.md` Contribution 5 in scope
for this pass — the "single LLM with full evidence" vs. "independent
specialists + static vote (current system)" comparison, not the full
ablation (which also includes a cross-agent-critique condition, out of
scope here).

**Method.** For each of the 25 scenarios, the same hybrid-retrieval
evidence was fetched once and given to both arms, so only the generation
architecture varies:

- **Real 5-agent arm** — `evaluate_scenario(scenario, "Agents")`, reusing
  Day 1's already-tested harness unmodified: 5 specialist LLM calls + 1
  consensus call (6 total), scored by GPCS.
- **Single-LLM arm** (new: `generate_and_score_single_llm` in
  `app/research/self_consistency.py`) — one direct LLM call given the same
  evidence, no specialist chain, sampled 5 times and self-consistency-
  checked, with the *primary* sample's claims scored by the same GPCS
  instance the Agents arm uses — not a different scoring mechanism, so
  "unsupported rate" means the same thing for both arms.

Call counts recorded per scenario, not assumed: **150 total LLM calls for
the Agents arm (6×25), 125 for the single-LLM arm (5×25)** — close but not
identical; report the gap honestly rather than claim perfect parity.

## Result

25/25 scenarios completed, 0 excluded — raw data in
`experiments/results/matched_compute_raw.csv`.

| arm | mean unsupported rate | median |
|---|---|---|
| Real 5-agent consensus | **44.2%** | 44.4% |
| Single-LLM (5-sample self-consistency) | **31.5%** | 31.2% |

The single-LLM baseline had a **lower** hallucination rate than the real
5-agent system in **19 of 25 scenarios** (agents won in 6, no ties). Paired
per-scenario delta (agents − single-LLM): mean **+0.127**, 95% bootstrap CI
**[+0.053, +0.201]** (excludes zero), Wilcoxon p=**0.0018** — statistically
significant, not sampling noise. See
`experiments/results/significance_tests.md`.

## Conclusion — a real, honest negative result

**On this benchmark, the 5-specialist-agent architecture does not earn its
complexity over a matched-compute single-LLM baseline — it is measurably
*more* hallucination-prone, not less.** Per guardrail #5
(`research/7_DAY_SPRINT_CHECKLIST.md`), this is reported as measured, not
adjusted to flatter the multi-agent system. This is consistent with
`NOVEL_CONTRIBUTIONS.md` Contribution 5's own framing: *"if independent
ensembling or matched-compute self-consistency perform equally well, the
'agentic interaction' framing is not earning its complexity and the honest
finding is that CloudGraph's gains (if any) come from evidence quality
(GraphRAG) and ensembling, not from agency per se."* Here the single-LLM
baseline doesn't just tie — it outperforms — which is a stronger version
of that same finding.

A plausible mechanism, not yet confirmed: the 5-agent system's specialists
each report independently and get combined by a static-weight consensus
vote (`ConsensusEngine.WEIGHTS`), with no cross-agent critique or
correction step — a single low-confidence or wrong specialist finding can
still be woven into the final narrative rather than caught and revised.
The single-LLM baseline has no such aggregation step to introduce
compounding errors; it reasons over the same evidence once, directly.
Testing this mechanism specifically (an interaction/cross-critique round)
is the next slice of Contribution 5, not built in this pass.

## Limitations

- **n=25 scenarios** — wide confidence intervals; the direction is clear
  and significant here, but treat the exact magnitude (44.2% vs. 31.5%) as
  approximate.
- **Call counts are close, not identical** (150 vs. 125) — a small residual
  compute-budget difference favors the single-LLM arm slightly; this
  doesn't change the direction of a 12.7-point gap, but is worth stating
  plainly rather than claiming perfect parity.
- **Claim-count asymmetry not controlled for.** The single-LLM arm
  extracted more claims on average (~16.4/scenario) than a typical Agents-
  arm generation — not directly comparable in this data since the Agents
  arm's own claim count wasn't separately saved (only the ground-truth-
  claims-scaled unsupported rate `evaluate_scenario` already computes). A
  method that asserts fewer, more conservative claims will tend to have a
  lower *rate* of unsupported ones almost by construction; this is worth
  checking directly in a follow-up rather than assumed away.
- This control isolates architecture vs. compute under the same retrieved
  evidence; it does not test the cross-agent-critique condition
  (Contribution 5's condition (c)) that a full ablation would need.
