# CloudGraph verification flow

One scenario — `rcaeval-01`, CPU exhaustion on `checkoutservice`, condition
`hybrid` — drawn end to end. All values are from the live trace in
`/tmp/cloudgraph-trace-v2.log`.

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
    H->>N: 31 nodes (26 Log, 1 Metric, 5 entities)
    H->>Q: 28 vectors (384-dim, cosine)
    H->>Q: isolation assert → PASSED
    end

    rect rgb(238, 242, 248)
    Note over H,Q: RETRIEVE — 0.06s, no LLM
    H->>Q: hybrid search
    Q-->>H: 5 items, top score 0.6499
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
    L-->>H: 31 typed claims
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
scoring all 31 claims takes 0.11 s.

---

## 2. GPCS — "can I find proof?"

For each claim, independently:

```mermaid
flowchart TD
    A["Claim: 'Pod checkoutservice is a<br/>noisy neighbor on node-worker-01'"] --> B[Extract named entities]
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

**Result for this scenario: 29 of 38 unsupported (76.3%).** Only six distinct
trust scores occurred across all 31 claims — `0.000`, `0.703`, `0.713`, `0.720`.
A claim either matches evidence a hop away, or finds nothing at all.

---

## 3. Self-consistency — "did you say it again?"

```mermaid
flowchart TD
    A["Same incident, diagnosed<br/>3 times at temperature 0.8"] --> B1["Generation 1<br/>PRIMARY"]
    A --> B2["Generation 2"]
    A --> B3["Generation 3"]

    B1 --> C1["31 claims"]
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

**Result for this scenario: 15 of 31 unsupported (48.4%).**

---

## 4. The two verdicts side by side

```mermaid
flowchart LR
    A["31 claims<br/>from ONE extraction"] --> B["GPCS<br/>graph evidence"]
    A --> C["Self-consistency<br/>model repetition"]

    B --> D["29 unsupported<br/>76.3%"]
    C --> E["15 unsupported<br/>48.4%"]

    D --> F["Compare<br/>claim by claim"]
    E --> F

    F --> G["both supported: 6"]
    F --> H["both unsupported: 13"]
    F --> I["GPCS only flagged: 10"]
    F --> J["SC only flagged: 2"]

    G --> K["Agreement 19/31 = 61.3%"]
    H --> K

    style D fill:#f8dde3,stroke:#9b2242
    style E fill:#f8dde3,stroke:#9b2242
    style I fill:#fdf0e4,stroke:#a8560c
    style K fill:#eef1f5,stroke:#5a6270
```

Both verifiers score **the same claims**, from **the same extraction**, from
**the same generation**. Only the mechanism differs — which is what makes the
comparison fair.

The **10 claims GPCS alone rejects** are the strictness gap made visible.

> Agreement here is **concordance**, never accuracy. Both verifiers can be wrong
> about the same claim and it still counts on the diagonal.

---

## 5. Does either one track truth?

```mermaid
flowchart TD
    A["31 claims"] --> B{"Is the claim causal AND<br/>does it name a mechanism?"}
    B -->|"No — 30 claims"| C["unverifiable<br/>EXCLUDED"]
    B -->|"Yes — 1 claim"| D{"Compare to the injected fault<br/>cpu_exhaustion on checkoutservice"}

    D -->|"names the real mechanism"| E["consistent"]
    D -->|"names a different mechanism"| F["contradicted"]
    D -->|"blames a different service"| F

    E --> G["Evaluable subset:<br/>1 of 31 = 3.2%"]
    F --> G
    G --> H["Too small to conclude<br/>anything from one scenario"]

    style C fill:#eef1f5,stroke:#5a6270
    style H fill:#fdf0e4,stroke:#a8560c
```

**30 of 31 claims cannot be judged.** The benchmark metadata settles causal
claims that name a mechanism, and nothing else. *"CPU rose from 0.4289 to
18.29"* is descriptive — true about the telemetry, silent about the cause.

Across all 6 scenarios this comes to **22 of 661 claims — 3.3%**.

### And on that 3.3%

| Verifier | Flags **incorrect** | Flags **correct** | Gap |
|---|---|---|---|
| GPCS | 60.4% | 61.2% | **−0.8 pp** |
| Self-consistency | 72.6% | 73.5% | **−0.8 pp** |

Both flag true and false claims at **the same rate**. Being rejected by either
verifier tells you essentially nothing about whether the claim is correct.

Both also post a precision of exactly **0.681** on a set that is **68.4%
incorrect** — which is precisely the score a verifier that flagged *everything*
would achieve. The precision is class balance, not discrimination.

---

## The one-line summary

```mermaid
flowchart LR
    A["GPCS flags MORE<br/>80.8% vs 52.3%"] --> B["STRICTER"]
    C["Gap between correct<br/>and incorrect claims:<br/>-0.8 pp"] --> D["NOT SHARPER"]
    B --> E["Being rejected by GPCS<br/>carries no information<br/>about whether a claim is true"]
    D --> E

    style B fill:#eef1f5,stroke:#5a6270
    style D fill:#f8dde3,stroke:#9b2242
    style E fill:#fdf0e4,stroke:#a8560c
```
