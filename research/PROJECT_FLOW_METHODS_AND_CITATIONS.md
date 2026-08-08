# CloudGraph — full pipeline, methods, citations, and contributions

Green = your contribution. Blue = borrowed/cited technique. Amber dashed =
not done yet. See `internal/planning/PROJECT_CONTRIBUTION_AND_ROADMAP.md` for the
full written explanation this diagram summarizes.

```mermaid
flowchart TD
    T["Cluster telemetry<br/>logs, metrics, traces, commits"] --> KG[("Neo4j knowledge graph")]
    T --> VS[("Qdrant vector store")]

    subgraph LADDER["Six-method benchmark ladder — your ablation design"]
        direction TB
        M1["1. Keyword search"]
        M2["2. Vector RAG"]
        M3["3. GraphRAG"]
        M4["4. + Agents"]
        M5["5. + GCP"]
        M6["6. + GPCS"]
        M1 --> M2 --> M3 --> M4 --> M5 --> M6
    end

    KG --> M1
    KG --> M3
    VS --> M2
    VS --> M3

    C1["Lewis et al. 2020<br/>Retrieval-Augmented Generation"] -.cites.-> M2
    C2["Edge et al. 2024<br/>GraphRAG"] -.cites.-> M3
    C3["Guo et al. 2024<br/>Multi-agent LLM survey"] -.cites.-> M4
    C4["Classical Noisy-OR /<br/>belief propagation"] -.grounds.-> M5

    M6 --> RCA["Generated RCA text<br/>title, summary, cause"]

    subgraph COMPARE["Hallucination-detection comparison — your experimental design"]
        direction TB
        GSCORE["GPCS scoring<br/>1 generation, evidence-grounded"]
        SC["Self-consistency<br/>3 generations, model-internal"]
        RESULT["Compared head-to-head<br/>agreement / disagreement by claim type"]
        GSCORE --> RESULT
        SC --> RESULT
    end

    RCA --> GSCORE
    RCA --> SC

    C5["Wang et al. 2022<br/>Self-consistency improves CoT reasoning"] -.cites.-> SC

    subgraph PENDING["Closest prior work — empirical comparison not done yet"]
        direction TB
        P1["MetaRCA<br/>Liang et al. 2026"]
        P2["Agentic structured graph traversal<br/>Cui et al. 2025"]
        P3["Graphical causal reasoning<br/>Chraim et al. 2026"]
    end

    RESULT -.still needed for journal submission.-> PENDING

    classDef yours fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef cited fill:#E6F1FB,stroke:#185FA5,color:#042C53
    classDef pending fill:#FAEEDA,stroke:#854F0B,color:#412402,stroke-dasharray: 4 3

    class M1,M4,M5,M6,LADDER,GSCORE,RESULT,COMPARE yours
    class M2,M3,SC,C1,C2,C3,C4,C5 cited
    class P1,P2,P3,PENDING pending
```
