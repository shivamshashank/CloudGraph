"""Guards for benchmark scenario loading.

The pipeline reads every scenario through `load_scenarios`, so two
properties have to hold: the scenarios carry every field the pipeline
touches, and a missing dataset fails loudly rather than quietly
producing a run over nothing.
"""

import pytest

from app.demo import datasets
from app.demo.datasets import (
    DEFAULT_INCIDENT_TIME,
    load_scenarios,
    scenario_incident_time,
)

# Fields consumed somewhere in the pipeline (seeding.py, evaluation.py,
# report_runner.py, self_consistency.py).
PIPELINE_FIELDS = {
    "id",
    "query",
    "target_service",
    "target_entity",
    "expected_tags",
    "observed_symptoms",
    "ground_truth_claims",
}


def test_missing_data_raises_rather_than_returning_empty(monkeypatch):
    """An ungenerated dataset must stop the run. Returning [] would let a
    report complete over zero scenarios and look like a valid result."""
    monkeypatch.setattr(datasets, "load_rcaeval_scenarios", lambda: [])
    with pytest.raises(RuntimeError, match="have not been generated"):
        load_scenarios()


def test_scenarios_carry_every_field_the_pipeline_reads():
    """A missing field would surface as a KeyError mid-run, after the
    scenario had already been seeded and LLM calls spent on it."""
    scenarios = load_scenarios()
    assert scenarios
    for scenario in scenarios:
        missing = PIPELINE_FIELDS - set(scenario)
        assert not missing, f"{scenario.get('id')} missing {missing}"
        assert scenario["observed_symptoms"], scenario["id"]
        assert scenario["ground_truth_claims"], scenario["id"]


def test_scenario_ids_are_unique():
    """Duplicate IDs would silently collide when results are joined by
    scenario_id during analysis."""
    ids = [s["id"] for s in load_scenarios()]
    assert len(ids) == len(set(ids))


def test_every_scenario_has_a_real_injection_time():
    """RCAEval cases all record when the fault was injected. Falling back
    to the constant would mean seeded evidence ages were fabricated."""
    for scenario in load_scenarios():
        assert scenario.get("inject_time"), scenario["id"]
        assert scenario_incident_time(scenario) != DEFAULT_INCIDENT_TIME


def test_incident_time_falls_back_for_scenarios_without_one():
    """The fallback must stay fixed so seeding and retrieval agree."""
    assert scenario_incident_time({"id": "x"}) == DEFAULT_INCIDENT_TIME
