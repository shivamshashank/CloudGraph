"""Unit tests for the Graph-Provenance Claim Scoring module."""

from unittest.mock import MagicMock

from app.research.gpcs import GraphProvenanceClaimScorer
from app.schemas import GraphRAGSearchPayload


def test_extract_claims_uses_llm_when_available(monkeypatch):
    """Verify claim extraction uses LLM when available."""
    mocked_response = [
        {
            "claim_id": "claim-1",
            "text": "The checkout pod failed due to a database timeout.",
            "claim_type": "state",
        },
        {
            "claim_id": "claim-2",
            "text": "The checkout service depends on payment-service.",
            "claim_type": "entity_relationship",
        },
    ]
    monkeypatch.setattr(
        "app.research.gpcs.call_llm",
        lambda prompt, system_prompt, **_kwargs: mocked_response,
    )

    scorer = GraphProvenanceClaimScorer()
    analysis = {
        "title": "Checkout pipeline failure",
        "summary": "The checkout pod repeatedly failed because the database timed out.",
        "cause": "Service dependency payment-service was unreachable.",
    }

    claims = scorer.extract_claims(analysis)

    assert len(claims) == 2
    assert claims[0]["id"] == "claim-1"
    assert "database timeout" in claims[0]["text"].lower()
    assert claims[1]["type"] == "entity_relationship"


def test_extract_claims_falls_back_to_sentence_splitting(monkeypatch):
    """Verify claim extraction falls back to sentence splitting on LLM failure."""
    monkeypatch.setattr(
        "app.research.gpcs.call_llm", lambda prompt, system_prompt, **_kwargs: None
    )

    scorer = GraphProvenanceClaimScorer()
    analysis = {
        "title": "Checkout pipeline failure",
        "summary": (
            "The checkout pod failed. "
            "The payment-service dependency was unavailable."
        ),
        "cause": "Timeout errors were thrown in the database layer.",
    }

    claims = scorer.extract_claims(analysis)

    assert len(claims) >= 2
    assert any("checkout pod failed" in claim["text"].lower() for claim in claims)
    assert any(
        "payment-service dependency" in claim["text"].lower() for claim in claims
    )


def test_extract_entities_keeps_full_identifier_suffix():
    """Verify entity extraction captures the full resource name, not just
    up through "pod"/"service"/"deployment" — a truncated name (dropping
    e.g. "-7f" or "-deploy") silently fails graph_traversal_retriever's
    exact-match lookup, which was the real cause of GPCS's trust_score
    being hard-zero for ~98% of claims in a real report run."""
    scorer = GraphProvenanceClaimScorer()

    assert scorer.extract_entities("Pod payment-service-pod-7f is in Failed state") == [
        "payment-service-pod-7f"
    ]
    assert scorer.extract_entities(
        "Deployment payment-service-deploy is in Degraded status"
    ) == ["payment-service-deploy"]
    assert scorer.extract_entities("Pod 'api-gateway-service' is in Failed state") == [
        "api-gateway-service"
    ]


def test_extract_entities_matches_node_identifiers():
    """A Node identifier like "node-worker-01" starts with the keyword
    itself, so a leading class requiring at least one prefix char never
    matched it — this silently dropped every claim about a worker node
    (noisy-neighbor, node-level contention, topology) from ever
    attempting evidence retrieval at all. Also verify bare "node"/"pod"
    with no identifier suffix isn't returned as a candidate entity."""
    scorer = GraphProvenanceClaimScorer()

    assert scorer.extract_entities(
        "payment-service-pod-7f is co-located on node-worker-01 with payment-ingress"
    ) == ["payment-service-pod-7f", "node-worker-01"]
    assert scorer.extract_entities(
        "TOPOLOGY Agent confirms the pod is isolated on node 'node-worker-01'"
    ) == ["node-worker-01"]


def test_score_claims_returns_expected_structure(monkeypatch):
    """Verify claim scoring returns expected schema and results."""
    fake_search_results = {
        "results": [
            {
                "id": "pod-1",
                "label": "pod",
                "type": "pod",
                "name": "checkout-pod",
                "score": 0.85,
                "hop_distance": 1,
                "sources": ["graph"],
            }
        ]
    }

    def fake_search(_payload: GraphRAGSearchPayload, _method: str | None = None):
        return fake_search_results

    monkeypatch.setattr(
        "app.research.gpcs.graph_traversal_retriever",
        MagicMock(retrieve=MagicMock(return_value=[])),
    )
    monkeypatch.setattr(
        "app.research.gpcs.call_llm", lambda prompt, system_prompt, **_kwargs: None
    )

    scorer = GraphProvenanceClaimScorer()
    analysis = {
        "title": "Payment timeout",
        "summary": "The payment pod failed with a database timeout error.",
        "cause": "The service could not reach the backend database in time.",
    }

    result = scorer.score_claims(analysis, fake_search)

    assert result["claim_count"] >= 1
    assert 0.0 <= result["unsupported_claim_rate"] <= 1.0
    assert isinstance(result["claims"], list)
    for claim in result["claims"]:
        assert "trust_score" in claim
        assert "supporting_evidence" in claim
        assert isinstance(claim["unsupported"], bool)


def test_low_score_semantic_results_are_treated_as_no_evidence(monkeypatch):
    """graphrag_search's hybrid ranking always returns its top-k nearest
    neighbors even for a claim with no real match in the graph — verified
    live, a genuinely vague claim still scores 0.16-0.30 against whatever
    happens to be closest. Below MIN_SEMANTIC_EVIDENCE_SCORE must be
    treated the same as no evidence at all (hard-zero trust_score), or
    GPCS can never flag anything as unsupported."""
    below_threshold_results = {
        "results": [
            {"id": "n1", "label": "incident", "name": "unrelated", "score": 0.24},
            {"id": "n2", "label": "log", "name": "unrelated-2", "score": 0.18},
        ]
    }

    def fake_search(_payload: GraphRAGSearchPayload, _method: str | None = None):
        return below_threshold_results

    monkeypatch.setattr(
        "app.research.gpcs.graph_traversal_retriever",
        MagicMock(retrieve=MagicMock(return_value=[])),
    )
    monkeypatch.setattr(
        "app.research.gpcs.call_llm", lambda prompt, system_prompt, **_kwargs: None
    )

    scorer = GraphProvenanceClaimScorer()
    analysis = {
        "title": "Vague finding",
        "summary": "Monitoring data is inconclusive.",
        "cause": "No root cause could be confirmed.",
    }

    result = scorer.score_claims(analysis, fake_search)

    assert result["claim_count"] >= 1
    for claim in result["claims"]:
        assert claim["trust_score"] == 0.0
        assert claim["unsupported"] is True
