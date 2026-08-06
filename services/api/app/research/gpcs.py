"""Graph-Provenance Claim Scoring (GPCS) implementation.

This module provides a lightweight claim extraction and evidence scoring layer
for evaluating how well generated RCA statements are grounded in the
GraphRAG retrieval results.
"""

import json
import os
import re
from typing import Any, Callable

import requests

from app.retrieval.graph_traversal import graph_traversal_retriever
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


def call_llm(
    prompt: str,
    system_prompt: str = "You are an expert AIOps assistant. Output valid JSON.",
    provider: str = "",
    api_key: str = "",
    model: str = "",
) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Execute direct LLM queries against OpenAI, Gemini, or Meta's API.

    OpenAI and Gemini share an OpenAI-compatible /chat/completions shape.
    Meta uses a different, Responses-API-style surface (/v1/responses) with
    its own request/response shape — handled separately below.

    Returns the parsed JSON response, or None on failure (missing key,
    unsupported provider, unreachable server, malformed response).
    """
    provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower().strip()
    api_key = (
        api_key
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("META_API_KEY")
    )
    if not api_key:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    timeout = 60

    chat_completions_config = {
        "openai": (
            "https://api.openai.com/v1/chat/completions",
            "gpt-4o-mini",
        ),
        "gemini": (
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            "gemini-1.5-flash",
        ),
    }
    try:
        if provider in chat_completions_config:
            url, default_model = chat_completions_config[provider]
            model = model or os.getenv("LLM_MODEL", default_model)
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            }
            res = requests.post(url, headers=headers, json=payload, timeout=timeout)
            res.raise_for_status()
            content = res.json()["choices"][0]["message"]["content"]
            return json.loads(content)

        if provider == "meta":
            # Request shape verified against a real example from the
            # account owner (api.meta.ai/v1/responses, not the
            # chat-completions shape). "instructions" for the system
            # prompt and the response-parsing shape below are inferred
            # from that example plus the OpenAI Responses API this
            # endpoint appears to mirror — not independently confirmed.
            url = "https://api.meta.ai/v1/responses"
            model = model or os.getenv("LLM_MODEL", "muse-spark-1.2")
            payload = {
                "model": model,
                "instructions": system_prompt,
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": prompt}],
                    }
                ],
                "temperature": 0.1,
                "stream": False,
            }
            res = requests.post(url, headers=headers, json=payload, timeout=timeout)
            res.raise_for_status()
            data = res.json()
            message_item = next(
                (
                    item
                    for item in data.get("output", [])
                    if item.get("type") == "message"
                ),
                None,
            )
            if not message_item or not message_item.get("content"):
                return None
            content = message_item["content"][0]["text"]
            return json.loads(content)
    except (
        requests.RequestException,
        AttributeError,
        KeyError,
        IndexError,
        ValueError,
    ):
        # Contract of this function is "never raise" — any failure to reach
        # the provider or parse its response degrades to the heuristic,
        # non-LLM claim extraction path in the caller.
        return None

    return None


class GraphProvenanceClaimScorer:
    """Implementation of Graph-Provenance Claim Scoring."""

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
        llm_claims = self._extract_claims_with_llm(raw_text)
        if llm_claims:
            return llm_claims

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

    def _extract_claims_with_llm(self, raw_text: str) -> list[dict[str, str]]:
        prompt = (
            "Extract the atomic factual claims from the following RCA summary. "
            "Return a JSON array of objects with keys: claim_id, text, claim_type. "
            "claim_type must be one of "
            "temporal, causal, entity_relationship, state, general.\n\n"
            f"RCA text:\n{raw_text}\n\n"
            "Example output:\n"
            '[{"claim_id": "claim-1", "text": "...", "claim_type": "state"}]'
        )
        system_prompt = (
            "You are an expert claim extractor for AIOps incident reports. "
            "Output only a JSON array."
        )
        llm_res = call_llm(prompt, system_prompt)
        if isinstance(llm_res, list):
            claims = []
            for item in llm_res:
                if isinstance(item, dict) and item.get("claim_id") and item.get("text"):
                    claims.append(
                        {
                            "id": str(item["claim_id"]),
                            "text": self._normalize_claim_text(str(item["text"])),
                            "type": item.get("claim_type", "general"),
                        }
                    )
            return claims
        return []

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
            word in lower for word in ["failed", "crash", "error", "timed out", "oom"]
        ):
            return "state"
        if any(word in lower for word in ["cause", "reason", "because"]):
            return "causal"
        return "general"

    def _extract_entities(self, claim: str) -> list[str]:
        names = re.findall(r"([A-Za-z0-9_-]+(?:service|deployment|pod))", claim)
        if names:
            return list(dict.fromkeys(names))
        tokens = re.findall(r"[A-Za-z0-9_-]+", claim)
        return [
            t
            for t in dict.fromkeys(tokens)
            if t.lower().endswith(("service", "deployment", "pod"))
        ]

    def _retrieve_supporting_evidence(
        self,
        claim: str,
        search_func: ClaimSearchFunc,
    ) -> list[dict[str, Any]]:
        evidence_candidates = []
        try:
            payload = GraphRAGSearchPayload(query=claim, depth=2, method="hybrid")
            search_res = search_func(payload, method="hybrid")
            evidence_candidates.extend(search_res.get("results", []) or [])
        except (ValueError, KeyError, TypeError, RuntimeError):
            pass

        entities = self._extract_entities(claim)
        for entity in entities[:3]:
            try:
                traversal = graph_traversal_retriever.retrieve(entity, depth=2, limit=8)
                for item in traversal:
                    evidence_candidates.append(
                        {
                            "id": item.get("id"),
                            "label": item.get("type", "node"),
                            "type": item.get("type", "node"),
                            "name": item.get("name"),
                            "score": 0.6 if item.get("hop_distance", 0) > 2 else 0.75,
                            "hop_distance": item.get("hop_distance"),
                            "sources": ["graph"],
                        }
                    )
            except (RuntimeError, ValueError, KeyError, TypeError, AttributeError):
                continue

        unique = {}
        deduped = []
        for item in evidence_candidates:
            item_id = item.get("id") or item.get("name")
            if not item_id or item_id in unique:
                continue
            unique[item_id] = True
            deduped.append(item)
        return deduped

    def _aggregate_evidence_metrics(
        self, evidence: list[dict[str, Any]]
    ) -> tuple[float, int | None, float, list[dict[str, Any]]]:
        """Aggregate scores, hop distances, and reliability from evidence list."""
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

        avg_reliability = (
            (total_reliability / reliability_count) if reliability_count else 0.0
        )
        return best_score, min_hop_distance, avg_reliability, best_evidence

    def _score_claim(
        self, evidence: list[dict[str, Any]]
    ) -> tuple[float, list[dict[str, Any]]]:
        if not evidence:
            return 0.0, []

        best_score, min_hop_distance, avg_reliability, best_evidence = (
            self._aggregate_evidence_metrics(evidence)
        )

        min_hop = 0 if min_hop_distance is None else min_hop_distance
        proximity = 1.0 / (1.0 + min_hop) if min_hop >= 0 else 0.0
        penalty = self.penalty_weight * (min_hop * 0.05)

        trust_score = (
            self.semantic_weight * best_score
            + self.graph_weight * proximity
            + self.reliability_weight * avg_reliability
            - penalty
        )
        trust_score = max(0.0, min(1.0, trust_score))

        sorted_evidence = sorted(
            best_evidence,
            key=lambda item: item.get("score", 0.0),
            reverse=True,
        )[:3]

        return trust_score, sorted_evidence
