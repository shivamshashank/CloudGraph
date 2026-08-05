"""API endpoints for generating CloudGraph's research report (GPCS vs.
self-consistency) as a background job — see app/research/report_runner.py.
Driven by the `cloudgraph report` CLI command, not the web UI."""

from fastapi import APIRouter, Query

from app.research import report_runner

router = APIRouter()


@router.post("/api/v1/research/report")
def start_report(limit: int | None = Query(default=None, ge=1)):
    """Start generating the report in the background. Returns immediately —
    a full run can take a long time on local CPU inference. Poll via
    GET /api/v1/research/report for status and the eventual result."""
    started = report_runner.start_report(scenario_limit=limit)
    if not started:
        return {"status": "already_running"}
    return {"status": "started"}


@router.get("/api/v1/research/report")
def get_report():
    """Current status of the report run — idle/running/completed/failed,
    a human-readable progress string, and the result once completed."""
    return report_runner.get_status()
