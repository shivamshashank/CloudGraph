"""Tests for LLM agent reasoning, providers, and rule-based fallbacks."""

import importlib.util
import os
import sys
import pytest
import requests

# Load investigation engine main module using absolute spec file location
inv_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../investigation-engine/main.py")
)
inv_spec = importlib.util.spec_from_file_location("investigation_main", inv_path)
investigation_main = importlib.util.module_from_spec(inv_spec)
sys.modules["investigation_main"] = investigation_main
inv_spec.loader.exec_module(investigation_main)

run_monitoring_agent = investigation_main.run_monitoring_agent
run_log_agent = investigation_main.run_log_agent
run_deployment_agent = investigation_main.run_deployment_agent
run_topology_agent = investigation_main.run_topology_agent
run_security_agent = investigation_main.run_security_agent

# Load agent orchestrator main module using absolute spec file location
orch_path = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../agent-orchestrator/main.py")
)
orch_spec = importlib.util.spec_from_file_location("orchestrator_main", orch_path)
orchestrator_main = importlib.util.module_from_spec(orch_spec)
sys.modules["orchestrator_main"] = orchestrator_main
orch_spec.loader.exec_module(orchestrator_main)

ConsensusEngine = orchestrator_main.ConsensusEngine


class MockResponse:
    """Mock HTTP response."""

    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code

    def json(self):
        """Return JSON data."""
        return self.json_data

    def raise_for_status(self):
        """Mock raise_for_status."""
        if self.status_code != 200:
            raise requests.HTTPError("Mock status error")


def test_call_llm_ollama(monkeypatch):
    """Test call_llm against the local Ollama server — the only supported
    provider now that CloudGraph runs entirely on local models."""

    def mock_post_ollama(url, json, timeout=120, **_kwargs):
        assert "/v1/chat/completions" in url
        assert json["model"] == "llama3.1:8b"
        assert timeout == 120
        res_content = '{"finding": "Ollama Success", "confidence": 0.9}'
        return MockResponse({"choices": [{"message": {"content": res_content}}]})

    monkeypatch.setattr(requests, "post", mock_post_ollama)
    res = investigation_main.call_llm(
        prompt="Test prompt",
        provider="ollama",
        model="llama3.1:8b",
    )
    assert res["finding"] == "Ollama Success"
    assert res["confidence"] == 0.9

    # No provider given defaults to "ollama" too.
    monkeypatch.setattr(requests, "post", mock_post_ollama)
    res = investigation_main.call_llm(prompt="Test prompt", model="llama3.1:8b")
    assert res["finding"] == "Ollama Success"


def test_call_llm_unsupported_provider():
    """Verify call_llm rejects any provider other than "ollama" — cloud
    providers were removed entirely, not just left unconfigured."""
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        investigation_main.call_llm(prompt="test", provider="openai")


def test_monitoring_agent_reasoning_and_fallback(monkeypatch):
    """Test run_monitoring_agent reasoning and rule fallback paths."""
    # Mock Neo4j execute_query to return mock metrics records
    mock_metrics = [
        {"name": "pod/cpu/usage_rate", "value": 75.0, "ts": 123},
        {"name": "pod/memory/usage", "value": 85.0, "ts": 123},
    ]
    monkeypatch.setattr(
        investigation_main.neo4j_client,
        "execute_query",
        lambda *args, **kwargs: mock_metrics,
    )

    # Mock _call_llm_agent success
    mock_llm_res = {"finding": "AI detected anomaly", "confidence": 0.95}
    monkeypatch.setattr(
        investigation_main,
        "_call_llm_agent",
        lambda *args, **kwargs: mock_llm_res,
    )

    llm_config = {
        "provider": "ollama",
        "api_key": "test-mock-token",  # gitleaks:allow
        "model": "llama3.1:8b",
    }

    mon_ai = run_monitoring_agent("test-pod", llm_config=llm_config)
    assert mon_ai["finding"] == "AI detected anomaly"
    assert mon_ai["confidence"] == 0.95

    # Mock _call_llm_agent failure (returns None) to trigger fallback rules
    monkeypatch.setattr(
        investigation_main,
        "_call_llm_agent",
        lambda *args, **kwargs: None,
    )

    mon_fallback = run_monitoring_agent("test-pod", llm_config=None)
    assert "metrics are within normal operational limits" in mon_fallback["finding"]


def test_log_agent_reasoning_and_fallback(monkeypatch):
    """Test run_log_agent reasoning and rule fallback paths."""
    monkeypatch.setattr(
        investigation_main.neo4j_client,
        "execute_query",
        lambda *args, **kwargs: [],
    )

    llm_config = {
        "provider": "ollama",
        "api_key": "test-mock-token",  # gitleaks:allow
        "model": "llama3.1:8b",
    }

    # Mock LLM Success
    mock_log_res = {
        "finding": "AI log signature match",
        "confidence": 0.92,
        "category": "oom",
    }
    monkeypatch.setattr(
        investigation_main,
        "_call_llm_agent",
        lambda *args, **kwargs: mock_log_res,
    )
    log_ai = run_log_agent("test-pod", ["error log message"], llm_config=llm_config)
    assert log_ai["finding"] == "AI log signature match"
    assert log_ai["confidence"] == 0.92
    assert log_ai["metadata"]["category"] == "oom"

    # Mock LLM failure -> Fallback
    monkeypatch.setattr(
        investigation_main,
        "_call_llm_agent",
        lambda *args, **kwargs: None,
    )
    log_fallback = run_log_agent(
        "test-pod",
        ["database connection timeout"],
        llm_config=None,
    )
    assert log_fallback["metadata"]["category"] == "network"
    assert log_fallback["confidence"] == 0.92


def test_deployment_agent_reasoning_and_fallback(monkeypatch):
    """Test run_deployment_agent reasoning and rule fallback paths."""
    llm_config = {
        "provider": "ollama",
        "api_key": "test-mock-token",  # gitleaks:allow
        "model": "llama3.1:8b",
    }

    # Mock LLM Success
    mock_dep_res = {
        "finding": "AI deployment anomaly",
        "confidence": 0.88,
    }
    monkeypatch.setattr(
        investigation_main,
        "_call_llm_agent",
        lambda *args, **kwargs: mock_dep_res,
    )
    # Mock Neo4j returning active deployment info
    mock_records = [
        {
            "name": "payment-dep",
            "status": "Progressing",
            "sha": "1a2b3c",
            "commit_msg": "Initial commit",
        }
    ]
    monkeypatch.setattr(
        investigation_main.neo4j_client,
        "execute_query",
        lambda *args, **kwargs: mock_records,
    )
    dep_ai = run_deployment_agent("test-pod", llm_config=llm_config)
    assert dep_ai["finding"] == "AI deployment anomaly"
    assert dep_ai["confidence"] == 0.88

    # Mock LLM failure -> Fallback
    monkeypatch.setattr(
        investigation_main,
        "_call_llm_agent",
        lambda *args, **kwargs: None,
    )
    dep_fallback = run_deployment_agent("test-pod", llm_config=None)
    assert dep_fallback["metadata"]["recent_change"] is True
    assert dep_fallback["confidence"] == 0.85


def test_topology_agent_reasoning_and_fallback(monkeypatch):
    """Test run_topology_agent reasoning and rule fallback paths."""
    llm_config = {
        "provider": "ollama",
        "api_key": "test-mock-token",  # gitleaks:allow
        "model": "llama3.1:8b",
    }

    # Mock LLM Success
    mock_top_res = {
        "finding": "AI topology cascading failure",
        "confidence": 0.91,
    }

    monkeypatch.setattr(
        investigation_main,
        "_call_llm_agent",
        lambda *args, **kwargs: mock_top_res,
    )

    def fake_neo4j_topology(query, _params=None):
        if "noisy_neighbors" in query or "bad_pods" in query:
            return [{"node": "node-1", "bad_pods": ["bad-pod-a", "bad-pod-b"]}]
        return [{"service": "auth-service"}]

    monkeypatch.setattr(
        investigation_main.neo4j_client,
        "execute_query",
        fake_neo4j_topology,
    )

    top_ai = run_topology_agent("test-pod", llm_config=llm_config)
    assert top_ai["finding"] == "AI topology cascading failure"
    assert top_ai["confidence"] == 0.91

    # Mock LLM failure -> Fallback
    monkeypatch.setattr(
        investigation_main,
        "_call_llm_agent",
        lambda *args, **kwargs: None,
    )
    top_fallback = run_topology_agent("test-pod", llm_config=None)
    assert "noisy_neighbors" in top_fallback["metadata"]
    assert top_fallback["confidence"] == 0.86


def test_security_agent_reasoning_and_fallback(monkeypatch):
    """Test run_security_agent reasoning and rule fallback paths."""
    llm_config = {
        "provider": "ollama",
        "api_key": "test-mock-token",  # gitleaks:allow
        "model": "llama3.1:8b",
    }

    # Mock LLM Success
    mock_sec_res = {
        "finding": "AI security leak detected",
        "confidence": 0.96,
        "threat_detected": True,
    }
    monkeypatch.setattr(
        investigation_main,
        "_call_llm_agent",
        lambda *args, **kwargs: mock_sec_res,
    )
    sec_ai = run_security_agent(
        "test-pod",
        ["password leak on stdout"],
        llm_config=llm_config,
    )
    assert sec_ai["finding"] == "AI security leak detected"
    assert sec_ai["confidence"] == 0.96

    # Mock LLM failure -> Fallback
    monkeypatch.setattr(
        investigation_main,
        "_call_llm_agent",
        lambda *args, **kwargs: None,
    )
    sec_fallback = run_security_agent(
        "test-pod",
        ["unauthorized RBAC warning"],
        llm_config=None,
    )
    assert sec_fallback["metadata"]["category"] == "credentials"
    assert sec_fallback["metadata"]["threat_detected"] is True
    assert sec_fallback["confidence"] == 0.94


def test_consensus_engine_reasoning_and_fallback(monkeypatch):
    """Test ConsensusEngine reasoning path and weighted rule fallback path."""

    agents = [
        {
            "name": "monitoring",
            "finding": "CPU usage high",
            "confidence": 0.8,
        },
        {
            "name": "logs",
            "finding": "OOM signature detected",
            "confidence": 0.9,
            "metadata": {"category": "oom"},
        },
        {
            "name": "deployments",
            "finding": "Recent commit deployed",
            "confidence": 0.7,
        },
        {
            "name": "topology",
            "finding": "Cascading network issues",
            "confidence": 0.6,
        },
        {
            "name": "security",
            "finding": "No threats detected",
            "confidence": 0.8,
        },
    ]

    # 1. Test LLM-based Consensus resolution
    mock_orchestrator_llm = {
        "title": "Out of memory on billing-pod",
        "summary": "OOM limits exceeded due to payload leak",
        "cause": "Observed container restart with Exit Code 137",
        "recommendation": "Increase deployment memory limits",
        "severity": "CRITICAL",
        "confidence": 0.94,
        "evidence": ["Billing service exceeded 512Mi allocation limit"],
    }

    monkeypatch.setattr(
        orchestrator_main,
        "call_llm",
        lambda *args, **kwargs: mock_orchestrator_llm,
    )

    res_ai = ConsensusEngine.resolve_incident(
        agents=agents,
        pod_name="billing-pod",
        pod_status="CrashLoopBackOff",
        llm_config={
            "provider": "ollama",
            "api_key": "test-mock-token",  # gitleaks:allow
            "model": "llama3.1:8b",
        },
    )

    assert res_ai["title"] == "Out of memory on billing-pod"
    assert res_ai["severity"] == "CRITICAL"
    assert "Consensus Engine confidence: 94%" in res_ai["evidence"]

    # 2. Test Rule-based Fallback consensus
    # Trigger exception on call_llm to force fallback path
    def raise_err(*args, **kwargs):
        raise ValueError("LLM Error")

    monkeypatch.setattr(orchestrator_main, "call_llm", raise_err)

    res_fallback = ConsensusEngine.resolve_incident(
        agents=agents,
        pod_name="billing-pod",
        pod_status="CrashLoopBackOff",
        llm_config=None,
    )

    assert "Out of memory" in res_fallback["title"]
    assert res_fallback["severity"] == "CRITICAL"
    # Weighted consensus score calculation:
    # monitoring: 0.8 * 0.2 = 0.16
    # logs: 0.9 * 0.3 = 0.27
    # deployments: 0.7 * 0.2 = 0.14
    # topology: 0.6 * 0.15 = 0.09
    # security: 0.8 * 0.15 = 0.12
    # Total confidence = 0.16 + 0.27 + 0.14 + 0.09 + 0.12 = 0.78
    assert res_fallback["evidence"][0] == "Consensus Engine confidence: 78%"
