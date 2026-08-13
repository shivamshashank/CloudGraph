"""API endpoints for generating CloudGraph's research report (GPCS vs.
self-consistency) as a background job — see app/research/report_runner.py.
Driven by the `cloudgraph report` CLI command, not the web UI."""

from fastapi import APIRouter, Query

from app.research import report_runner

router = APIRouter()


@router.post("/api/v1/research/report")
def start_report(
    limit: int | None = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
):
    """Start generating the report in the background. Returns immediately —
    a full run can take a long time. Poll via GET /api/v1/research/report
    for status and the eventual result.

    offset + limit select a slice of the benchmark
    (offset=5&limit=5 runs scenarios 6-10), so a full run can be split
    into independent batches instead of one long one — each batch's
    result is self-contained; combine batches with
    scripts/merge_reports.py."""
    started = report_runner.start_report(scenario_limit=limit, scenario_offset=offset)
    if not started:
        return {"status": "already_running"}
    return {"status": "started"}


@router.get("/api/v1/research/report")
def get_report():
    """Current status of the report run — idle/running/completed/failed,
    a human-readable progress string, and the result once completed."""
    return report_runner.get_status()
