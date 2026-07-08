"""Demo module containing kubernetes incident manifest generation utilities."""

from .incident_scenario import (
    build_demo_incident_manifest,
    write_demo_incident_manifest,
)

__all__ = ["build_demo_incident_manifest", "write_demo_incident_manifest"]
