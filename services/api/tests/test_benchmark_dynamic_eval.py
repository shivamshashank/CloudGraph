"""Unit tests for the ground-truth dataset and dynamic benchmark evaluation engine."""

from fastapi.testclient import TestClient

from app.main import app
from app.demo.benchmark_dataset import BENCHMARK_GROUND_TRUTH_SCENARIOS
from app.routers.benchmark import (
    evaluate_baseline_dynamically,
)

client = TestClient(app)


def test_benchmark_ground_truth_dataset_structure():
    """Verify that ground-truth dataset scenarios contain all required fields."""
    assert len(BENCHMARK_GROUND_TRUTH_SCENARIOS) == 10

    required_keys = {
        "id",
        "query",
        "target_service",
        "target_entity",
        "root_cause",
        "expected_tags",
        "ground_truth_claims",
    }

    for scenario in BENCHMARK_GROUND_TRUTH_SCENARIOS:
        assert required_keys.issubset(scenario.keys())
        assert isinstance(scenario["expected_tags"], list)
        assert len(scenario["expected_tags"]) > 0
        assert isinstance(scenario["ground_truth_claims"], list)
        assert len(scenario["ground_truth_claims"]) > 0


def test_evaluate_baseline_dynamically_calculates_valid_metrics():
    """Verify dynamic evaluation formula calculations across baseline tiers."""
    scenarios = BENCHMARK_GROUND_TRUTH_SCENARIOS

    kw_res = evaluate_baseline_dynamically("Keyword Search", scenarios)
    gpcs_res = evaluate_baseline_dynamically(
        "GraphRAG + Agents + GCP + GPCS", scenarios
    )

    for res in [kw_res, gpcs_res]:
        assert "baseline" in res
        assert 0.0 <= res["accuracy"] <= 1.0
        assert 0.0 <= res["precision"] <= 1.0
        assert 0.0 <= res["recall"] <= 1.0
        assert 0.0 <= res["f1"] <= 1.0
        assert 0.0 <= res["hallucination_rate"] <= 1.0
        assert res["latency"] > 0
        assert res["tp"] >= 0
        assert res["fp"] >= 0
        assert res["fn"] >= 0

    # GPCS tier should have higher accuracy and lower hallucination rate
    # than raw keyword search
    assert gpcs_res["accuracy"] >= kw_res["accuracy"]
    assert gpcs_res["hallucination_rate"] < kw_res["hallucination_rate"]


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
    assert "[1/6]" in log_text
    assert "[6/6]" in log_text
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
