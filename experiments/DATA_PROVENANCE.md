# Data Provenance — RCAEval RE2 Benchmark Subset

Records exactly where CloudGraph's evaluation data came from, so any
result computed from it can be traced to its source and regenerated.
Written because the alternative — "we used 36 real incidents" with no
audit trail — is not a reproducible claim.

## Source

| | |
|---|---|
| Dataset | **RCAEval** — A Benchmark for Root Cause Analysis of Microservice Systems with Telemetry Data |
| Authors | Luan Pham, Hongyu Zhang, Huong Ha, Flora Salim, Xiuzhen Zhang |
| Published | FSE 2026, WWW 2025 (Companion), ASE 2024 |
| arXiv | [2412.17015](https://arxiv.org/abs/2412.17015) |
| DOI | [10.5281/zenodo.14590730](https://doi.org/10.5281/zenodo.14590730) |
| Code | <https://github.com/phamquiluan/RCAEval> |
| Data | <https://huggingface.co/datasets/phamquiluan/RCAEval> |
| Licence | **MIT** — covers both the code and the authors' own datasets |
| Suite used | **RE2** (270 cases; metrics + logs + traces) |
| Retrieved | 2026-08-09 |

RE2 was chosen over RE1 and RE3 deliberately. RE1 ships metrics only,
with no logs — and GPCS scores claims by semantic search over *text*
evidence, so a metrics-only suite would starve the exact mechanism under
study. RE3 covers code-level faults (F1–F5), a different fault family
from RE2's resource/network faults; it is a candidate for a follow-up
experiment broadening fault coverage, not a substitute here.

## How the cases were produced (upstream)

The RCAEval authors deployed three open-source microservice systems to
Kubernetes clusters and injected faults with chaos tooling, capturing
telemetry through the incident window:

- Metrics via Prometheus / cAdvisor / Istio
- Logs via Vector and Loki
- Traces via Jaeger

Every case therefore records a fault that actually occurred in a running
system. This is the property the authored benchmark could not provide,
and the reason it was retired (see `dissertation/PROGRESS.md`, Week 9).

## Selection

36 cases, chosen by `scripts/build_rcaeval_dataset.py` — deterministic,
not randomly sampled, so the same selection reproduces exactly:

1. Cases missing any required file are excluded up front. Upstream ships
   one incomplete RE2 case (`re2tt_ts-auth-service_cpu_1`, no
   `logs.parquet`); excluding it before selection keeps the subset full
   and balanced rather than 35 cases with a hole.
2. Remaining cases are bucketed into (system × fault-type) cells — 3
   systems × 6 fault types = 18 cells.
3. Cells are visited in a fixed order, taking the lowest-numbered unused
   instance from each. At 36 cases this is exactly **2 per cell**, so
   both axes come out perfectly balanced with no tie-breaking needed.

Resulting distribution:

| Axis | Distribution | Spread |
|---|---|---|
| System | Online Boutique 12, Sock Shop 12, Train Ticket 12 | **0** |
| Fault type | cpu 6, memory 6, disk 6, delay 6, loss 6, socket 6 | **0** |
| Distinct services | 7 | — |
| Injection times | 2024-01-15 21:36 UTC – 2024-01-25 16:08 UTC | — |

## What was derived, and how

Each case is converted into CloudGraph's scenario shape. Two fields
matter for evaluation integrity and must never be conflated:

- **`observed_symptoms`** — the system's *input*. Built only from raw
  telemetry: metric before/after means across the 12 minutes either side
  of `inject_time`, plus real container log lines from the injection
  window. Metric observations are emitted for **every service in the
  system**, never filtered to the faulted one — filtering would be
  leakage by selection, since choosing what to show is itself the answer.
  Cases average ~8 distinct services per set of observations.
- **`ground_truth_claims`** — *held out*, used only to score extracted
  claims after generation. Derived from RCAEval's own root-cause service
  and fault-type label. Never seeded as evidence, never placed in a
  prompt.

Enforced automatically by `tests/test_rcaeval_dataset.py` and
`tests/test_evaluation_integrity.py`.

### Redaction

One transformation is applied to the raw log text: JWTs and UUIDs are
replaced with `<JWT_REDACTED>` / `<UUID_REDACTED>` (89 substitutions
across the 36 cases). Train Ticket's `TokenServiceImpl` logs issued
session tokens, and while these come from a public demo system rather
than real users, credential-shaped strings should not be committed into
this repository. The log line and its structure are preserved — that a
token was issued is the observable signal; the token body carries no
information about a resource or network fault.

## Task shape (a scoping choice, stated so it is not over-claimed)

RCAEval's label identifies *which service* was faulted. The adapter sets
`target_entity` to that service, so the system is told which entity is
affected and must diagnose **why**. This benchmark therefore measures
fault-type diagnosis, **not** root-cause service localisation — that
would require seeding a downstream symptom entity instead. Results must
not be described as "the system found the culprit service."

## Coverage limitation

RE2 covers six fault types, all resource or network: CPU, memory, disk,
network delay, packet loss, socket exhaustion. It contains no config
errors, security events, deployment failures, DNS faults, or certificate
expiry. Claims from this benchmark are scoped to **resource and network
faults in microservice systems**, not Kubernetes incidents in general.

## Reproducing

```bash
cd services/api
.venv/bin/python scripts/build_rcaeval_dataset.py --n-cases 36
```

Raw parquet (~65MB) downloads to `experiments/rcaeval_data/` and is
gitignored — it is third-party data with an upstream home. The derived
scenarios are tracked, so the benchmark is reproducible without
vendoring the source corpus.

| Artifact | Status |
|---|---|
| `services/api/app/demo/rcaeval_dataset_generated.json` | tracked |
| `experiments/rcaeval_data/` (raw parquet) | gitignored, regenerate on demand |

Generated file SHA-256 (of the committed artifact; regenerate and
re-hash if the build script changes, since formatting hooks can alter
the file after generation):

```text
37a527d6558943211a847d0034a3bb71343fecfc86c91be5486fc2678fd53ed3
```

## Citation

```bibtex
@inproceedings{pham2025rcaeval,
  title     = {{RCAEval}: A Benchmark for Root Cause Analysis of
               Microservice Systems with Telemetry Data},
  author    = {Pham, Luan and Zhang, Hongyu and Ha, Huong and
               Salim, Flora and Zhang, Xiuzhen},
  booktitle = {Companion Proceedings of the ACM Web Conference},
  year      = {2025},
  doi       = {10.1145/3701716.3715290}
}
```

## Selected cases

| Scenario | RCAEval case | System | Faulted service | Fault | Inject time (Unix) |
|---|---|---|---|---|---|
| rcaeval-01 | `re2ob_checkoutservice_cpu_1` | Online Boutique | checkoutservice | cpu_exhaustion | 1705354566 |
| rcaeval-02 | `re2ss_carts_cpu_1` | Sock Shop | carts | cpu_exhaustion | 1705596179 |
| rcaeval-03 | `re2tt_ts-order-service_cpu_1` | Train Ticket | ts-order-service | cpu_exhaustion | 1705935125 |
| rcaeval-04 | `re2ob_checkoutservice_delay_1` | Online Boutique | checkoutservice | network_delay | 1705666511 |
| rcaeval-05 | `re2ss_carts_delay_1` | Sock Shop | carts | network_delay | 1705662624 |
| rcaeval-06 | `re2tt_ts-auth-service_delay_1` | Train Ticket | ts-auth-service | network_delay | 1705921865 |
| rcaeval-07 | `re2ob_checkoutservice_disk_1` | Online Boutique | checkoutservice | disk_saturation | 1705373910 |
| rcaeval-08 | `re2ss_carts_disk_1` | Sock Shop | carts | disk_saturation | 1705817948 |
| rcaeval-09 | `re2tt_ts-auth-service_disk_1` | Train Ticket | ts-auth-service | disk_saturation | 1705980016 |
| rcaeval-10 | `re2ob_checkoutservice_loss_1` | Online Boutique | checkoutservice | packet_loss | 1705376266 |
| rcaeval-11 | `re2ss_carts_loss_1` | Sock Shop | carts | packet_loss | 1705664209 |
| rcaeval-12 | `re2tt_ts-auth-service_loss_1` | Train Ticket | ts-auth-service | packet_loss | 1705983003 |
| rcaeval-13 | `re2ob_checkoutservice_mem_1` | Online Boutique | checkoutservice | memory_exhaustion | 1705462070 |
| rcaeval-14 | `re2ss_carts_mem_1` | Sock Shop | carts | memory_exhaustion | 1705845578 |
| rcaeval-15 | `re2tt_ts-auth-service_mem_1` | Train Ticket | ts-auth-service | memory_exhaustion | 1706026700 |
| rcaeval-16 | `re2ob_checkoutservice_socket_1` | Online Boutique | checkoutservice | socket_exhaustion | 1705656313 |
| rcaeval-17 | `re2ss_carts_socket_1` | Sock Shop | carts | socket_exhaustion | 1705632937 |
| rcaeval-18 | `re2tt_ts-auth-service_socket_1` | Train Ticket | ts-auth-service | socket_exhaustion | 1705981508 |
| rcaeval-19 | `re2ob_currencyservice_cpu_1` | Online Boutique | currencyservice | cpu_exhaustion | 1705682817 |
| rcaeval-20 | `re2ss_catalogue_cpu_1` | Sock Shop | catalogue | cpu_exhaustion | 1705600751 |
| rcaeval-21 | `re2tt_ts-route-service_cpu_1` | Train Ticket | ts-route-service | cpu_exhaustion | 1705938117 |
| rcaeval-22 | `re2ob_currencyservice_delay_1` | Online Boutique | currencyservice | network_delay | 1705702012 |
| rcaeval-23 | `re2ss_catalogue_delay_1` | Sock Shop | catalogue | network_delay | 1705640134 |
| rcaeval-24 | `re2tt_ts-order-service_delay_1` | Train Ticket | ts-order-service | network_delay | 1705952245 |
| rcaeval-25 | `re2ob_currencyservice_disk_1` | Online Boutique | currencyservice | disk_saturation | 1705386669 |
| rcaeval-26 | `re2ss_catalogue_disk_1` | Sock Shop | catalogue | disk_saturation | 1705636944 |
| rcaeval-27 | `re2tt_ts-order-service_disk_1` | Train Ticket | ts-order-service | disk_saturation | 1705985281 |
| rcaeval-28 | `re2ob_currencyservice_loss_1` | Online Boutique | currencyservice | packet_loss | 1705388941 |
| rcaeval-29 | `re2ss_catalogue_loss_1` | Sock Shop | catalogue | packet_loss | 1705602312 |
| rcaeval-30 | `re2tt_ts-order-service_loss_1` | Train Ticket | ts-order-service | packet_loss | 1705988266 |
| rcaeval-31 | `re2ob_currencyservice_mem_1` | Online Boutique | currencyservice | memory_exhaustion | 1705464519 |
| rcaeval-32 | `re2ss_catalogue_mem_1` | Sock Shop | catalogue | memory_exhaustion | 1705819416 |
| rcaeval-33 | `re2tt_ts-order-service_mem_1` | Train Ticket | ts-order-service | memory_exhaustion | 1706198902 |
| rcaeval-34 | `re2ob_currencyservice_socket_1` | Online Boutique | currencyservice | socket_exhaustion | 1705479661 |
| rcaeval-35 | `re2ss_catalogue_socket_1` | Sock Shop | catalogue | socket_exhaustion | 1705638535 |
| rcaeval-36 | `re2tt_ts-order-service_socket_1` | Train Ticket | ts-order-service | socket_exhaustion | 1705986772 |
