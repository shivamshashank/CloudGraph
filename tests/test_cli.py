import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_cloudgraph_help_prints_usage():
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "cloudgraph"), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "CloudGraph CLI" in result.stdout
    assert "Usage:" in result.stdout


def test_cloudgraph_version_prints_version():
    result = subprocess.run(
        ["bash", str(REPO_ROOT / "cloudgraph"), "version"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "cloudgraph" in result.stdout.lower()


def test_install_script_uses_local_cloudgraph_when_present(tmp_path):
    env = os.environ.copy()
    env["CLOUDGRAPH_INSTALL_DIR"] = str(tmp_path)
    env["CLOUDGRAPH_REPO_URL"] = "https://example.invalid"

    result = subprocess.run(
        ["bash", str(REPO_ROOT / "install.sh")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0
    assert (tmp_path / "cloudgraph").exists()
    assert "CloudGraph CLI installed" in result.stdout
