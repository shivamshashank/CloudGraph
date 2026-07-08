"""Tests verifying the hybrid ranking of search context entries."""

import pytest

from app.retrieval.hybrid_ranker import HybridRanker


def test_hybrid_ranker_combines_vector_graph_and_recency_with_rationale():
    """
    Verify that HybridRanker correctly weights and scores vector and graph features.
    """
    ranker = HybridRanker(recency_half_life_seconds=3600)
    vector_hits = [
        {
            "id": "qdrant-point-modified-unique",
            "text": "database auth failure event",
            "score": 0.85,
            "metadata": {
                "source_id": "log-entry-modified-unique-1",
                "type": "log",
                "name": "payment service authentication failures",
                "timestamp": 6400,
            },
        }
    ]
    graph_hits = [
        {
            "id": "neo4j-element",
            "labels": ["Log"],
            "properties": {"id": "log-entry-modified-unique-1", "timestamp": 6400},
            "hop_distance": 1,
            "relationships": ["GENERATES"],
            "path": [{"name": "payment"}, {"name": "payment log"}],
        }
    ]

    result = ranker.rank(vector_hits, graph_hits, reference_time=10000)[0]

    # 0.50*0.85 + 0.30*0.5 + 0.20*0.5 = 0.675
    assert result["score"] == pytest.approx(0.675)
    assert result["sources"] == ["graph", "vector"]
    assert result["score_breakdown"]["vector_similarity"]["contribution"] == 0.425
    assert result["score_breakdown"]["graph_proximity"]["hop_distance"] == 1
    assert result["score_breakdown"]["recency"]["age_seconds"] == 3600
    assert result["score_breakdown"]["final_score"] == pytest.approx(0.675)
    assert len(result["ranking_rationale"]) == 3


def test_closer_and_newer_graph_evidence_ranks_above_distant_old_evidence():
    """Verify that closer hop counts and more recent timestamps yield higher scores."""
    ranker = HybridRanker(recency_half_life_seconds=3600)
    graph_hits = [
        {
            "id": "near",
            "labels": ["Log"],
            "properties": {"id": "near", "timestamp": 9900},
            "hop_distance": 1,
        },
        {
            "id": "far",
            "labels": ["Log"],
            "properties": {"id": "far", "timestamp": 1000},
            "hop_distance": 3,
        },
    ]

    results = ranker.rank([], graph_hits, reference_time=10000)

    assert [result["id"] for result in results] == ["near", "far"]
    assert results[0]["score"] > results[1]["score"]


def test_vector_only_evidence_has_zero_graph_and_missing_time_contributions():
    """
    Verify that evidence only found in vector store does not receive
    graph/recency scores.
    """
    result = HybridRanker().rank(
        [{"id": "doc-1", "text": "failure", "score": 0.9, "metadata": {}}],
        [],
        reference_time=10000,
    )[0]

    assert result["score"] == pytest.approx(0.45)
    assert result["score_breakdown"]["graph_proximity"]["raw_score"] == 0.0
    assert result["score_breakdown"]["recency"]["raw_score"] == 0.0


def test_ranker_rejects_weights_that_do_not_sum_to_one():
    """Verify that ranker construction asserts sum of weights equals 1.0."""
    with pytest.raises(ValueError, match="sum to 1.0"):
        HybridRanker(vector_weight=0.5, graph_weight=0.5, recency_weight=0.5)
