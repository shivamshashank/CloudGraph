# Design Evolution / Deviations from Initial Design

CloudGraph's implementation diverged from its original design in three
places. Each is documented here as an engineering decision with a reason,
not an omission — per `research/OXBRIDGE_READINESS.md`'s own framing,
undocumented drift between what a repo claims and what it does is a
credibility liability for a reviewer or examiner, not a cosmetic detail.

## 1. Cloud provider: AWS → Helm/kubeadm

**Original plan:** deploy on AWS (EKS), with the architecture diagrams and
badges reflecting that.

**What actually shipped:** a Kubernetes-native deployment via Helm charts
(`deployments/helm/cloudgraph/`) on kubeadm — provider-agnostic, not tied
to AWS. `cmd/cloudgraph/deploy.go` installs kubeadm and Helm directly, and
the entire session's real development and testing (25-scenario report
runs, the matched-compute control, all figures in `experiments/`) ran on a
single-node kubeadm cluster on a plain Linux server, never on AWS.

**Why:** provider-agnostic Kubernetes is strictly more general than an
AWS-specific deployment — anything that runs on kubeadm runs on EKS,
GKE, or bare metal without code changes, and developing/testing against a
local VM removed cloud cost and credential management from the
development loop entirely. AWS EKS remains a valid *optional* target
(README.md's architecture section already notes this), just not the one
actually built or tested against.

## 2. Multi-agent orchestration: LangGraph → custom HTTP orchestrator

**Original plan:** use LangGraph for multi-agent orchestration.

**What actually shipped:** two custom Python services
(`agent-orchestrator/main.py`, `investigation-engine/main.py`) built on
`http.server.BaseHTTPRequestHandler`, exchanging JSON over HTTP, with a
`ConsensusEngine` class doing static-weight vote aggregation
(`agent-orchestrator/main.py`'s `WEIGHTS` dict) — no LangGraph dependency
anywhere in the codebase.

**Why:** a hand-rolled HTTP JSON pipeline gave direct control over retry
behavior, timeout tuning, and request/response logging — all of which
turned out to be load-bearing this session. Getting a real, non-fabricated
LLM-backed multi-agent chain working end-to-end required threading a
`temperature` parameter through the whole call chain, adding bounded retry
with backoff for real API flakiness, extending timeouts to accommodate 6
sequential LLM calls, and adding always-on request/response logging for
auditability (`_log_llm_request`/`_log_llm_response` in `gpcs.py` and both
services' `call_llm`). Doing this against a framework abstraction would
have added a layer to work around rather than through. This decision is
also directly testable by the research itself: the matched-compute
control (`experiments/results/matched_compute_control.md`) found the real
5-specialist architecture does *not* outperform a matched-compute
single-LLM baseline on this benchmark — a finding about whether the
multi-agent structure earns its complexity at all, independent of which
orchestration framework implements it.

## 3. Frontend: planned SPA (React/Vue/Svelte) → static HTML/vanilla JS

**Original plan:** a single-page application built with a modern
JavaScript framework.

**What actually shipped:** static HTML/CSS/vanilla JavaScript
(`services/ui/static`), served directly with no build step. The topology
graph is rendered via hand-built SVG DOM manipulation (`topology.js`), not
a charting or graph-visualization library.

**Why:** the UI's job is to make real backend data (graph state, agent
findings, GPCS scores) visible and clickable — evidence display and
navigation, not client-side application state management. A build-free
static frontend removed an entire toolchain (bundler, framework version
management, build step in CI) for a UI that doesn't need client-side
routing, component state, or reactivity beyond what direct DOM updates
already provide. This is a legitimate scope-reduction, not a shortcut that
compromises what the UI needs to demonstrate.

## What this means for how the repo should be read

None of these three deviations weaken the research contributions
(`research/NOVEL_CONTRIBUTIONS.md`) — GPCS, the self-consistency
comparison, and the neuro-symbolic retrieval ablation are all independent
of which cloud provider, orchestration framework, or frontend stack
implements the surrounding system. They're recorded here so a reviewer
comparing this repo against earlier design docs (`docs/week-1/`,
`research/REPOSITORY_REVIEW.md`) sees engineering decisions with reasons,
not unexplained drift.
