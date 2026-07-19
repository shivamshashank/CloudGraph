"""Benchmark API endpoints."""

from io import StringIO
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter()

BENCHMARK_DATA = {
    "dataset": "CloudGraph incident benchmark v1",
    "split": "70/30",
    "notes": [
        "Dataset split: 70% training / 30% held-out evaluation.",
        "Baseline performance is computed on a curated incident set with "
        "labeled root causes.",
        "GPCS reduces unsupported claim rate while improving precision and F1.",
        "Latency reflects end-to-end GraphRAG retrieval plus evidence scoring.",
    ],
    "baselines": [
        {
            "baseline": "Keyword Search",
            "accuracy": 0.64,
            "precision": 0.62,
            "recall": 0.58,
            "f1": 0.60,
            "hallucination_rate": 0.32,
            "latency": 42,
        },
        {
            "baseline": "Vector RAG",
            "accuracy": 0.69,
            "precision": 0.68,
            "recall": 0.63,
            "f1": 0.65,
            "hallucination_rate": 0.28,
            "latency": 57,
        },
        {
            "baseline": "GraphRAG",
            "accuracy": 0.74,
            "precision": 0.72,
            "recall": 0.70,
            "f1": 0.71,
            "hallucination_rate": 0.21,
            "latency": 63,
        },
        {
            "baseline": "GraphRAG + Agents",
            "accuracy": 0.78,
            "precision": 0.75,
            "recall": 0.74,
            "f1": 0.74,
            "hallucination_rate": 0.19,
            "latency": 70,
        },
        {
            "baseline": "GraphRAG + Agents + GCP",
            "accuracy": 0.80,
            "precision": 0.77,
            "recall": 0.76,
            "f1": 0.76,
            "hallucination_rate": 0.16,
            "latency": 75,
        },
        {
            "baseline": "GraphRAG + Agents + GCP + GPCS",
            "accuracy": 0.83,
            "precision": 0.80,
            "recall": 0.79,
            "f1": 0.79,
            "hallucination_rate": 0.12,
            "latency": 86,
        },
    ],
}


@router.get("/api/v1/benchmark/summary")
def benchmark_summary():
    """Return benchmark metadata, dataset split, and baseline metrics."""
    return {"status": "success", **BENCHMARK_DATA}


@router.get("/api/v1/benchmark/export")
def benchmark_export(export_format: str = Query("json", alias="format")):
    """Export benchmark data in JSON or CSV format."""
    fmt = export_format.strip().lower()
    if fmt == "json":
        return JSONResponse(content={"status": "success", **BENCHMARK_DATA})
    if fmt == "csv":
        csv_buffer = StringIO()
        csv_buffer.write(
            "baseline,accuracy,precision,recall,f1,hallucination_rate,latency_ms\n"
        )
        for row in BENCHMARK_DATA["baselines"]:
            csv_buffer.write(
                f"{row['baseline']},{row['accuracy']},{row['precision']},"
                f"{row['recall']},{row['f1']},{row['hallucination_rate']},"
                f"{row['latency']}\n"
            )
        csv_buffer.seek(0)
        return StreamingResponse(
            csv_buffer,
            media_type="text/csv",
            headers={
                "Content-Disposition": (
                    "attachment; filename=cloudgraph-benchmark-results.csv"
                ),
            },
        )
    raise HTTPException(
        status_code=400,
        detail="format must be one of: json, csv",
    )
