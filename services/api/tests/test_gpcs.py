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
        "app.research.gpcs.call_llm", lambda prompt, system_prompt: mocked_response
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
        "app.research.gpcs.call_llm", lambda prompt, system_prompt: None
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
        "app.research.gpcs.call_llm", lambda prompt, system_prompt: None
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
