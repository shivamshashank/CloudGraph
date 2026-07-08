# pylint: skip-file
"""Integration tests for the CloudGraph Go CLI."""

import subprocess
import shutil
from pathlib import Path
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module", autouse=True)
def build_cli():
    """Build the CLI binary before running tests and clean up after."""
    go_path = shutil.which("go") or "/opt/homebrew/bin/go"
    subprocess.run(
        [go_path, "build", "-o", "cloudgraph", "./cmd/cloudgraph"],
        cwd=REPO_ROOT,
        check=True,
    )
    yield
    # Clean up after tests run
    binary = REPO_ROOT / "cloudgraph"
    if binary.exists():
        binary.unlink()


def test_cloudgraph_help_prints_usage():
    """Verify that calling cloudgraph --help prints the usage information."""
    env = {**subprocess.os.environ, "CLOUDGRAPH_TESTING": "true"}
    result = subprocess.run(
        ["./cloudgraph", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert "CloudGraph CLI" in result.stdout
    assert "Usage:" in result.stdout


def test_cloudgraph_version_prints_version():
    """Verify that calling cloudgraph version prints version metadata."""
    env = {**subprocess.os.environ, "CLOUDGRAPH_TESTING": "true"}
    result = subprocess.run(
        ["./cloudgraph", "version"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0
    assert "version" in result.stdout
