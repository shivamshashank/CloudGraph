"""Benchmark scenario access for the evaluation pipeline.

CloudGraph evaluates on **real telemetry only**: scenarios derived from
chaos-injected failures in the RCAEval RE2 benchmark, where each case is
a fault that actually occurred in a running Kubernetes system (see
`rcaeval_dataset.py` and `experiments/DATA_PROVENANCE.md`).

An earlier hand-authored benchmark was retired. Its incidents were
written rather than observed, so no result computed on it could speak to
whether the system handles real telemetry — and its inputs had to be
authored too, which is how a ground-truth leak got in unnoticed (see
`dissertation/PROGRESS.md`, Week 9). Keeping it around would have
invited accidental use; git history retains it if it is ever needed.

This module stays as the single access point rather than having callers
import the dataset directly, so the "where do scenarios come from"
decision lives in one place if a second real dataset is added later
(RCAEval RE3 covers code-level faults and is the obvious candidate).
"""

from typing import Any, Dict, List

from app.demo.rcaeval_dataset import load_rcaeval_scenarios

# Reference timestamp for scenarios that carry no real injection time.
# Every RCAEval case does carry one, so this is a defensive fallback
# rather than a normal path.
DEFAULT_INCIDENT_TIME = 1_600_000_000


def scenario_incident_time(scenario: Dict[str, Any]) -> int:
    """Return the reference timestamp for a scenario's incident.

    Seeding and retrieval must derive this the same way: the hybrid
    ranker scores evidence recency as
    ``exp(-ln2 * (reference - timestamp) / half_life)``, so if the two
    disagree the recency term degenerates — identical values make it a
    constant (no discriminative power at all), and a wall-clock reference
    against seeded timestamps drives every candidate to zero.
    """
    return int(scenario.get("inject_time") or DEFAULT_INCIDENT_TIME)


def load_scenarios() -> List[Dict[str, Any]]:
    """Return the benchmark scenarios.

    Raises if the scenarios have not been generated yet rather than
    returning an empty list, so a run fails loudly instead of silently
    reporting results over zero scenarios.
    """
    scenarios = load_rcaeval_scenarios()
    if not scenarios:
        raise RuntimeError(
            "RCAEval scenarios have not been generated. Run:\n"
            "  .venv/bin/python scripts/build_rcaeval_dataset.py --n-cases 36"
        )
    return scenarios
