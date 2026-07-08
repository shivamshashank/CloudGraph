"""Evidence-aware text chunking for vector retrieval."""

from typing import Any


def _bounded_chunks(parts: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if current and len(current) + len(part) + 1 > max_chars:
            chunks.append(current)
            current = part
        else:
            current = f"{current}\n{part}".strip()
    if current:
        chunks.append(current)
    return chunks


def chunk_evidence(
    text: str, evidence_type: str, _metadata: dict[str, Any] | None = None
) -> list[str]:
    """Chunk evidence according to its operational meaning, not raw token count."""
    normalized_type = evidence_type.lower().replace("_", "-")
    text = text.strip()
    if not text:
        return []

    if normalized_type in {"log", "logs"}:
        # Preserve complete log lines and group short adjacent lines together.
        return _bounded_chunks(text.splitlines(), max_chars=1200)
    if normalized_type in {"metric", "metrics", "metrics-summary"}:
        # Metric inputs are aggregate-window summaries; never split individual values.
        return [text[:1600]]
    if normalized_type in {"incident", "incidents"}:
        # Incident sections remain coherent while long narratives split by paragraph.
        return _bounded_chunks(text.split("\n\n"), max_chars=1600)
    if normalized_type in {"deployment", "commit", "change"}:
        # Change metadata is one causal unit and should be retrieved together.
        return [text[:1600]]
    return _bounded_chunks(text.split("\n\n"), max_chars=1600)
