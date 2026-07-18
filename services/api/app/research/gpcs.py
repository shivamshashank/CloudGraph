"""Graph-Provenance Claim Scoring (GPCS) implementation.

This module provides a lightweight claim extraction and evidence scoring layer
for evaluating how well generated RCA statements are grounded in the
GraphRAG retrieval results.
"""

import re
from typing import Any, Callable

from app.schemas import GraphRAGSearchPayload

ClaimSearchFunc = Callable[[GraphRAGSearchPayload, str], dict[str, Any]]

SOURCE_RELIABILITY = {
    "pod": 0.90,
    "service": 0.90,
    "deployment": 0.90,
    "incident": 0.90,
    "log": 0.80,
    "metric": 0.85,
    "node": 0.75,
}


class GraphProvenanceClaimScorer:
    """Minimal implementation of Graph-Provenance Claim Scoring."""

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        threshold: float = 0.50,
    ):
        weights = weights or {}
        self.semantic_weight = weights.get("semantic", 0.45)
        self.graph_weight = weights.get("graph", 0.35)
        self.reliability_weight = weights.get("reliability", 0.25)
        self.penalty_weight = weights.get("penalty", 0.15)
        self.threshold = threshold

    def score_claims(
        self,
        analysis: dict[str, Any],
        search_func: ClaimSearchFunc,
    ) -> dict[str, Any]:
        """Score the claims extracted from an analysis against the evidence graph."""
        claims = self.extract_claims(analysis)
        scored_claims = []
        unsupported = 0

        for claim in claims:
            evidence = self._retrieve_supporting_evidence(claim["text"], search_func)
            score, details = self._score_claim(evidence)
            claim_result = {
                "claim_id": claim["id"],
                "text": claim["text"],
                "claim_type": claim["type"],
                "trust_score": round(score, 3),
                "unsupported": score < self.threshold,
                "supporting_evidence": details,
            }
            if claim_result["unsupported"]:
                unsupported += 1
            scored_claims.append(claim_result)

        total = len(scored_claims)
        unsupported_rate = round(unsupported / total, 3) if total else 0.0
        return {
            "unsupported_claim_rate": unsupported_rate,
            "claim_count": total,
            "claims": scored_claims,
        }

    def extract_claims(self, analysis: dict[str, Any]) -> list[dict[str, str]]:
        """Extract atomic claims from an analysis payload."""
        raw_text = " ".join(
            str(analysis.get(key, ""))
            for key in ("title", "summary", "cause")
            if analysis.get(key)
        )
        raw_text = raw_text.replace(" - ", ". ")
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", raw_text)
            if sentence.strip()
        ]

        claims = []
        claim_id = 1
        for sentence in sentences:
            normalized = self._normalize_claim_text(sentence)
            if not normalized or len(normalized) < 20:
                continue
            claims.append(
                {
                    "id": f"claim-{claim_id}",
                    "text": normalized,
                    "type": self._guess_claim_type(normalized),
                }
            )
            claim_id += 1
        return claims

    def _normalize_claim_text(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        cleaned = cleaned.rstrip(".?")
        return cleaned

    def _guess_claim_type(self, claim: str) -> str:
        lower = claim.lower()
        if any(word in lower for word in ["before", "after", "during", "time"]):
            return "temporal"
        if any(word in lower for word in ["depends on", "belongs to", "calls", "uses"]):
            return "entity_relationship"
        if any(
            word in lower for word in ["failed", "crash", "error", "timed out", "OOM"]
        ):
            return "state"
        if any(word in lower for word in ["cause", "reason", "because"]):
            return "causal"
        return "general"

    def _retrieve_supporting_evidence(
        self,
        claim: str,
        search_func: ClaimSearchFunc,
    ) -> dict[str, Any]:
        try:
            payload = GraphRAGSearchPayload(query=claim, depth=2, method="hybrid")
            results = search_func(payload, method="hybrid")
            return results.get("results", [])
        except (ValueError, KeyError, TypeError, RuntimeError):
            return []

    def _score_claim(
        self, evidence: list[dict[str, Any]]
    ) -> tuple[float, list[dict[str, Any]]]:
        if not evidence:
            return 0.0, []

        best_score = 0.0
        best_evidence = []
        min_hop_distance = None
        total_reliability = 0.0
        reliability_count = 0

        for result in evidence[:5]:
            score = float(result.get("score", 0.0))
            best_score = max(best_score, score)
            hop_distance = result.get("hop_distance")
            if hop_distance is not None:
                min_hop_distance = (
                    hop_distance
                    if min_hop_distance is None
                    else min(min_hop_distance, hop_distance)
                )
            label = str(result.get("label", result.get("type", "unknown"))).lower()
            reliability = SOURCE_RELIABILITY.get(label, 0.60)
            total_reliability += reliability
            reliability_count += 1

            best_evidence.append(
                {
                    "label": label,
                    "name": result.get("name"),
                    "score": round(score, 3),
                    "hop_distance": hop_distance,
                    "sources": result.get("sources", []),
                }
            )

        min_hop_distance = 0 if min_hop_distance is None else min_hop_distance

        trust_score = (
            self.semantic_weight * best_score
            + self.graph_weight
            * (1.0 / (1.0 + min_hop_distance) if min_hop_distance >= 0 else 0.0)
            + self.reliability_weight
            * ((total_reliability / reliability_count) if reliability_count else 0.0)
            - self.penalty_weight * (min_hop_distance * 0.05)
        )
        trust_score = max(0.0, min(1.0, trust_score))

        return trust_score, best_evidence[:3]
