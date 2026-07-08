"""Tests verifying demo incident manifest creation."""

from app.demo.incident_scenario import build_demo_incident_manifest


def test_build_demo_incident_manifest_contains_expected_incident_details():
    """Verify that build_demo_incident_manifest returns expected manifest strings."""
    manifest = build_demo_incident_manifest()

    assert "kind: Deployment" in manifest
    assert "name: demo-payment-app" in manifest
    assert "namespace: cloudgraph-system" in manifest
    assert "image: nginx:does-not-exist" in manifest
    assert "DB_PASSWORD" in manifest
    assert "value: wrong-password" in manifest
