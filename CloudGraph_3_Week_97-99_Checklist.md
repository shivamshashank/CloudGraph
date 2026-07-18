# CloudGraph --- 3 Week Roadmap to a 97--99/100 MSc Dissertation

> Goal: Transform CloudGraph from an excellent engineering project into
> a research contribution with publication potential.

## Success Criteria

- [x] Complete end-to-end GraphRAG + Multi-Agent pipeline
- [x] Introduce **Graph Confidence Propagation (GCP)** (novel
    algorithm)
- [x] Introduce **Graph-Provenance Claim Scoring (GPCS)** (novel
    algorithm)
- [x] LLM Context Explorer UI comparing raw data for all 4 configs
- [ ] 60--80 balanced incident dataset
- [ ] Full ablation study
- [ ] Human evaluation (3--5 evaluators)
- [ ] Statistical analysis (CI + effect sizes)
- [ ] Dissertation chapters aligned to RQ1--RQ4

------------------------------------------------------------------------

# Week 1 --- Finish the Research System

## Platform

- [x] End-to-end deployment works
- [x] Neo4j + Qdrant integrated
- [x] GraphRAG retrieval operational
- [x] Multi-agent orchestration complete
- [x] RCA report generation complete

## Graph Confidence Propagation (NEW)

### Deliverables

- [x] Design confidence propagation algorithm
- [x] Confidence score for every graph node
- [x] Confidence decay across graph edges
- [x] Root Cause Confidence
- [x] Recommendation Confidence
- [x] Confidence visualization in UI

### Documentation

- [x] Mathematical formulation
- [x] Architecture diagram
- [x] Pseudocode
- [x] Complexity analysis

------------------------------------------------------------------------

# Week 2 --- Novel Research Contribution

## Graph-Provenance Claim Scoring (GPCS)

### Claim Extraction

- [x] Extract atomic claims from RCA
- [x] Classify (Temporal / Causal / State / Relationship)

### Evidence Alignment

- [x] Semantic retrieval
- [x] Graph retrieval
- [x] Merge evidence

### Trust Scoring

- [x] Semantic similarity
- [x] Graph proximity
- [x] Source reliability
- [x] Path-length penalty

### Outputs

- [x] Unsupported Claim Rate
- [x] Claim confidence
- [x] Evidence path
- [x] UI highlighting

## Baselines

- [x] Keyword Search
- [x] Vector RAG
- [x] GraphRAG
- [x] GraphRAG + Agents
- [x] GraphRAG + Agents + GCP
- [x] GraphRAG + Agents + GCP + GPCS

## LLM Context Explorer (NEW)

### Deliverables

- [x] Implement backend endpoint `/api/v1/investigations/context-comparison` returning raw payloads for all 4 parts
- [x] Create UI Context Explorer tab inside AI Diagnosis page
- [x] Add 4-way toggles in UI to display exact logs, metrics, and prompts sent under each configuration

------------------------------------------------------------------------

# Week 3 --- Evaluation & Dissertation

## Dataset

- [ ] 60--80 incidents
- [ ] Balanced categories
- [ ] Ground truth labels

## Ablation Study

- [ ] Remove GraphRAG
- [ ] Remove Agents
- [ ] Remove GCP
- [ ] Remove GPCS

Measure: - Accuracy - Precision - Recall - F1 - MTTR reduction -
Hallucination rate - Latency

## Human Evaluation

- [ ] 3--5 SRE/DevOps reviewers
- [ ] Blind comparison
- [ ] Usefulness
- [ ] Trustworthiness
- [ ] Explainability
- [ ] Inter-rater agreement

## Statistics

- [ ] Confidence intervals
- [ ] Effect size
- [ ] Significance tests

## Dissertation

- [ ] Methodology
- [ ] Algorithm design
- [ ] Experimental setup
- [ ] Results
- [ ] Threats to validity
- [ ] Limitations
- [ ] Future work

------------------------------------------------------------------------

# Stretch Goals (Only if time remains)

- [ ] Conference paper draft
- [ ] Demo video
- [ ] Interactive evidence graph
- [ ] Live Kubernetes demo

------------------------------------------------------------------------

# Final Submission Checklist

## Research

- [ ] Two named algorithms (GCP + GPCS)
- [ ] Novel contribution clearly stated
- [ ] RQ1--RQ4 answered

## Engineering

- [ ] Clean architecture
- [ ] Tests passing
- [ ] Reproducible deployment

## Evaluation

- [ ] Baselines
- [ ] Ablation
- [ ] Human study
- [ ] Statistical evidence

## Dissertation Quality

- [ ] Professional figures
- [ ] High-quality writing
- [ ] Critical discussion
- [ ] Honest limitations

# Target Outcome

Expected dissertation score: **97--99/100**

This roadmap prioritizes research depth over feature breadth. Every new
feature must strengthen the research questions or evaluation; avoid
adding unrelated engineering work.
