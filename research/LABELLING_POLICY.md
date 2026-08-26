# Labelling policy

**Pre-specified.** This document was written and dated before the results it
governs were produced, and was not revised afterwards.

| | |
|---|---|
| Written | 2026-08-20 |
| Applies to | claim-correctness labelling in `experiment-1-benchmark/` |
| Author | Shivam Shashank |

It exists because of a specific hazard. Deciding how to treat a class of claims
*after* seeing which decision improves the headline result would be p-hacking.
The decision is therefore made in advance, recorded here, and any departure from
it is logged in §7 with its date and reasoning.

If the numbers are disappointing under this policy, the policy does not change.
That is the point of writing it first.

---

## 1. Core rules

These are not up for revision.

- **Only causal claims are labelled.** A claim qualifies if `claim_type ==
  "causal"` or `CAUSAL_MARKERS` matches. State and temporal claims are
  `unverifiable` and excluded.
- **Mechanism words must be named affirmatively.** `NEGATION_NEAR` scans the
  whole claim; a negated mechanism is being ruled out, which is correct
  reasoning, not a wrong answer.
- **Bare effect words are excluded.** "latency" follows from every fault type;
  matching it would attribute delay faults to most CPU cases.
- **Foreign services indict only in a cause position** (`FOREIGN_AS_CAUSE`).
  Naming a neighbour as harmed is an effect statement and usually true.
- **Anything not clearly consistent or contradicted is `unverifiable`** and is
  excluded from metrics rather than assumed correct.
- **Ground truth comes from RCAEval case metadata**, never from CloudGraph
  output.

---

## 2. The decision this policy adds

### 2.1 Deployment- and configuration-regression claims are `contradicted`

**Rule.** A causal claim that affirmatively attributes the incident to a code
change, configuration change, deployment, rollout, or commit is labelled
**`contradicted`**.

**Justification.** RCAEval RE2 faults are **chaos-injected**. In every one of the
36 scenarios, no deployment, rollout, config change or commit occurred within the
incident window. A claim asserting that one caused the failure is false about the
ground truth in exactly the sense `MECHANISM_PATTERNS` already captures for a
competing fault family — naming `mem` when the injection was `cpu`. Deployment
regression is a competing causal mechanism; the only reason the labeller misses it is that
it enumerates the six *injected* families and stops there. That is an
implementation boundary, not a principled one.

**Patterns** (added to `MECHANISM_PATTERNS` under key `"deploy"`, subject to the
same affirmative-mention and negation scoping as every other family):

```python
"deploy": [
    r"(?:config(?:uration)?|code|deployment|rollout|release)\s+"
    r"(?:change|update|regression|push|rollout)",
    r"config[- ]induced",
    r"faulty\s+(?:config(?:uration)?|commit|deploy(?:ment)?|rollout|release)",
    r"(?:commit|sha)[- ]?[a-z0-9-]*\s+(?:introduced|caused|triggered)",
    r"regression\s+(?:from|introduced by)\s+(?:a\s+)?"
    r"(?:commit|deploy(?:ment)?|rollout|release|config)",
    r"bad\s+(?:deploy(?:ment)?|rollout|release|commit)",
],
```

**Consequences, stated in advance:**

- The base rate of contradicted claims **will rise** above the figure of
  106/155 = 68.4%. Both the new base rate and the v1 figure must be reported
  side by side.
- Precision for both verifiers will drift toward the new base rate. This is the
  known artefact already documented — precision measures class prevalence here,
  not discrimination — and it is **why the flag-rate gap, not precision, remains
  the primary discriminating statistic**.
- Evaluable coverage should rise, because claims that fell through to
  `unverifiable` now land in a class.

### 2.2 The `deploy` family is never `consistent`

`"deploy"` may produce `contradicted` only. It can never be the injected fault,
because RCAEval injects none. A claim naming a deployment cause cannot be right
in this corpus, so the `names_correct_mechanism` branch must never select it.

### 2.3 Precedence when a claim names both

A claim naming the correct injected mechanism **and** a deployment cause — e.g.
*"a config change caused CPU saturation"* — is **`contradicted`**.

This matches v1's existing treatment of mixed mechanisms: in the pilot,
*"failure is due to isolated CPU/memory pressure"* was labelled contradicted on a
`cpu` scenario because it also named `mem`. A root-cause explanation that hedges
across mechanisms has not identified the root cause. Applying a different rule to
`deploy` than to `mem` would be special pleading.

**Implementation note:** the competing-mechanism check must therefore be
evaluated **before** the correct-mechanism check for `deploy`, which reverses
v1's ordering. This must be implemented explicitly, not left to dict ordering.

---

## 3. What this policy explicitly does NOT change

Listed so that any later change is visibly a deviation:

- No change to `CAUSAL_MARKERS`, `NEGATION_NEAR`, `FOREIGN_AS_CAUSE`, or
  `_word_re`.
- No change to the six injected fault families or their patterns.
- No change to the 0.50 GPCS threshold, the 0.30 evidence floor, the `evidence[:5]`
  slice, the 0.8 self-consistency cosine threshold, or the 3-sample count.
- No change to the bootstrap procedure: 10,000 resamples, seed 42, **clustered on
  scenario**, alongside Wilcoxon signed-rank.
- No re-labelling of `experiment-1-benchmark/results/`. That archive stays under v1. If it
  is ever re-labelled under v2, both versions must be published together with the
  delta.

---

## 4. Analysis plan, fixed in advance

**Primary comparisons** — three, pre-specified, as in v1:

1. GPCS vs self-consistency unsupported-rate delta (paired, clustered on scenario)
2. hybrid vs raw claim-agreement-rate delta
3. hybrid vs keyword expected-tag recall delta

**Primary discriminating statistic for correctness:** flag-rate gap,
`FlagRate(contradicted) − FlagRate(consistent)`. Precision is reported but is
**not** treated as evidence of discrimination, for the base-rate reason above.

**New for the post-fix run** — RQ3, which v1 never measured:

4. Root-cause accuracy per condition, scored against RCAEval metadata,
   clustered on scenario, reported as counts and rates. A
   proportion over 36 scenarios, **not** over 108 scenario-condition pairs.

**Reported regardless of outcome:** all four, with intervals, plus evaluable
coverage per condition, plus the count of scenarios where any generation named a
deployment cause.

**No multiple-comparison correction**, consistent with v1; a reader applying
Bonferroni at α = 0.05/4 should be able to reach the same conclusions, and if
they cannot, that must be said.

---

## 5. Falsification criteria

Fixed now, so the re-run can fail.

| Claim | Fails if |
|---|---|
| GPCS is stricter than self-consistency | the delta's 95% CI includes 0 |
| GPCS tracks correctness | flag-rate gap CI includes 0, or is negative |
| Hybrid beats raw on diagnosis | root-cause accuracy CI for (hybrid − raw) includes 0 |
| Hybrid beats *no retrieval* | root-cause accuracy CI for (hybrid − none) includes 0 |

**The last row is the one that matters and the one most likely to fail.** In the
pilot, `none` and `hybrid` both scored 2/2. If retrieval only avoids damage that
raw retrieval causes, the honest finding is that ranked retrieval **did not beat
supplying no evidence at all**, and it must be reported that way.

---

## 6. Prerequisite: the seeding fix

This policy assumes the seeded `Commit` node has been corrected
(`seeding.py`, `COMMIT_MIN_AGE_DAYS`): dated 3–10 days before the incident by a
deterministic per-scenario offset, carrying a message that names neither the
faulted service nor its configuration, with Neo4j and Qdrant timestamps agreeing.

Under the old seeding the commit sat at `incident_time`, giving the hybrid
ranker's recency term its maximum value of **1.0** for the one item guaranteed to
be causally irrelevant; it is now ~**2e-22**.

**Rationale for fixing it rather than measuring it:** the old node was a uniform
artefact of CloudGraph's own harness, identical across all 36 scenarios. Measuring
how often a model blames it would characterise the harness, not GraphRAG. With
the node correctly dated and neutrally worded, a model that still blames it is
making an error the graph itself contradicts — which is a fair test of the
neuro-symbolic claim.

**A run under this policy but with the old seeding is not valid** and must not be
reported.

---

## 7. Deviation protocol

Any departure from this document must be recorded here, in a dated appendix,
stating what changed, why, and whether it was decided before or after the
affected numbers were seen. An undated or unrecorded deviation invalidates the
run.

### Deviations

#### D-1 — negation-pattern morphology fix (2026-08-20)

**Decided before the affected results existed**, so this correction cannot have
been selected to improve a number.

**What changed.** `NEGATION_NEAR` in `label_claim_correctness.py` failed to match
three forms, each of which produced a **false `contradicted`** on a claim that
reasoned correctly:

| Claim | Missed by | Was | Now |
|---|---|---|---|
| *"CPU saturation is **excluded** as the cause"* | `excludes?` — no participle | contradicted | unverifiable |
| *"…**ruling out** noisy-neighbor contention"* | `rules?/ruled out` — no gerund | contradicted | unverifiable |
| *"**non-CPU-bound** blocking bottleneck"* | `\bno\b`/`\bnot\b` — no hyphen prefix | contradicted | unverifiable |

All three were observed in `rcaeval-04` (`network_delay`). The class clusters in
delay and loss scenarios, where models write negative reasoning ("not CPU",
"excluded", "non-CPU-bound"), so unfixed it would have inflated apparent
contradictions in precisely the arms reasoning best.

**Scope.** The fix closes inflections of lexemes **already present** in the
pattern (`rul(e|es|ed|ing) out`, `exclud(e|es|ed|ing)`, `refut…`, `contradict…`)
and adds the hyphenated `non-` prefix. It deliberately adds **no new negation
concepts** — *preclude*, *discount*, *dismiss*, *eliminate* were considered and
rejected as a scope change rather than a bug fix.

**Direction of error.** Over-matching is the safe side: a spurious negation makes
`mentioned_affirmatively()` return `False` for every pattern, so the claim falls
to `unverifiable` rather than being mislabelled. Under-matching, which is what
happened, manufactures contradictions that are not there.

**Effect on measured coverage.** Evaluable coverage **falls**, it does not rise:
all three claims move from a definite label to `unverifiable`. This correction
therefore weakens the apparent evidence base rather than strengthening it, which
is the expected direction for an honest fix.

**Verification.** Eight previously-matching negation forms still match; four
affirmative mechanism assertions still do not. Checked against every scored claim
in the twelve `Single Scenario 1` logs — exactly three claims change label.

#### D-2 — `non-` scoped as a bound morpheme (2026-08-20)

**Decided before any v2 results exist.**

D-1 added `non-\w+` to `NEGATION_NEAR`, which scopes over the **whole claim**.
That interacted badly with the v2 deployment rule: *"Root cause is a
deployment-related **non-CPU-bound** blocking bottleneck"* denies CPU while
asserting a deployment cause, but whole-claim negation suppressed every family
at once — including `deploy` — so the claim fell to `unverifiable` and the v2
rule's headline case escaped it.

`non-` is a **bound** morpheme: it negates only the token it prefixes, unlike
free-standing *not*/*no*, which can scope broadly. It is therefore moved out of
`NEGATION_NEAR` into `NEGATED_PREFIX`, and the matched span is excised before
pattern matching rather than vetoing the claim. The mechanism it names
disappears; everything else in the claim is still read.

Net effect on that claim: `unverifiable` → **`contradicted`**, which is the
correct label — it attributes a chaos-injected network delay to a deployment.

**Verification.** A 10-case matrix covering both v2 targets, the v2 precedence
rule, both D-1 forms, and four v1 behaviours that must survive: 10/10.

#### D-3 — record of a withdrawn defect claim (2026-08-20)

An earlier analysis asserted that raw retrieval was **non-deterministic across
generations** (logged as "60 / 40 / 57 / 44 items") and flagged it as a threat to
the RQ3 control. **This was a misreading and is withdrawn.**

Retrieval runs once per condition. The later three counts are *claim-extraction*
outputs from the three generations, confirmed by `claims extracted from primary
generation: 40` matching the first of them. `run_raw_context_search()` is
deterministic: all `is_benchmark` nodes for the `scenario_id`, plus a Qdrant
search under `limit=50`.

Recorded because the false claim was written into a trace document before being
caught, and the correction should be as visible as the assertion was.

#### D-4 — the v2 deployment-regression rule is WITHDRAWN (2026-08-20)

**This withdraws the substantive change this policy was written to introduce
(section 2.1). Recorded in full because a pre-registration that can be quietly
abandoned when inconvenient buys nothing.**

**Why it was specified.** Section 2.1 argued that attributing a chaos-injected
fault to a deployment is a competing causal mechanism, exactly as naming `mem` on
a `cpu` fault already is, and should therefore be `contradicted` rather than
`unverifiable`. That was written against pilot data in which the model very
often did exactly this.

**Why it is withdrawn — the phenomenon was a seeding artefact.** Consensus titles
attributing cause to a deployment or config change, counted across every run:

| Pipeline state | Titles blaming a deployment |
|---|---|
| Pre seeding-fix (`Single Scenario/`) | **5 / 13 — 38%** |
| Post seeding-fix (`Single Scenario 1/`) | 1 / 23 — 4% |
| All fixes (`experiment-1/`) | **0 / 9 — 0%** |

The driver was `seeding.py`: a `Commit` node stamped at `incident_time` with the
message *"update {service} configuration"*, present identically in all 36
scenarios. Re-dating it 3--10 days earlier with a neutral message removed the
attractor, and with it the behaviour the rule targeted.

**It also misfired.** In the `rcaeval-03` pilot the rule produced two false
`contradicted` labels on claims that *decline* to blame a deployment:

```text
"A code regression cannot be confirmed due to null sha/commit_msg"
"Code regression as a cause is discounted due to low confidence (0.3)"
```

Neither asserts a deployment cause; both are the Deployment agent correctly
reporting it cannot correlate anything. Two causes: `NEGATION_NEAR` does not
cover *"cannot be confirmed"* or *"discounted"*, and the `deploy` patterns
matched the bare phrase *"code regression"* without requiring a causal
qualifier -- a requirement every other family imposes. Both are fixable, but the
rule had by then required three successive corrections (D-1, D-2, this), which
is evidence about the rule rather than about any one implementation.

**Failure modes are asymmetric.** Under v1 a deployment attribution is
`unverifiable` and excluded from every correctness metric -- it is not scored as
correct, it gets no vote. Under a misfiring v2, a *correct* claim is scored as
wrong. Silence is safer than a false accusation, and matches this labeller's
stated preference for "a narrow, defensible label over a broad, noisy one".

**It costs comparability.** `experiment-1-benchmark/results/` was labelled under v1. A rule
that shifts the base rate makes new runs non-comparable with the archived
36-scenario dataset, which is the evidence base carrying RQ1.

**What is retained.** D-1 and D-2 stay. They fix genuine defects in v1's own
negation handling -- `excluded`, `ruling out`, `non-X` -- and are correct
independently of anything v2 proposed.

**What replaces it.** Deployment attribution is **counted and reported as a
descriptive statistic**, not labelled. The table above is that statistic. This
keeps the phenomenon visible without a fragile rule, and the count itself is a
reportable result: the seeding fix took it from 38% to 0%.

**Effect on measured coverage.** Coverage falls. `rcaeval-03 NONE` goes from
`consistent=3 contradicted=2` (12.8%) to `consistent=3 contradicted=0` (7.7%).
As with D-1, this correction weakens the apparent evidence base rather than
strengthening it.

**Status of this policy.** With section 2.1 withdrawn, the labelling rules for
the re-run are **v1 plus the D-1/D-2 negation corrections**. Sections 1, 3, 4, 5
and 6 stand unchanged.
