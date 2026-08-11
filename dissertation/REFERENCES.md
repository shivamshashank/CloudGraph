# References

Supersedes the Week 1 reference list (`dissertation/week-1/references.md`,
removed — in git history), adding the benchmark, hallucination-detection, and
statistical-methods sources the project came to depend on, and closing that
list's numbering gap (it ran 12 → 14). Numbering here is the numbering used by
[`LITERATURE_REVIEW.md`](LITERATURE_REVIEW.md).

> **Verification status.** Entries marked ⚠ were carried forward from the
> Week 1 reference list and have **not** been independently checked against a
> canonical record. Verify every ⚠ entry — author list, title, venue, and
> identifier — against arXiv or the publisher before submission. An
> unverifiable citation in a submitted dissertation is an academic-integrity
> problem, not a formatting one.

---

## Retrieval and generation

**[1]** Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal,
N., Küttler, H., Lewis, M., Yih, W., Rocktäschel, T., Riedel, S., and Kiela,
D. (2020). *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.*
Advances in Neural Information Processing Systems (NeurIPS) 33.
arXiv:2005.11401. <https://arxiv.org/abs/2005.11401>

**[2]** Edge, D., Trinh, H., Cheng, N., Bradley, J., Chao, A., Mody, A.,
Truitt, S., and Larson, J. (2024). *From Local to Global: A Graph RAG Approach
to Query-Focused Summarization.* arXiv:2404.16130.
<https://arxiv.org/abs/2404.16130>

**[7]** Reimers, N., and Gurevych, I. (2019). *Sentence-BERT: Sentence
Embeddings using Siamese BERT-Networks.* EMNLP-IJCNLP 2019. arXiv:1908.10084.
<https://arxiv.org/abs/1908.10084> — the lineage of the
`sentence-transformers/all-MiniLM-L6-v2` model used by CloudGraph.
<https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2>

## Multi-agent LLM systems

**[3]** Guo, T., Chen, X., Wang, Y., Chang, R., Pei, S., Chawla, N. V.,
Wiest, O., and Zhang, X. (2024). *Large Language Model based Multi-Agents: A
Survey of Progress and Challenges.* arXiv:2402.01680.
<https://arxiv.org/abs/2402.01680>

## Cloud-native root cause analysis

⚠ **[4]** Liang, S., Chen, P., Tian, B., Tan, G., Xu, M., Qu, Y., Zhao, Y.,
Shang, Y., and Tan, C. (2026). *MetaRCA: A Generalizable Root Cause Analysis
Framework for Cloud-Native Systems Powered by Meta Causal Knowledge.*
arXiv:2603.02032. <https://arxiv.org/abs/2603.02032>

⚠ **[5]** Cui, S., Krishna, R., Jha, S., and Iyer, R. K. (2025). *Agentic
Structured Graph Traversal for Root Cause Analysis of Code-related Incidents
in Cloud Applications.* arXiv:2512.22113. <https://arxiv.org/abs/2512.22113>

⚠ **[6]** Chraim, F., Janzing, D., and Evans, J. (2026). *Graphical Causal
Reasoning for Root Cause Analysis in Cloud Networks.* arXiv:2606.13532.
<https://arxiv.org/abs/2606.13532>

## Benchmark

**[8]** Pham, L., Zhang, H., Ha, H., Salim, F., and Zhang, X. *RCAEval: A
Benchmark for Root Cause Analysis of Microservice Systems with Telemetry
Data.* FSE 2026; WWW 2025 (Companion); ASE 2024. arXiv:2412.17015.
<https://arxiv.org/abs/2412.17015>
Dataset DOI: 10.5281/zenodo.14590730 — <https://doi.org/10.5281/zenodo.14590730>
Code: <https://github.com/phamquiluan/RCAEval> · Data:
<https://huggingface.co/datasets/phamquiluan/RCAEval> · Licence: MIT.
CloudGraph uses 36 cases from the **RE2** suite; see
[`experiments/DATA_PROVENANCE.md`](../experiments/DATA_PROVENANCE.md).

## Hallucination and claim verification

**[9]** Ji, Z., Lee, N., Frieske, R., Yu, T., Su, D., Xu, Y., Ishii, E., Bang,
Y., Madotto, A., and Fung, P. (2023). *Survey of Hallucination in Natural
Language Generation.* ACM Computing Surveys, 55(12), 1–38. arXiv:2202.03629.
<https://arxiv.org/abs/2202.03629>

**[10]** Wang, X., Wei, J., Schuurmans, D., Le, Q., Chi, E., Narang, S.,
Chowdhery, A., and Zhou, D. (2022). *Self-Consistency Improves Chain of
Thought Reasoning in Language Models.* ICLR 2023. arXiv:2203.11171.
<https://arxiv.org/abs/2203.11171>

**[11]** Manakul, P., Liusie, A., and Gales, M. J. F. (2023). *SelfCheckGPT:
Zero-Resource Black-Box Hallucination Detection for Generative Large Language
Models.* EMNLP 2023. arXiv:2303.08896. <https://arxiv.org/abs/2303.08896> —
the design basis for CloudGraph's self-consistency baseline verifier.

## Platform and observability documentation

**[12]** Kubernetes Documentation. *Overview.*
<https://kubernetes.io/docs/concepts/overview/>

**[13]** Neo4j Documentation. *Graph database.*
<https://neo4j.com/docs/getting-started/graph-database/>

**[14]** Qdrant Documentation. *Overview.*
<https://qdrant.tech/documentation/overview/>

**[15]** Prometheus Documentation. *Overview.*
<https://prometheus.io/docs/introduction/overview/>

**[16]** OpenTelemetry Documentation. *Signals.*
<https://opentelemetry.io/docs/concepts/signals/>

**[17]** Grafana Loki Documentation.
<https://grafana.com/docs/loki/latest/>

**[18]** kube-state-metrics. *Add-on agent to generate and expose
cluster-level metrics.* <https://github.com/kubernetes/kube-state-metrics>

**[19]** Prometheus node_exporter. *Exporter for machine metrics.*
<https://github.com/prometheus/node_exporter>

**[20]** Falco. *Cloud native runtime security.* <https://falco.org/>

**[21]** Argo CD Documentation. *Notifications Overview.*
<https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/>

**[22]** Argo CD Documentation. *Git Webhook Configuration.*
<https://argo-cd.readthedocs.io/en/release-2.9/operator-manual/webhook/>

## Statistical methods

**[23]** Efron, B., and Tibshirani, R. J. (1993). *An Introduction to the
Bootstrap.* Chapman & Hall/CRC. — basis for the scenario-clustered paired
bootstrap in [`scripts/paired_bootstrap.py`](../services/api/scripts/paired_bootstrap.py).

**[24]** Wilcoxon, F. (1945). *Individual Comparisons by Ranking Methods.*
Biometrics Bulletin, 1(6), 80–83. — basis for the paired signed-rank tests
reported alongside every bootstrap interval.

---

## How these sources map to CloudGraph

| Source | Where it is used in the system |
|---|---|
| [1] RAG | Defines the vector-retrieval baseline condition |
| [2] GraphRAG | Motivates graph traversal and multi-hop context expansion |
| [3] Multi-agent survey | Justifies the five specialist agents and consensus design |
| [4] [5] [6] Cloud RCA | Situates the work against current RCA approaches |
| [7] Sentence-BERT | The embedding model in `services/embeddings.py` |
| [8] RCAEval | The entire evaluation corpus — 36 RE2 cases |
| [9] Hallucination survey | Defines "unsupported claim" as a measurable quantity |
| [10] [11] Self-consistency / SelfCheckGPT | The baseline verifier GPCS is compared against |
| [12] Kubernetes | The entity model for the knowledge graph |
| [16] OpenTelemetry | The signal model: logs, metrics, traces |
| [15] Prometheus, [17] Loki | Live metric and log ingestion adapters |
| [18] kube-state-metrics, [19] node_exporter | Object-state and host-level metrics |
| [20] Falco | Runtime security event ingestion |
| [21] [22] Argo CD | Deployment, sync, health and GitOps event ingestion |
| [13] Neo4j | Graph schema and Cypher traversal |
| [14] Qdrant | Vector index for semantic retrieval |
| [23] [24] Bootstrap, Wilcoxon | Every confidence interval and p-value reported |
