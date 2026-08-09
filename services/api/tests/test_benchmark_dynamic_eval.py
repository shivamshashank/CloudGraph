"""Unit tests for the ground-truth dataset and dynamic benchmark evaluation engine."""

import types

import pytest
import requests
from fastapi.testclient import TestClient

from app.main import app
from app.database.neo4j_client import neo4j_client
from app.demo.datasets import load_scenarios
from app.research.evaluation import evaluate_scenario

client = TestClient(app)


def _fake_orchestrator_response(payload, status_code=200):
    """Stand-in for requests.Response, used to mock the agent-orchestrator
    HTTP boundary only — evaluate_scenario's own logic runs unmodified. A
    plain factory function rather than a class, since only .status_code and
    .json() are ever read off the result."""
    return types.SimpleNamespace(status_code=status_code, json=lambda: payload)


def _fake_orchestrator_post(*_args, **_kwargs):
    return _fake_orchestrator_response(
        {
            "status": "success",
            "consensus": {
                "title": "Mock RCA",
                "summary": "Mocked orchestrator consensus for unit testing.",
                "cause": "Simulated root cause for unit test.",
                "recommendation": "Investigate further.",
                "severity": "CRITICAL",
                "evidence": ["mock evidence line"],
            },
        }
    )


@pytest.fixture(autouse=True)
def mock_neo4j_queries(monkeypatch):
    """Mock out Neo4j database calls globally for this file."""
    monkeypatch.setattr(neo4j_client, "execute_query", lambda *args, **kwargs: [])


@pytest.fixture(autouse=True)
def mock_agent_orchestrator(monkeypatch):
    """Mock the live agent-orchestrator HTTP call at the network boundary so
    'Agents' tiers can be exercised without a running orchestrator process.
    evaluate_scenario must never fall back to fabricated ground-truth data
    on its own — that contract is what individual tests below verify by
    overriding this default (successful) mock where needed."""
    monkeypatch.setattr(
        "app.research.evaluation.requests.post", _fake_orchestrator_post
    )


def test_benchmark_ground_truth_dataset_structure():
    """Every scenario must carry the fields the pipeline reads.

    Leakage separation is covered in tests/test_rcaeval_dataset.py,
    which owns the generated dataset's invariants."""
    assert len(load_scenarios()) == 36

    required_keys = {
        "id",
        "query",
        "target_service",
        "target_entity",
        "root_cause",
        "expected_tags",
        "observed_symptoms",
        "ground_truth_claims",
    }

    for scenario in load_scenarios():
        assert required_keys.issubset(scenario.keys())
        assert isinstance(scenario["expected_tags"], list)
        assert len(scenario["expected_tags"]) > 0
        assert isinstance(scenario["observed_symptoms"], list)
        assert len(scenario["observed_symptoms"]) > 0
        assert isinstance(scenario["ground_truth_claims"], list)
        assert len(scenario["ground_truth_claims"]) > 0


def test_evaluate_scenario_calculates_valid_metrics():
    """Verify evaluation logic on a ground-truth scenario."""
    scenario = load_scenarios()[0]

    # Keyword Search generates no text/claims, so hallucination rate is
    # undefined (None / N/A), not a fabricated number.
    tp_kw, fp_kw, fn_kw, correct_kw, unsupp_kw = evaluate_scenario(
        scenario, "Keyword Search"
    )
    assert tp_kw >= 0
    assert fp_kw >= 0
    assert fn_kw >= 0
    assert correct_kw in {0, 1}
    assert unsupp_kw is None

    # Full GPCS Search: real orchestrator call (mocked at the HTTP boundary
    # only) + real GCP propagation + real GPCS claim scoring.
    result = evaluate_scenario(scenario, "GraphRAG + Agents + GCP + GPCS")
    assert result is not None
    tp_gpcs, fp_gpcs, fn_gpcs, correct_gpcs, unsupp_gpcs = result
    assert tp_gpcs >= 0
    assert fp_gpcs >= 0
    assert fn_gpcs >= 0
    assert correct_gpcs in {0, 1}
    # GPCS scoring can itself fail open (returns None) in edge cases, but
    # when it succeeds the rate must be a real non-negative measurement.
    assert unsupp_gpcs is None or unsupp_gpcs >= 0.0


def test_evaluate_scenario_excludes_when_orchestrator_unreachable(monkeypatch):
    """An 'Agents' baseline must be excluded (return None), never fall back
    to fabricating a result from the scenario's own ground truth, when the
    agent-orchestrator cannot be reached."""

    def _raise_connection_error(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError("mock: connection refused")

    monkeypatch.setattr(
        "app.research.evaluation.requests.post", _raise_connection_error
    )

    scenario = load_scenarios()[0]
    result = evaluate_scenario(scenario, "GraphRAG + Agents")
    assert result is None


def test_evaluate_scenario_excludes_on_non_200_orchestrator_response(monkeypatch):
    """A non-200 orchestrator response must also exclude the result rather
    than silently substitute fabricated data."""
    monkeypatch.setattr(
        "app.research.evaluation.requests.post",
        lambda *a, **k: _fake_orchestrator_response({}, status_code=500),
    )

    scenario = load_scenarios()[0]
    result = evaluate_scenario(scenario, "GraphRAG + Agents + GCP")
    assert result is None


def test_run_benchmark_endpoint_updates_state_and_logs():
    """Verify POST /api/v1/benchmark/run computes dynamic metrics and logs."""
    response = client.post("/api/v1/benchmark/run")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "success"
    assert body["has_run"] is True
    assert body["last_run_timestamp"] is not None
    assert "CloudGraph incident benchmark v1" in body["dataset"]
    assert isinstance(body["baselines"], list)
    assert len(body["baselines"]) == 6
    assert isinstance(body["logs"], list)
    assert len(body["logs"]) >= 6

    # Verify execution logs contain calculation step details
    log_text = " ".join(body["logs"])
    assert "Processing scenario: rcaeval-01" in log_text
    assert "Tearing down scenario" in log_text
    assert "Dynamic evaluation engine completed" in log_text


def test_benchmark_reset_endpoint_clears_state():
    """Verify POST /api/v1/benchmark/reset resets benchmark state to unexecuted."""
    client.post("/api/v1/benchmark/run")
    summary_before = client.get("/api/v1/benchmark/summary").json()
    assert summary_before["has_run"] is True

    reset_res = client.post("/api/v1/benchmark/reset")
    assert reset_res.status_code == 200
    assert reset_res.json()["has_run"] is False

    summary_after = client.get("/api/v1/benchmark/summary").json()
    assert summary_after["has_run"] is False
    assert summary_after["baselines"] == []


def test_benchmark_export_endpoint_returns_json_and_csv():
    """Verify GET /api/v1/benchmark/export exports JSON and CSV metrics."""
    client.post("/api/v1/benchmark/run")

    json_res = client.get("/api/v1/benchmark/export?format=json")
    assert json_res.status_code == 200
    assert json_res.json()["status"] == "success"
    assert len(json_res.json()["baselines"]) == 6

    csv_res = client.get("/api/v1/benchmark/export?format=csv")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers["content-type"]
    assert (
        "baseline,accuracy,precision,recall,f1,hallucination_rate,latency_ms"
        in csv_res.text
    )
    assert "GraphRAG + Agents + GCP + GPCS" in csv_text_lines(csv_res.text)


def csv_text_lines(text: str) -> str:
    """Helper to return csv text."""
    return text
