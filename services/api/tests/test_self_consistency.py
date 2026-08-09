"""Unit tests for the self-consistency hallucination baseline."""

import types

import pytest
import requests

from app.database.neo4j_client import neo4j_client
from app.research.self_consistency import (
    SelfConsistencyUnavailableError,
    _build_single_llm_prompt,
    generate_and_score,
)

SCENARIO = {
    "id": "scenario-01",
    "target_entity": "payment-service-pod-7f",
    "observed_symptoms": [
        "kubectl describe pod payment-service-pod-7f: Last State: "
        "Terminated, Reason: OOMKilled, Exit Code: 137"
    ],
    "ground_truth_claims": ["Pod payment-service failed due to OOMKilled"],
}


@pytest.fixture(autouse=True)
def mock_neo4j_queries(monkeypatch):
    """Mock Neo4j globally for this file — load_stored_llm_settings() hits
    it on every _generate_one_sample call, and these tests must not depend
    on live infrastructure."""
    monkeypatch.setattr(neo4j_client, "execute_query", lambda *args, **kwargs: [])


def _fake_response(payload, status_code=200):
    """Stand-in for requests.Response, exposing only the .json() this
    module's HTTP calls actually use."""
    return types.SimpleNamespace(status_code=status_code, json=lambda: payload)


def _llm_consensus(summary: str, cause: str) -> dict:
    return {
        "status": "success",
        "service": "agent-orchestrator",
        "consensus": {
            "title": "",
            "summary": summary,
            "cause": cause,
            "recommendation": "Investigate further.",
            "severity": "CRITICAL",
            "evidence": [],
            "agents": [],
            "generation_source": "llm",
        },
    }


def test_generate_and_score_distinguishes_recurring_from_novel_claims(monkeypatch):
    """A claim repeated verbatim across generations should be supported; a
    claim that appears in only one generation, on an unrelated topic to the
    other two, should be flagged unsupported."""

    oom_summary = (
        "The container was terminated by the OOM killer process unexpectedly today."
    )
    responses = [
        _llm_consensus(
            oom_summary,
            "The service silently enabled an unrelated deprecated debug "
            "flag causing this specific noise.",
        ),
        _llm_consensus(
            oom_summary,
            "A completely unrelated network partition caused intermittent "
            "packet loss during the incident.",
        ),
        _llm_consensus(
            oom_summary,
            "Disk pressure on the underlying node triggered eviction of "
            "several unrelated pods nearby.",
        ),
    ]
    call_count = {"n": 0}

    def _fake_post(*_args, **_kwargs):
        payload = responses[call_count["n"]]
        call_count["n"] += 1
        return _fake_response(payload)

    monkeypatch.setattr("app.research.self_consistency.requests.post", _fake_post)

    result = generate_and_score(SCENARIO, n_samples=3, temperature=0.8)

    assert result["n_samples"] == 3
    assert result["claim_count"] >= 2
    assert result["unsupported_claim_rate"] is not None

    by_text = {c["text"]: c for c in result["claims"]}
    oom_claim = next(c for text, c in by_text.items() if "OOM killer" in text)
    debug_flag_claim = next(c for text, c in by_text.items() if "debug flag" in text)

    assert oom_claim["unsupported"] is False
    assert oom_claim["recurrence_count"] == 2
    assert debug_flag_claim["unsupported"] is True
    assert debug_flag_claim["recurrence_count"] == 0


def test_generate_and_score_rejects_rule_based_fallback(monkeypatch):
    """Self-consistency must refuse to run on the deterministic rule-based
    fallback path — every claim would trivially recur, which is not a
    measurement of anything."""

    def _fake_post(*_args, **_kwargs):
        return _fake_response(
            {
                "status": "success",
                "consensus": {
                    "title": "x",
                    "summary": "x",
                    "cause": "x",
                    "generation_source": "rule_based_fallback",
                },
            }
        )

    monkeypatch.setattr("app.research.self_consistency.requests.post", _fake_post)

    with pytest.raises(SelfConsistencyUnavailableError, match="rule-based fallback"):
        generate_and_score(SCENARIO, n_samples=3, temperature=0.8)


def test_generate_and_score_raises_when_orchestrator_unreachable(monkeypatch):
    """Self-consistency must surface a clear exclusion reason, not crash,
    when the agent-orchestrator itself is unreachable."""

    def _raise_connection_error(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError("mock: connection refused")

    monkeypatch.setattr(
        "app.research.self_consistency.requests.post", _raise_connection_error
    )

    with pytest.raises(SelfConsistencyUnavailableError, match="unreachable"):
        generate_and_score(SCENARIO, n_samples=3, temperature=0.8)


def test_generate_and_score_requires_at_least_two_samples():
    """Self-consistency is undefined with fewer than 2 samples to compare."""
    with pytest.raises(ValueError):
        generate_and_score(SCENARIO, n_samples=1, temperature=0.8)


def test_matched_compute_prompt_uses_observed_symptoms_not_ground_truth():
    """Regression guard for the exact leakage bug this pipeline had: the
    matched-compute control's single-LLM prompt must be built from
    observed_symptoms, never from ground_truth_claims — the latter is the
    held-out answer key and must never reach a generation call."""
    scenario = {
        "target_entity": "payment-service-pod-7f",
        "observed_symptoms": ["kubectl describe pod: Reason: OOMKilled"],
        "ground_truth_claims": ["Pod payment-service failed due to OOMKilled"],
    }
    prompt, _system_prompt = _build_single_llm_prompt(scenario, retrieval_text="")

    assert "OOMKilled" in prompt  # the observed symptom itself is expected
    assert scenario["ground_truth_claims"][0] not in prompt
