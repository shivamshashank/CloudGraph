# References

These are the Week 1 sources used to justify the CloudGraph research direction,
architecture, and evaluation plan.

## Academic and Research Sources

1. Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir
   Karpukhin, Naman Goyal, Heinrich Kuttler, Mike Lewis, Wen-tau Yih, Tim
   Rocktaschel, Sebastian Riedel, and Douwe Kiela. "Retrieval-Augmented
   Generation for Knowledge-Intensive NLP Tasks." NeurIPS, 2020.
   <https://arxiv.org/abs/2005.11401>

2. Darren Edge, Ha Trinh, Newman Cheng, Joshua Bradley, Alex Chao, Apurva Mody,
   Steven Truitt, and Jonathan Larson. "From Local to Global: A Graph RAG
   Approach to Query-Focused Summarization." arXiv, 2024.
   <https://arxiv.org/abs/2404.16130>

3. Taicheng Guo, Xiuying Chen, Yaqi Wang, Ruidi Chang, Shichao Pei, Nitesh V.
   Chawla, Olaf Wiest, Xiangliang Zhang. "Large Language Model based
   Multi-Agents: A Survey of Progress and Challenges." arXiv, 2024.
   <https://arxiv.org/abs/2402.01680>

4. Shuai Liang, Pengfei Chen, Bozhe Tian, Gou Tan, Maohong Xu, Youjun Qu, Yahui
   Zhao, Yiduo Shang, and Chongkang Tan. "MetaRCA: A Generalizable Root Cause
   Analysis Framework for Cloud-Native Systems Powered by Meta Causal
   Knowledge." arXiv, 2026.
   <https://arxiv.org/abs/2603.02032>

5. Shengkun Cui, Rahul Krishna, Saurabh Jha, and Ravishankar K. Iyer. "Agentic
   Structured Graph Traversal for Root Cause Analysis of Code-related Incidents
   in Cloud Applications." arXiv, 2025.
   <https://arxiv.org/abs/2512.22113>

6. Fabien Chraim, Dominik Janzing, and John Evans. "Graphical Causal Reasoning
   for Root Cause Analysis in Cloud Networks." arXiv, 2026.
   <https://arxiv.org/abs/2606.13532>

## Official Technical Documentation

7. Kubernetes Documentation. "Overview."
   <https://kubernetes.io/docs/concepts/overview/>

8. OpenTelemetry Documentation. "Signals."
   <https://opentelemetry.io/docs/concepts/signals/>

9. Neo4j Documentation. "Graph database."
   <https://neo4j.com/docs/getting-started/graph-database/>

10. Qdrant Documentation. "Overview."
    <https://qdrant.tech/documentation/overview/>

11. Prometheus Documentation. "Overview."
    <https://prometheus.io/docs/introduction/overview/>

12. Grafana Loki Documentation.
    <https://grafana.com/docs/loki/latest/>

14. Kubernetes kube-state-metrics. "Add-on agent to generate and expose cluster-level metrics."
    <https://github.com/kubernetes/kube-state-metrics>

15. Prometheus node_exporter. "Exporter for machine metrics."
    <https://github.com/prometheus/node_exporter>

16. Falco. "Cloud native runtime security."
    <https://falco.org/>

17. Argo CD Documentation. "Notifications Overview."
    <https://argo-cd.readthedocs.io/en/stable/operator-manual/notifications/>

18. Argo CD Documentation. "Git Webhook Configuration."
    <https://argo-cd.readthedocs.io/en/release-2.9/operator-manual/webhook/>

## How These Sources Map To CloudGraph

| Source Area | CloudGraph Design Use |
| --- | --- |
| RAG | Defines the traditional retrieval baseline. |
| GraphRAG | Justifies graph-based retrieval and multi-hop incident context expansion. |
| Multi-agent LLM systems | Justifies specialist investigation agents and consensus design. |
| Cloud-native RCA | Justifies the focus on observability data, topology, causality, and explainability. |
| Kubernetes | Defines the workload and resource model for incidents. |
| OpenTelemetry | Defines telemetry signals: logs, metrics, traces, and related instrumentation. |
| Prometheus | Supports live metric scraping and time-series evidence collection. |
| Loki | Supports log aggregation and log-based incident evidence. |
| kube-state-metrics | Supports Kubernetes object-state metrics for pods, deployments, nodes, and jobs. |
| node_exporter | Supports host-level infrastructure metrics. |
| Falco | Supports runtime security event collection. |
| Argo CD | Supports deployment, sync, health, and GitOps event ingestion. |
| Neo4j | Supports graph schema and Cypher-based traversal. |
| Qdrant | Supports vector retrieval baseline and hybrid retrieval. |
