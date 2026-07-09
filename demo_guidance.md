# CloudGraph Status Update & Demo Talk Track (Week 4)

This document provides a breakdown of what has been implemented so far, what remains on the roadmap, and a complete script for tomorrow's demo.

---

## 1. What is Done vs. What is Left

CloudGraph has completed **Weeks 1–4** of the dissertation roadmap. The infrastructure, knowledge graph ingestion, vector database integration, and hybrid GraphRAG retrieval layers are fully functional and merged into the `main` branch.

### ✅ What is Done (Implemented & Verified)

1. **Unified Go CLI (`cloudgraph`)**
   - Commands for deployment (`deploy`), cleanup (`uninstall`), validation (`doctor`), and health checking (`status`, `health`, `ingest`).
   - Automated provisioning of local Kubernetes tooling (swap disabled, conntrack configuration, container runtimes, Flannel CNI, and Rancher Local Path Storage).
2. **Production-Ready Helm Chart**
   - Deploys API Ingestion, UI, Agent Orchestrator, and Investigation Engine.
   - Sets up dependencies: Neo4j (graph database), Qdrant (vector database), Redis (cache/queue), and OpenTelemetry Collector.
3. **Knowledge Graph Ingestion Pipeline**
   - Parsers for Prometheus metrics, Loki logs, Git commits, and ArgoCD deployment webhooks.
   - Relationship linkages mapping pods to nodes, services, deployments, and namespaces.
4. **Core GraphRAG Retrieval Engine**
   - **Qdrant Vector Client**: Configured with a `sentence-transformers` embedder (using `all-MiniLM-L6-v2`) and a local hashed-file fallback for offline-safe execution.
   - **Multi-hop Cypher Traversal**: Traverses graph neighborhoods (depth=2+) with temporal constraint filtering.
   - **Hybrid Ranking Algorithm**: Combines vector cosine similarity + graph proximity (hop distance) + log/incident recency into a combined relevance score.
   - **Explainability API**: Returns a detailed ranking rationale and evidence chain showing *why* each item was retrieved.
5. **Interactive UI Dashboards**
   - **Side-by-side search comparison view**: Direct search comparison showing results from Keyword Search vs. GraphRAG Search.
   - **Detailed Evidence Page**: Visualizes evidence chains, hop counts, and score breakdowns.
   - **Incident Simulation Tool**: Shell script (`apply_demo_incident.sh`) injecting a failing Payment App crashing with an invalid container image and broken database credentials.

---

### ⚠️ What is Left (Roadmap Weeks 5–8)

1. **Multi-Agent Orchestrator (Week 5)**
   - Developing specialized agent nodes (Monitoring Agent, Log Agent, Deployment Agent, Security Agent) using a LangGraph framework.
   - Creating the **Consensus Engine** (evidence aggregation, confidence voting, and cross-agent correlation).
2. **RCA Reasoning & Recommendations (Week 6)**
   - Generating explainable graph reasoning paths.
   - Proposing concrete remediation plans (e.g., rolling back deployment, scaling resources).
3. **Rigorous Evaluation & Benchmark Dataset (Week 7)**
   - Injecting 100+ simulated failure scenarios.
   - Running statistical tests (T-Test, Wilcoxon) comparing precision, recall, and MTTR reduction across:
     - Baseline A: Keyword Search
     - Baseline B: Vector-only RAG
     - Baseline C: GraphRAG
     - Baseline D: GraphRAG + Multi-Agent Orchestration.
4. **Dissertation Compilation & Submission (Week 8)**
   - Writing final thesis chapters and finalizing codebase documentation.

---

## 2. Step-by-Step Demo Script & Talk Track (5–7 Minutes)

This script is structured to show the transition from "raw data" to "intelligence," specifically highlighting the core contribution of **GraphRAG vs. Traditional Search**.

### Phase 1: Setup & Preflight Check (Before the Demo)

1. Connect to your Kubernetes VM/cluster.
2. Compile/verify the CLI: `go build -o cloudgraph ./cmd/cloudgraph`.
3. Verify all services are healthy: `./cloudgraph status` and `./cloudgraph doctor`.
4. Run the UI port-forward in a background terminal:

   ```bash
   kubectl -n cloudgraph-system port-forward svc/cloudgraph-ui 8080:80
   ```

5. Open your web browser to `http://localhost:8080` (UI Home page).

---

### Phase 2: Live Presentation Script

#### **Minute 0–1: Introduction & The Core Claim**

- **Action:** Show the title screen/UI homepage.
- **What to speak:**
  > "Hi everyone. Today I'm demonstrating CloudGraph, an intelligent Kubernetes incident investigation platform.
  > In modern cloud environments, when an incident occurs, SREs are overwhelmed by disconnected alerts, logs, and metrics.
  > The core thesis of CloudGraph is that **representing system structures as a Knowledge Graph and combining it with Vector Search—known as GraphRAG—leads to faster, more explainable root cause analysis than traditional keyword or vector search alone.**
  > Today, we'll see the deployment, simulate a failure, and contrast traditional search directly with our GraphRAG engine."

#### **Minute 1–2: Single-Command Deploy & Status**

- **Action:** Bring up your terminal. Show the `cloudgraph status` output.
- **What to speak:**
  > "First, the platform is designed for zero-friction installation. We compiled a unified Go CLI. A single command—`cloudgraph deploy`—brings up the entire system.
  > If we run `./cloudgraph status`, we see our dashboard. The CLI automatically checks our cluster context, verifies that our core microservices—the API, UI, and Agent Orchestrator—are running, and confirms that Qdrant and Neo4j are active and reachable. We can see our vector collections are already running."

#### **Minute 2–3: Injecting the Incident**

- **Action:** Run the incident injection script:

  ```bash
  ./scripts/apply_demo_incident.sh
  ```

  Then run `kubectl -n cloudgraph-system get pods` to show the crashing pod.
- **What to speak:**
  > "Let's inject a real-world incident. I'll execute our simulation script. This deploys a microservice called `demo-payment-app` in our namespace.
  > If I check the pods, we see the payment app is in a crash loop due to `ImagePullBackOff`. However, behind the scenes, there's a deeper configuration problem: the pod was also deployed with an incorrect database password environment variable. In a real system, this is hard to trace because the pod crashed before logging a database error. Let's see how CloudGraph helps."

#### **Minute 3–5: The Climax — Side-by-Side Search**

- **Action:** Switch to the web browser (`http://localhost:8080`).
  - Click on **Search / GraphRAG** in the menu.
  - In the search input, type: `payment database`
  - Select **Keyword** search and show the sparse/irrelevant results.
  - Then select **Hybrid / GraphRAG** and press Search. Point to the richer, connected results.
- **What to speak:**
  > "Now, I will open the UI. We've built a search interface that lets us evaluate different retrieval methodologies side-by-side.
  > If an engineer searches for 'payment database' using **Traditional Keyword Search**, we get almost no results, or we get basic, disconnected pod names because keyword search requires exact matches and doesn't understand context.
  > But when I switch to **GraphRAG Search**, we see a completely different picture. The engine uses vector embeddings from Qdrant to find semantically relevant terms, but then it goes a step further: it performs a multi-hop traversal in Neo4j to pull the surrounding context. It returns the related secrets, the parent deployment, and the host node."

#### **Minute 5–6: Explainability & Ranking Rationale**

- **Action:** Click on one of the search results or navigate to the **Evidence** tab to show the score breakdown and path steps.
- **What to speak:**
  > "One of the major research contributions here is **Explainability**. We don't just return a black-box list.
  > Under the hood, our hybrid ranking engine scores evidence using a formula that weights: vector similarity, graph proximity (how many hops away an event is from the failure point), and temporal recency.
  > In the UI, the engineer can see the exact **Evidence Chain**: it shows that this pod is connected to this deployment, which in turn was updated by a git commit containing changed database configs. We can trace the provenance of the recommendation back to the exact files and lines of code."

#### **Minute 6–7: Wrap-up & Roadmap**

- **Action:** Click on the "Run AI Diagnosis" button. Explain that it is rule-based now, pointing to the Multi-Agent framework next.
- **What to speak:**
  > "Right now, triggering a diagnosis runs our initial rule-based analyzer, which highlights the failing image tag.
  > However, this brings us to our next milestones. Now that the core GraphRAG retrieval engine is complete, Week 5 and 6 will replace this baseline logic with a **Multi-Agent Orchestrator** using LangGraph. Log, Metric, and Deployment agents will collaboratively review this ranked evidence to form a consensus on the root cause and propose risk-assessed remediations.
  > Thank you, and I'd be happy to take any questions."

---

## 3. Anticipated Q&A (Be Prepared)

- **Q: Why did you use Sentence Transformers locally instead of OpenAI?**
  - **A:** "For two reasons: First, local embedding models like `all-MiniLM-L6-v2` ensure offline safety and network independence, which is critical for air-gapped enterprise systems and demo reliability. Second, it reduces API costs during the 100+ incident benchmark evaluations in Week 7."
- **Q: How does the hybrid ranking work?**
  - **A:** "It runs a reciprocal rank fusion-style formula: it combines the vector similarity score from Qdrant, subtracts penalty points for every additional hop distance traversed in the Neo4j graph, and factors in a decay function for temporal recency. This ensures that only relevant, fresh, and physically connected evidence ranks at the top."
- **Q: How will the multi-agent system differ from a single LLM call?**
  - **A:** "A single LLM call suffers from context limits and hallucination when digesting raw streams of metrics and logs. By dividing labor among dedicated agents (e.g., one agent focusing on Git events, another on OTel metrics), each agent produces high-precision local hypotheses. The coordinator then fuses these inputs, leading to a much more accurate and explainable consensus."
