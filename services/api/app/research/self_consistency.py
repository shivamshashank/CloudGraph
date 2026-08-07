"""Self-consistency hallucination baseline — compared head-to-head with GPCS.

Self-consistency (Wang et al.-style) is the dominant model-internal
hallucination-detection family in the literature: generate the same answer
multiple times at elevated temperature and flag claims that don't recur
across samples. GPCS (`app.research.gpcs`) is evidence-grounded instead —
this module exists to produce a fair, apples-to-apples comparison between
the two (Contribution 2, `research/NOVEL_CONTRIBUTIONS.md`).

This is only a meaningful measurement when generations actually vary due to
real LLM stochasticity. It must never silently accept the deterministic
rule-based consensus fallback as if it were a valid sample — every claim
would trivially "recur" in 100% of identical generations, which is not a
measurement of anything.
"""

import datetime
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests

from app.research.gpcs import GraphProvenanceClaimScorer
from app.research.llm_settings import load_stored_llm_settings
from app.services.embeddings import SentenceTransformerEmbedder

logger = logging.getLogger(__name__)

DEFAULT_N_SAMPLES = 3
DEFAULT_TEMPERATURE = 0.8
# Same threshold GPCS's own design doc and the rest of this sprint uses for
# semantic-equivalence checks between two claim strings.
RECURRENCE_SIMILARITY_THRESHOLD = 0.8
# A small breather between samples — cloud providers enforce per-minute
# rate limits that vary by provider and account tier, and this reduces the
# odds of bursting past them when generating N samples back-to-back.
INTER_SAMPLE_DELAY_SECONDS = 2.0


class SelfConsistencyUnavailableError(RuntimeError):
    """Raised when a real, LLM-backed generation cannot be obtained.

    Covers: orchestrator unreachable, non-200 response, malformed body, or
    (critically) the orchestrator silently used its deterministic
    rule-based fallback instead of calling an LLM — detected via the
    `generation_source` field added to ConsensusEngine's response
    specifically so callers here can tell the difference.

    `retryable` is False when the underlying cause is a provider quota
    that a retry cannot fix (e.g. Groq's daily-tokens cap) — retrying
    those just burns more of an already-exhausted budget for a request
    that is structurally guaranteed to fail again. See
    `_is_quota_exhausted_reason`.
    """

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


# Substrings observed directly in real provider error bodies (Groq's
# "tokens per day (TPD)" 429, and the generic OpenAI-style
# "rate_limit_exceeded" code) that indicate a hard quota ceiling rather
# than a transient burst — confirmed via a live reproduction, not guessed.
_QUOTA_EXHAUSTED_MARKERS = (
    "tokens per day",
    "rate_limit_exceeded",
    "429",
    "too many requests",
)


def _is_quota_exhausted_reason(reason: Optional[str]) -> bool:
    if not reason:
        return False
    text = reason.lower()
    return any(marker in text for marker in _QUOTA_EXHAUSTED_MARKERS)


MAX_ATTEMPTS_PER_SAMPLE = 3

# Called once per HTTP attempt to /orchestrate (success or failure) with a
# JSON-serializable record: {timestamp, scenario_id, request, status_code,
# response, error}. The request's llm_api_key is always redacted before the
# logger ever sees it — this exists purely for experiment auditability
# ("what did we actually send/receive"), never to persist a credential.
RequestLogger = Callable[[Dict[str, Any]], None]


def _sanitize_request_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = dict(payload)
    if sanitized.get("llm_api_key"):
        sanitized["llm_api_key"] = "<redacted>"
    return sanitized


def _request_one_sample(
    scenario: Dict[str, Any],
    temperature: float,
    orch_addr: str,
    request_logger: Optional[RequestLogger] = None,
    retrieval_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Request one real, LLM-backed RCA generation for a scenario.

    retrieval_results defaults to empty — the original Day-2 condition:
    agents reason from error_logs alone, no retrieved evidence injected.
    Passing a populated list is what the Day-3 raw-context and
    ranked-hybrid conditions use to inject their retrieval into the exact
    same generation pipeline, so only the context varies, nothing else.
    """
    llm_settings = load_stored_llm_settings()
    request_payload = {
        "pod_id": f"pod-{scenario['id']}",
        "pod_name": scenario["target_entity"],
        "pod_status": "Failed",
        "namespace": "cloudgraph-system",
        "error_logs": scenario["ground_truth_claims"],
        "evidence_context": [],
        "retrieval_context": {"results": retrieval_results or []},
        "llm_temperature": temperature,
        "llm_provider": llm_settings.get("provider"),
        "llm_api_key": llm_settings.get("api_key"),
        "llm_model": llm_settings.get("model"),
    }

    def _log(
        status_code: Optional[int], response_body: Any, error: Optional[str]
    ) -> None:
        if request_logger is None:
            return
        request_logger(
            {
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "scenario_id": scenario["id"],
                "request": _sanitize_request_payload(request_payload),
                "status_code": status_code,
                "response": response_body,
                "error": error,
            }
        )

    try:
        response = requests.post(
            f"{orch_addr.rstrip('/')}/orchestrate",
            json=request_payload,
            # Must exceed the orchestrator's own wait for investigation-engine
            # (360s) plus its own consensus LLM call (up to 60s) — see the
            # timeout comment in agent-orchestrator/main.py for why.
            timeout=600,
        )
    except requests.RequestException as exc:
        _log(None, None, str(exc))
        raise SelfConsistencyUnavailableError(
            f"agent-orchestrator unreachable at {orch_addr}: {exc}"
        ) from exc

    if response.status_code != 200:
        _log(response.status_code, None, f"HTTP {response.status_code}")
        raise SelfConsistencyUnavailableError(
            f"agent-orchestrator returned HTTP {response.status_code} "
            f"for scenario {scenario['id']}"
        )

    rdata = response.json()
    _log(response.status_code, rdata, None)
    consensus = rdata.get("consensus")
    if rdata.get("status") != "success" or not consensus:
        raise SelfConsistencyUnavailableError(
            f"agent-orchestrator response missing consensus for "
            f"scenario {scenario['id']}: {rdata}"
        )
    if consensus.get("generation_source") != "llm":
        failure_reason = consensus.get("llm_failure_reason")
        quota_exhausted = _is_quota_exhausted_reason(failure_reason)
        detail = (
            f" Underlying error: {failure_reason}"
            if failure_reason
            else " No LLM provider configured yet (set one on the Settings "
            "page), or the provider request itself failed."
        )
        raise SelfConsistencyUnavailableError(
            "agent-orchestrator used its deterministic rule-based fallback "
            "instead of a real LLM call —" + detail + " self-consistency "
            "cannot be measured without genuine sample-to-sample variation.",
            retryable=not quota_exhausted,
        )
    return consensus


RETRY_BACKOFF_SECONDS = 4.0


def _generate_one_sample(
    scenario: Dict[str, Any],
    temperature: float,
    orch_addr: str,
    request_logger: Optional[RequestLogger] = None,
    retrieval_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Request one real, LLM-backed generation, retrying transient failures
    with a backoff delay between attempts.

    The orchestrator chains 6 sequential LLM calls (5 specialists + 1
    consensus), each subject to ordinary real-world API flakiness — most
    commonly a token-per-minute burst limit (Groq's free tier is 12K TPM,
    easily exceeded by 6 back-to-back calls fired in under 2 seconds).
    Retrying instantly just re-hits the same wall; a short backoff gives
    the provider's rate-limit window time to refill. Retrying is honest —
    each attempt is still a genuine, non-fabricated request — unlike
    silently accepting a rule-based fallback would be.
    """
    last_error: Optional[SelfConsistencyUnavailableError] = None
    for attempt in range(1, MAX_ATTEMPTS_PER_SAMPLE + 1):
        try:
            return _request_one_sample(
                scenario,
                temperature,
                orch_addr,
                request_logger=request_logger,
                retrieval_results=retrieval_results,
            )
        except SelfConsistencyUnavailableError as exc:
            last_error = exc
            logger.warning(
                "Sample generation attempt %d/%d failed for scenario '%s': %s",
                attempt,
                MAX_ATTEMPTS_PER_SAMPLE,
                scenario["id"],
                exc,
            )
            if not exc.retryable:
                # A hard provider quota (e.g. Groq's daily-tokens cap) —
                # retrying cannot help and only spends more of an already-
                # exhausted budget on a request guaranteed to fail again.
                logger.warning(
                    "Non-retryable quota failure for scenario '%s' — "
                    "stopping after 1 attempt instead of %d.",
                    scenario["id"],
                    MAX_ATTEMPTS_PER_SAMPLE,
                )
                break
            if attempt < MAX_ATTEMPTS_PER_SAMPLE:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise SelfConsistencyUnavailableError(
        f"all attempts failed for scenario '{scenario['id']}': {last_error}",
        retryable=last_error.retryable if last_error else True,
    ) from last_error


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Both vectors come from SentenceTransformerEmbedder, which L2-
    normalizes — dot product is therefore already cosine similarity."""
    return sum(x * y for x, y in zip(a, b))


def _generate_samples(  # pylint: disable=too-many-arguments
    scenario: Dict[str, Any],
    n_samples: int,
    temperature: float,
    orch_addr: str,
    request_logger: Optional[RequestLogger],
    retrieval_results: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Generate n_samples real RCA analyses, spacing calls out rather than
    bursting all n_samples * 6 calls back to back — same token-per-minute
    rationale as the retry backoff in _generate_one_sample."""
    generations = []
    for i in range(n_samples):
        if i > 0:
            time.sleep(INTER_SAMPLE_DELAY_SECONDS)
        generations.append(
            _generate_one_sample(
                scenario,
                temperature,
                orch_addr,
                request_logger=request_logger,
                retrieval_results=retrieval_results,
            )
        )
    return generations


def _score_claim_recurrence(
    primary_claims: List[Dict[str, Any]],
    other_embeddings: List[List[List[float]]],
    embedder: SentenceTransformerEmbedder,
) -> Tuple[List[Dict[str, Any]], int]:
    """Score each primary claim's recurrence across the other generations'
    embeddings. A claim is unsupported if a semantically equivalent claim
    (cosine similarity >= RECURRENCE_SIMILARITY_THRESHOLD) recurs in fewer
    than half of the other generations."""
    scored_claims = []
    unsupported = 0
    for claim in primary_claims:
        claim_vec = embedder.embed(claim["text"])
        recurrence_count = sum(
            1
            for gen_vecs in other_embeddings
            if any(
                _cosine_similarity(claim_vec, other_vec)
                >= RECURRENCE_SIMILARITY_THRESHOLD
                for other_vec in gen_vecs
            )
        )
        n_other = len(other_embeddings)
        recurrence_rate = round(recurrence_count / n_other, 3) if n_other else 0.0
        unsupported_flag = recurrence_rate < 0.5
        if unsupported_flag:
            unsupported += 1
        scored_claims.append(
            {
                "claim_id": claim["id"],
                "text": claim["text"],
                "claim_type": claim["type"],
                "recurrence_count": recurrence_count,
                "n_other_generations": n_other,
                "recurrence_rate": recurrence_rate,
                "unsupported": unsupported_flag,
            }
        )
    return scored_claims, unsupported


def generate_and_score(  # pylint: disable=too-many-arguments,too-many-locals
    scenario: Dict[str, Any],
    n_samples: int = DEFAULT_N_SAMPLES,
    temperature: float = DEFAULT_TEMPERATURE,
    orch_addr: Optional[str] = None,
    request_logger: Optional[RequestLogger] = None,
    retrieval_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Generate n_samples real RCA analyses for a scenario at elevated
    temperature and score self-consistency.

    A claim from the first ("primary") generation is treated as supported
    if a semantically equivalent claim (cosine similarity >= 0.8) recurs in
    at least half of the *other* n_samples - 1 generations — matching
    GPCS's own claim-level granularity so the two methods are comparable
    claim-for-claim, not just in aggregate.

    Uses GraphProvenanceClaimScorer.extract_claims for claim segmentation —
    the identical extractor GPCS uses — so the comparison is fair: the same
    text is split into the same claims by both methods, only the
    verification mechanism differs.

    retrieval_results is None by default (the original Day-2 condition —
    no retrieved evidence injected, agents reason from error_logs alone).
    Passing Day 3's raw-context or ranked-hybrid retrieval results here
    runs the identical generation+scoring pipeline against a different
    context condition — see app/research/report_runner.py.
    """
    if n_samples < 2:
        raise ValueError("self-consistency requires at least 2 samples")

    orch_addr = orch_addr or os.getenv(
        "AGENT_ORCHESTRATOR_URL", "http://localhost:8082"
    )
    llm_settings = load_stored_llm_settings()
    scorer = GraphProvenanceClaimScorer(
        llm_provider=llm_settings.get("provider") or "",
        llm_api_key=llm_settings.get("api_key") or "",
        llm_model=llm_settings.get("model") or "",
    )
    embedder = SentenceTransformerEmbedder()

    generations = _generate_samples(
        scenario,
        n_samples,
        temperature,
        orch_addr,
        request_logger,
        retrieval_results=retrieval_results,
    )

    claims_per_generation = [scorer.extract_claims(g) for g in generations]
    primary_claims = claims_per_generation[0]
    other_embeddings = [
        [embedder.embed(c["text"]) for c in claims]
        for claims in claims_per_generation[1:]
    ]

    scored_claims, unsupported = _score_claim_recurrence(
        primary_claims, other_embeddings, embedder
    )

    total = len(scored_claims)
    return {
        "unsupported_claim_rate": round(unsupported / total, 3) if total else None,
        "claim_count": total,
        "claims": scored_claims,
        "n_samples": n_samples,
        "temperature": temperature,
        "generations": generations,
    }
