# CloudGraph — install, connect an LLM, run diagnosis, view benchmarks

Green = built and working today. Amber dashed = not built yet (script
exists, no UI page). The code supports **three** cloud LLM providers —
OpenAI, Gemini, and Meta's Llama API — all via the same `call_llm` pattern
in `agent-orchestrator/main.py`, `investigation-engine/main.py`, and
`gpcs.py`. An earlier local-only-via-Ollama iteration (and, before that, a
six-provider lineup including Claude/Groq/OpenRouter) was tried and
reverted; this is the current, settled architecture.

```mermaid
flowchart TD
    A["Install CloudGraph<br/>Go CLI + Helm chart"] --> B["Deploy to a Kubernetes cluster<br/>cloudgraph deploy"]
    B --> E{"Choose LLM provider<br/>in Settings UI"}

    E --> P1["OpenAI"]
    E --> P2["Gemini"]
    E --> P3["Meta Llama API"]

    P1 & P2 & P3 --> F["Save provider + key + model"]
    F --> G[("Stored server-side in Neo4j<br/>Settings node")]

    G --> H["User clicks Run AI Diagnosis"]
    H --> I["POST /api/v1/investigations/trigger"]
    I --> J["Orchestrator:<br/>5 specialists + consensus"]
    J --> K["GCP confidence propagation"]
    K --> L["GPCS claim scoring"]
    L --> M["Answer shown in UI<br/>root cause, confidence, evidence chain"]

    G --> N["User opens Benchmark screen"]
    N --> O["6-method benchmark<br/>keyword through +GPCS"]
    N --> R["GPCS vs self-consistency screen<br/>backend script only, no UI yet"]

    classDef built fill:#E1F5EE,stroke:#0F6E56,color:#04342C
    classDef pending fill:#FAEEDA,stroke:#854F0B,color:#412402,stroke-dasharray: 4 3

    class A,B,E,P1,P2,P3,F,G,H,I,J,K,L,M,N,O built
    class R pending
```
