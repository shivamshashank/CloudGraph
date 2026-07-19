# CloudGraph Dissertation Completion Plan

## 1. Current project status

### What is already implemented

- Kubernetes deployment and Helm chart exist.
- Observability stack and telemetry ingestion pipeline are implemented.
- Neo4j knowledge graph schema and graph ingestion adapters exist.
- Qdrant semantic vector store integration is implemented, with local fallback.
- GraphRAG retrieval endpoints `/api/v1/graphrag/search` and `/api/v1/graphrag/retrieve` exist.
- Hybrid ranking logic is implemented in `services/api/app/retrieval/hybrid_ranker.py`.
- LLM-capable multi-agent pipeline exists in `services/investigation-engine/main.py` and `services/agent-orchestrator/main.py`.
- Graph Confidence Propagation (GCP) is implemented in `services/api/app/research/gcp.py`.
- Research documentation for RQs, methodology, literature review, architecture, and evidence planning exists in `docs/week-1/*`.

### What is not finished or incomplete

- Graph-Provenance Claim Scoring (GPCS) is implemented in `services/api/app/research/gpcs.py` and integrated into investigation responses, though the evaluation pipeline is incomplete.
- LLM Context Explorer backend/UI is implemented via `/api/v1/investigations/context-comparison` and the AI Diagnosis context explorer UI.
- A complete 60–80 incident benchmark dataset with ground truth labels is not present.
- Full evaluation runs and baseline comparisons (keyword, vector, GraphRAG, GraphRAG+Agents, GraphRAG+GCP, GraphRAG+GCP+GPCS) are missing.
- Hallucination/unsupported-claim metrics are now present in the investigation API response, but the evaluation pipeline is not complete.
- Human evaluation setup, ratings collection, and inter-rater agreement are not implemented.
- Dissertation chapter drafts are missing; only planning and evidence mapping exist.
- LLM Context Explorer backend/UI is not implemented.
- Some documented infrastructure assumptions are inconsistent with reality, especially around AWS/Terraform vs Helm/kubeadm.
- UI evidence/hallucination highlighting is not complete.
- Deployment hygiene items remain: Redis caching is now wired; stale CRD config was removed from the Helm values; secret handling still requires a fully documented generated-secret path.

## 2. Completion checklist

### Core roadmap tasks

- [ ] Implement Graph-Provenance Claim Scoring (GPCS) and unsupported-claim rate.
- [ ] Add claim extraction and evidence alignment for RCA output.
- [ ] Integrate GPCS into the investigation pipeline and API responses.
- [ ] Add prompt files and structured LLM output templates for reproducibility.
- [ ] Build a balanced 60–80 incident benchmark dataset with ground truth root cause labels.
- [ ] Run all baselines and ablations with recorded metrics.
- [ ] Implement statistical tests and tables for significance, confidence intervals, and effect sizes.
- [ ] Perform a human evaluation with 3–5 reviewers.
- [ ] Write dissertation chapter drafts and finalize the dissertation.
- [ ] Prepare a conference/journal publication plan and draft.

### Engineering & research quality

- [ ] Add UI support for per-claim evidence, trust scores, and unsupported claim highlighting.
- [ ] Add a backend endpoint for LLM context comparison if possible.
- [ ] Ensure retrieval results include explainable evidence chains.
- [ ] Convert any outdated completion claims in docs to accurate status or historical notes.
- [ ] Clean up deployment config: make Redis usage real or remove it, add missing CRDs, and eliminate hardcoded default secrets.
- [ ] Add end-to-end regression tests for the final investigation pipeline.

## 3. Exact plan to complete the dissertation

### Phase 1: Core system completion

1. Implement GPCS and hallucination scoring
   - Create a `GraphProvenanceClaimScorer` module.
   - Add claim extraction from generated RCA text (LLM-backed or structured parser).
   - Align extracted claims with evidence using semantic store search and graph traversal.
   - Score each claim using semantic similarity, graph proximity, source reliability, and path-length penalty.
   - Compute `unsupported_claim_rate` and expose it in the investigation API response.
   - Store per-claim support paths and trust scores for the UI.

2. Harden the multi-agent investigation pipeline
   - Ensure `investigation-engine` and `agent-orchestrator` use structured JSON outputs from LLMs consistently.
   - Add prompt files and a versioned prompt directory.
   - Confirm fallback logic is distinct from normal LLM execution.
   - Add test coverage for the LLM orchestration path using mock responses.

3. Stabilize retrieval and evidence chain flow
   - Verify Qdrant collection creation and search path.
   - Confirm `graph_traversal_retriever` is returning meaningful hops and temporal context.
   - Extend the evidence builder to include graph-node IDs and relationship paths.

### Phase 2: Dataset and evaluation

1. Build the evaluation dataset
   - Collect or synthesize 60–80 incident scenarios across categories:
     - Kubernetes workload failures
     - Networking/service connectivity issues
     - Security/authentication incidents
     - Deployment failures and rollbacks
     - Metrics/resource saturation
   - Add ground truth labels for root cause, remediation, and evidence.
   - Document the dataset creation process and limitations.

2. Implement baselines and ablations
   - Keyword search baseline.
   - Vector-only RAG baseline.
   - GraphRAG baseline.
   - GraphRAG + Agents baseline.
   - GraphRAG + Agents + GCP baseline.
   - GraphRAG + Agents + GCP + GPCS final system.

3. Collect evaluation metrics
   - RCA accuracy, precision, recall, F1 score.
   - Top-1/top-3 rank metrics.
   - Hallucination rate / unsupported claim rate.
   - MTTR proxy and reasoning efficiency.
   - Retrieval and end-to-end latency.

4. Run statistical analysis
   - Use paired tests (t-test / Wilcoxon) where applicable.
   - Report confidence intervals and effect sizes.
   - Compare each ablation to the full system.
   - Document threats to validity and dataset bias.

5. Execute human evaluation
   - Prepare a blind comparison protocol.
   - Collect usefulness, trustworthiness, and explainability ratings.
   - Calculate inter-rater agreement.
   - Add qualitative feedback to the discussion.

### Phase 3: Dissertation writing and publication

1. Write the dissertation chapters
   - Introduction: problem, motivation, research questions, contributions.
   - Related work: GraphRAG, AIOps, RCA, hallucination reduction, confidence-aware systems.
   - Methodology: experimental design, baselines, metrics, human evaluation, validity.
   - System design: architecture, graph schema, retrieval, agents, GCP, GPCS.
   - Implementation: ingestion, graph build, retrieval API, investigation pipeline.
   - Evaluation: dataset, results, statistical analysis, ablation.
   - Discussion: strengths, limitations, ethical considerations, future work.
   - Conclusion: answers to RQ1–RQ4 and publication potential.

2. Add technical dissertation content
   - Formalize the GCP algorithm and show math/pseudocode.
   - Formalize GPCS and show the scoring formula.
   - Include evidence chain diagrams and tables.
   - Add a dataset summary table and evaluation result tables.
   - Add a research contribution section for publication.

3. Prepare publication materials
   - Draft a conference paper centered on the novel GPCS + GraphRAG + agent evaluation.
   - Aim for a workshop or conference in AIOps / cloud-native systems first.
   - Prepare a journal extension for IEEE/ACM if time permits.

## 4. Publication and journal plan

### Candidate venues

- Conferences
  - USENIX Annual Technical Conference (ATC)
  - ACM/IEEE International Conference on Software Engineering (ICSE) Workshop or SEIP
  - IEEE International Conference on Cloud Engineering (IC2E)
  - ACM Symposium on Cloud Computing (SoCC)
  - AIOps / AI Systems Workshop co-located with ICML / NeurIPS / KDD

- Journals
  - IEEE Transactions on Cloud Computing
  - ACM Transactions on Autonomous and Adaptive Systems (TAAS)
  - IEEE Transactions on Network and Service Management
  - Journal of Systems and Software
  - IEEE Transactions on Dependable and Secure Computing

### Publication focus

- Core novelty: Graph-Provenance Claim Scoring (GPCS) for hallucination reduction in GraphRAG-based RCA.
- Supporting novelty: confidence-aware GraphRAG + multi-agent orchestration in cloud incident investigation.
- Evaluation story: baseline comparisons, ablation analysis, hallucination metrics, MTTR proxy, and human reviewer validation.
- Engineering contribution: reproducible cloud-native deployment with Neo4j, Qdrant, Helm, and LLM agent orchestration.

## 5. Recommended immediate next steps

- [ ] Create the `GraphProvenanceClaimScorer` implementation and integrate it into `/investigations/trigger`.
- [ ] Add claim-level support data to the API response and UI evidence chain.
- [ ] Build the 60–80 incident dataset and the evaluation runner.
- [ ] Draft dissertation chapter outlines and map each to repo evidence.
- [ ] Clean doc claims that overstate current completion and label historical/optional paths clearly.

## 6. Notes for cleanup

- Redis is configured in Helm but currently unused; either implement caching or remove the dependency.
- CRDs are declared in `values.yaml` but missing templates in the Helm chart.
- Default secrets and passwords should be replaced with generated Kubernetes secrets.
- Ensure `HALLUCINATION_SCORING_DESIGN.md` moves from design to implementation quickly; it is the highest-leverage research gap.
- Preserve the documented research narrative while correcting any outdated completion checkmarks.
