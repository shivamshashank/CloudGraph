# CloudGraph documentation

**v1 is complete.** The system is built, deployed and evaluated; the results
in [`../experiment-1-benchmark/`](../experiment-1-benchmark/) are final. Remaining work is scoped to
v2 and listed in `project/ROADMAP.md` and the
[v2 section of the root README](../README.md).

Every document here is marked with what it describes: **built** (implemented
and, where relevant, exercised by the evaluation), or **planned** (design
intent that does not exist in the code). Diagrams that could not be marked
honestly were removed rather than captioned.

## Start here

| Document | Describes | Status |
|---|---|---|
| [`architecture/figures/current-architecture.svg`](architecture/figures/current-architecture.svg) | The evaluated pipeline end to end — solid boxes are built, dashed are not | **built** |
| [`architecture/system-overview.md`](architecture/system-overview.md) | Step-by-step lifecycle, install through investigation | **built** |

## Algorithm design

| Document | Describes | Status |
|---|---|---|
| [`design/GPCS_DESIGN.md`](design/GPCS_DESIGN.md) | Graph-Provenance Claim Scoring — claim extraction, evidence retrieval, trust score | **built**, thresholds **not calibrated** |
| [`design/GCP_DESIGN.md`](design/GCP_DESIGN.md) | Graph Confidence Propagation — Noisy-OR belief propagation over the topology | **built**, weights hand-set, output is not a probability |

Neither algorithm's parameters are fitted on held-out data. Where these
documents describe calibration, they describe intent; the code ships fixed
defaults (GPCS: 0.30 evidence floor, 0.50 trust cut).

## Running it

| Document | Describes |
|---|---|
| [`guides/QUICKSTART.md`](guides/QUICKSTART.md) | Deploy in a few minutes |
| [`guides/INSTALLATION.md`](guides/INSTALLATION.md) | Full install, prerequisites, configuration |
| [`guides/UI_WALKTHROUGH.md`](guides/UI_WALKTHROUGH.md) | Every screen, tab and button, with screenshots from a live run |

## Project state

| Document | Describes |
|---|---|

## Results and research

Documentation of the evaluation lives with the data it describes, not here:

| Location | Contains |
|---|---|
| [`../experiment-1-benchmark/FINDINGS.html`](../experiment-1-benchmark/results/EXPERIMENT_FINAL_RESULTS.md) | Eight findings with their evidential status, statistics and figures |
| [`../experiment-1-benchmark/README.md`](../experiment-1-benchmark/README.md) | Benchmark, results, integrity guarantees, known limitations |
| [`../experiment-1-benchmark/DATA_PROVENANCE.md`](../experiment-1-benchmark/README.md) | Where the data came from, how cases were selected and derived |
| [`../research/`](../research/) | Research questions, gaps, contribution analysis, experiment plan |

## Product scope vs evaluated scope

These are not the same, and the figures cover both.

The **product** ingests metrics (Prometheus), logs (Loki), traces (Tempo),
Kubernetes API objects, and Git/ArgoCD webhook events — every one has a
working adapter behind `routers/telemetry.py` and `routers/webhooks.py`, and
`01-overall-architecture.svg` shows that full surface.

The **evaluation** used a narrower slice: metrics and logs only, seeded from
RCAEval RE2 cases. Traces, webhook events and live Kubernetes discovery were
not exercised by any of the 36 scenarios. `current-architecture.svg` shows
that narrower path, which is the one every published number came from.

So a figure showing Tempo or Git is describing the product, not overclaiming
the experiment.

## The evaluated task, stated once

CloudGraph is evaluated on **fault-type diagnosis for a known affected
service**. The benchmark supplies the faulted service, so the system is asked
*why* it failed, never *which* service failed. No result in this repository
demonstrates root-cause service localisation.

## Figures

`architecture/figures/` holds only diagrams that match the code:

| Figure | Shows |
|---|---|
| [`current-architecture.svg`](architecture/figures/current-architecture.svg) | Evaluated pipeline, built vs planned |
| [`01-overall-architecture.svg`](architecture/figures/01-overall-architecture.svg) | Product component layout and full ingestion surface |
| [`02-service-dependency-graph.svg`](architecture/figures/02-service-dependency-graph.svg) | Example service topology |
| [`03-knowledge-graph-pipeline.svg`](architecture/figures/03-knowledge-graph-pipeline.svg) | Telemetry to graph construction |
| [`04-multi-agent-workflow.svg`](architecture/figures/04-multi-agent-workflow.svg) | Five specialists into static consensus |
| [`05-graphrag-pipeline.svg`](architecture/figures/05-graphrag-pipeline.svg) | Retrieval over the incident graph |
| [`knowledge-graph-schema.png`](architecture/figures/knowledge-graph-schema.png) | Node and relationship types |

Removed in the 2026-08-11 documentation pass, because they depicted
components that were never built (AWS/EKS/RDS/S3, seven agents including
trace/RCA/recommendation roles, cross-agent collaboration, Slack/PagerDuty/
Jira integrations, a continuous-learning loop, and multi-cluster
federation): high-level-architecture.png, multi-agent-workflow.png,
graphrag-pipeline.png, graphrag-investigation-pipeline.png,
aws-deployment.png, logical-architecture.png,
continuous-live-data-flow.png, 06-multi-cluster-architecture.svg,
07-end-to-end-pipeline.svg (its final stage was a continuous-learning loop
feeding back into the graph), and an unreferenced cluster screenshot. Git
history retains them.
