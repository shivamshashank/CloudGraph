# CloudGraph verification flow

One scenario — `rcaeval-03`, CPU exhaustion on `ts-order-service`, condition
`hybrid` — drawn end to end. All values are from the checked-in trace
[`experiment-1-benchmark/traces/rcaeval-03-TRACE_HYBRID.md`](../experiment-1-benchmark/traces/rcaeval-03-TRACE_HYBRID.md)
and [`results/claims.csv`](../experiment-1-benchmark/results/claims.csv).

---

## 1. The whole pipeline, with every API call

18 LLM calls: 15 inside the cluster, 3 in the harness process.

```mermaid
sequenceDiagram
    autonumber
    participant H as Harness
    participant N as Neo4j
    participant Q as Qdrant
    participant O as Orchestrator
    participant E as Engine
    participant L as LLM API

    rect rgb(238, 244, 238)
    Note over H,Q: SEED — 5.05s, no LLM
    H->>N: entities + 26 telemetry symptom lines
    H->>Q: 384-dim vectors (cosine)
    H->>Q: isolation assert → PASSED
    end

    rect rgb(238, 242, 248)
    Note over H,Q: RETRIEVE — 0.06s, no LLM
    H->>Q: hybrid search
    Q-->>H: 5 items, top score 0.5689
    end

    rect rgb(252, 244, 236)
    Note over H,L: GENERATE — repeated 3x at temperature 0.8
    H->>O: POST /orchestrate
    O->>E: POST /analyze
    E->>L: monitoring specialist
    L-->>E: finding + confidence
    E->>L: logs specialist
    L-->>E: finding + confidence
    E->>L: deployments specialist
    L-->>E: finding + confidence
    E->>L: topology specialist
    L-->>E: finding + confidence
    Note over E: security agent uses RULES,<br/>no LLM call (no threat detected)
    E-->>O: 5 findings
    O->>L: consensus — fuse the five
    L-->>O: title, cause, severity
    O-->>H: one diagnosis
    end

    rect rgb(248, 240, 246)
    Note over H,L: EXTRACT — once per generation
    H->>L: split diagnosis into atomic claims
    L-->>H: 35 typed claims
    end

    rect rgb(240, 240, 244)
    Note over H,Q: VERIFY — 0.11s, NO LLM AT ALL
    H->>H: self-consistency — cosine across the 3 generations
    H->>Q: evidence per claim (floor 0.30)
    H->>N: hop distance per claim
    H->>H: GPCS — four terms per claim
    end
```

**Call tally**

| Where | Calls |
|---|---|
| 4 specialists × 3 generations | 12 |
| consensus × 3 generations | 3 |
| claim extraction × 3 generations | 3 |
| **Total** | **18** |

Note that **verification costs zero LLM calls**. Generation takes ~270 s;
scoring all 35 claims takes 0.11 s.

---

## 2. GPCS — "can I find proof?"

> **The worked example below is illustrative, not observed.** In Experiment 1 the
> `semantic` term never varies: evidence reaches GPCS through graph traversal,
> which assigns a fixed `0.75` within two hops (`0.6` beyond) rather than a
> measured cosine similarity. Only eight distinct trust scores occur across all 1,950
> claims — `0.000`, `0.700`, `0.703`, `0.705`, `0.708`, `0.710`, `0.713`,
> `0.720` — and `0.000` accounts for 1,546 of them. Read the formula as scoring **graph reachability**,
> not semantic provenance. See the root [README](../README.md#results).

For each claim, independently:

```mermaid
flowchart TD
    A["Claim: 'Pod ts-order-service is a<br/>noisy neighbor on node-worker-01'"] --> B[Extract named entities]
    B --> C["Search Qdrant (semantic)<br/>+ Neo4j (graph paths)"]
    C --> D{"Any evidence scoring<br/>above the 0.30 floor?"}

    D -->|"No"| E["Return 0.000 immediately<br/>no terms are ever computed"]
    E --> F["UNSUPPORTED"]

    D -->|"Yes — 8 items"| G["semantic = 0.7500<br/>min_hop = 1<br/>reliability = 0.8300"]
    G --> H["proximity = 1/(1+1) = 0.5000<br/>penalty = 0.15 x (1 x 0.05) = 0.0075"]
    H --> I["trust = 0.45(0.7500)<br/>+ 0.35(0.5000)<br/>+ 0.25(0.8300)<br/>- 0.0075"]
    I --> J["trust = 0.3375 + 0.1750<br/>+ 0.2075 - 0.0075<br/>= 0.7125"]
    J --> K{"trust >= 0.50 ?"}
    K -->|"Yes"| L["SUPPORTED"]
    K -->|"No"| F

    style F fill:#f8dde3,stroke:#9b2242
    style L fill:#dcefe6,stroke:#1f6f5c
    style E fill:#fdf0e4,stroke:#a8560c
```

**The floor exists** because nearest-neighbour search never returns empty — it
always yields its top-*k* regardless of relevance. Without a floor you cannot
tell "closest available match" from "no real match".

**`min_hop = None` is set to proximity 0, not treated as 0 hops.** Absent
provenance is not adjacency. Conflating them once gave full graph credit to
29.5% of claims and floored every score near 0.485.

**Result for this scenario: 25 of 35 unsupported (71.4%).** Only three distinct
trust scores occurred across all 35 claims — `0.000`, `0.708`, `0.710`.
A claim either matches evidence a hop away, or finds nothing at all.

---

## 3. Self-consistency — "did you say it again?"

```mermaid
flowchart TD
    A["Same incident, diagnosed<br/>3 times at temperature 0.8"] --> B1["Generation 1<br/>PRIMARY"]
    A --> B2["Generation 2"]
    A --> B3["Generation 3"]

    B1 --> C1["35 claims"]
    B2 --> C2["claims"]
    B3 --> C3["claims"]

    C1 --> D["Take one claim from<br/>the primary generation"]
    C2 --> E["Cosine similarity against<br/>every claim in gen 2 and gen 3"]
    C3 --> E
    D --> E

    E --> F{"Does an equivalent claim<br/>(cosine >= 0.8) appear?"}
    F -->|"in both others"| G["recurrence = 1.0"]
    F -->|"in one other"| H["recurrence = 0.5"]
    F -->|"in neither"| I["recurrence = 0.0"]

    G --> J{"recurrence >= 0.5 ?"}
    H --> J
    I --> J
    J -->|"Yes"| K["SUPPORTED"]
    J -->|"No"| L["UNSUPPORTED"]

    style K fill:#dcefe6,stroke:#1f6f5c
    style L fill:#f8dde3,stroke:#9b2242
```

With only two other generations, recurrence can only ever be `0.0`, `0.5` or
`1.0`.

**It never looks at evidence.** It only asks whether the model repeated itself.
So it measures **stability**, not truth — a confidently wrong model is wrong all
three times and gets marked *supported*.

**Result for this scenario: 20 of 35 unsupported (57.1%).**

---

## 4. The two verdicts side by side

```mermaid
flowchart LR
    A["35 claims<br/>from ONE extraction"] --> B["GPCS<br/>graph evidence"]
    A --> C["Self-consistency<br/>model repetition"]

    B --> D["25 unsupported<br/>71.4%"]
    C --> E["20 unsupported<br/>57.1%"]

    D --> F["Compare<br/>claim by claim"]
    E --> F

    F --> G["both supported: 7"]
    F --> H["both unsupported: 17"]
    F --> I["GPCS only flagged: 8"]
    F --> J["SC only flagged: 3"]

    G --> K["Agreement 24/35 = 68.6%"]
    H --> K

    style D fill:#f8dde3,stroke:#9b2242
    style E fill:#f8dde3,stroke:#9b2242
    style I fill:#fdf0e4,stroke:#a8560c
    style K fill:#eef1f5,stroke:#5a6270
```

Both verifiers score **the same claims**, from **the same extraction**, from
**the same generation**. Only the mechanism differs — which is what makes the
comparison fair.

The **8 claims GPCS alone rejects** are the strictness gap made visible.

> Agreement here is **concordance**, never accuracy. Both verifiers can be wrong
> about the same claim and it still counts on the diagonal.

---

## 5. Does either one track truth?

```mermaid
flowchart TD
    A["35 claims"] --> B{"Is the claim causal AND<br/>does it name a mechanism?"}
    B -->|"No — 33 claims"| C["unverifiable<br/>EXCLUDED"]
    B -->|"Yes — 2 claims"| D{"Compare to the injected fault<br/>cpu_exhaustion on ts-order-service"}

    D -->|"names the real mechanism"| E["consistent"]
    D -->|"names a different mechanism"| F["contradicted"]
    D -->|"blames a different service"| F

    E --> G["Evaluable subset:<br/>2 of 35 = 5.7%"]
    F --> G
    G --> H["Too small to conclude<br/>anything from one scenario"]

    style C fill:#eef1f5,stroke:#5a6270
    style H fill:#fdf0e4,stroke:#a8560c
```

**33 of 35 claims cannot be judged.** The benchmark metadata settles causal
claims that name a mechanism, and nothing else. *"CPU mean jumped from 5.289 to
37.52"* is descriptive — true about the telemetry, silent about the cause.

Across all 18 scenarios this comes to **93 of 1,950 claims — 4.8%**.

### And on that 4.8%

That subset splits **36 correct, 57 incorrect**.

| Verifier | Flags **incorrect** | Flags **correct** | Gap | Precision |
|---|---|---|---|---|
| GPCS | 91.2% (52/57) | 86.1% (31/36) | **+5.1 pp** | 0.627 |
| Self-consistency | 63.2% (36/57) | 63.9% (23/36) | **−0.7 pp** | 0.610 |

Self-consistency's gap is **negative** — it flags correct claims marginally more
often than incorrect ones. GPCS leans the right way by 5.1 pp, roughly three
claims out of 93.

A verifier that flagged *everything* would score **0.613** precision on this
set. GPCS's 0.627 and self-consistency's 0.610 are both at that floor: what
looks like precision here is class balance, not discrimination.

---

## The one-line summary

```mermaid
flowchart LR
    A["GPCS flags MORE<br/>79.3% vs 53.0%"] --> B["STRICTER"]
    C["Gap between correct<br/>and incorrect claims:<br/>+5.1 pp on 93 claims"] --> D["NOT SHARPER"]
    B --> E["Being rejected by GPCS<br/>carries no measurable information<br/>about whether a claim is true"]
    D --> E

    style B fill:#eef1f5,stroke:#5a6270
    style D fill:#f8dde3,stroke:#9b2242
    style E fill:#fdf0e4,stroke:#a8560c
```
