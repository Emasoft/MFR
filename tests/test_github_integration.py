#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial implementation of GitHub integration tests
# - Tests cloning a repository and building with uv
# - Supports both local and CI environments
#

"""Test GitHub repository cloning and building with MFR."""

import os
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path
import pytest
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def is_ci_environment() -> bool:
    """Check if running in CI environment."""
    return os.environ.get("CI", "").lower() == "true" or os.environ.get("GITHUB_ACTIONS", "").lower() == "true"


def run_command(cmd: list[str], cwd: Optional[Path] = None, timeout: int = 300) -> tuple[int, str, str]:
    """Run a command and return exit code, stdout, and stderr."""
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds"


class TestGitHubIntegration:
    """Test GitHub repository operations."""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing."""
        workspace = Path(tempfile.mkdtemp(prefix="mfr_test_"))
        yield workspace
        # Cleanup
        shutil.rmtree(workspace, ignore_errors=True)

    def test_clone_and_setup_public_repo(self, temp_workspace: Path):
        """Test cloning a public repository and setting up with uv."""
        # Use a small, stable public repo for testing
        test_repo = "https://github.com/psf/requests-html.git"
        repo_name = "requests-html"

        # Clone the repository
        print(f"\n📥 Cloning {test_repo}...")
        clone_dir = temp_workspace / repo_name

        # Use --depth 1 for faster cloning in tests
        exit_code, stdout, stderr = run_command(["git", "clone", "--depth", "1", test_repo, str(clone_dir)], timeout=60 if is_ci_environment() else 300)

        assert exit_code == 0, f"Failed to clone repo: {stderr}"
        assert clone_dir.exists(), "Clone directory does not exist"

        # Check if it's a Python project
        pyproject_path = clone_dir / "pyproject.toml"
        setup_py_path = clone_dir / "setup.py"

        assert pyproject_path.exists() or setup_py_path.exists(), "Not a Python project"

        print("✅ Repository cloned successfully")

    def test_build_mfr_in_container(self, temp_workspace: Path):
        """Test building MFR itself using uv build."""
        # Copy current project to temp workspace
        project_root = Path(__file__).parent.parent
        test_project = temp_workspace / "mfr_build_test"

        print(f"\n📦 Copying project to {test_project}...")

        # Copy essential files
        test_project.mkdir(parents=True)
        for item in ["src", "tests", "pyproject.toml", "uv.lock", "README.md", "replacement_mapping.json"]:
            src = project_root / item
            dst = test_project / item
            if src.exists():
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)

        # Create virtual environment
        print("🔧 Creating virtual environment with uv...")
        exit_code, stdout, stderr = run_command(["uv", "venv"], cwd=test_project, timeout=30)
        assert exit_code == 0, f"Failed to create venv: {stderr}"

        # Install dependencies
        print("📚 Installing dependencies...")
        exit_code, stdout, stderr = run_command(["uv", "sync", "--frozen"], cwd=test_project, timeout=120 if is_ci_environment() else 300)
        assert exit_code == 0, f"Failed to install dependencies: {stderr}"

        # Build the project
        print("🏗️  Building project with uv...")
        exit_code, stdout, stderr = run_command(["uv", "build"], cwd=test_project, timeout=60)
        assert exit_code == 0, f"Failed to build project: {stderr}"

        # Check build artifacts
        dist_dir = test_project / "dist"
        assert dist_dir.exists(), "dist directory not created"

        wheel_files = list(dist_dir.glob("*.whl"))
        tar_files = list(dist_dir.glob("*.tar.gz"))

        assert len(wheel_files) > 0, "No wheel file created"
        assert len(tar_files) > 0, "No source distribution created"

        print(f"✅ Built wheel: {wheel_files[0].name}")
        print(f"✅ Built sdist: {tar_files[0].name}")

    def test_mfr_on_cloned_repo(self, temp_workspace: Path):
        """Test running MFR on a cloned repository."""
        # Clone a small test repository
        test_repo = "https://github.com/psf/peps.git"
        repo_name = "peps"
        clone_dir = temp_workspace / repo_name

        print(f"\n🔄 Testing MFR on {test_repo}...")

        # Clone with minimal depth
        exit_code, stdout, stderr = run_command(
            ["git", "clone", "--depth", "1", "--single-branch", test_repo, str(clone_dir)],
            timeout=60 if is_ci_environment() else 300,
        )

        if exit_code != 0:
            pytest.skip(f"Could not clone test repo: {stderr}")

        # Create a test replacement mapping
        test_mapping = clone_dir / "test_replacement_mapping.json"
        test_mapping.write_text("""{
    "REPLACEMENT_MAPPING": {
        "Python": "Python🐍",
        "PEP": "PEP✨"
    }
}""")

        # Run MFR in dry-run mode
        print("🔍 Running MFR in dry-run mode...")
        exit_code, stdout, stderr = run_command(
            ["uv", "run", "mfr", str(clone_dir), "--dry-run", "--mapping-file", str(test_mapping)],
            cwd=Path(__file__).parent.parent,
            timeout=30,
        )

        assert exit_code == 0, f"MFR failed: {stderr}"
        assert "transaction" in stdout.lower() or "transaction" in stderr.lower(), "No transactions found"

        print("✅ MFR dry-run completed successfully")

    @pytest.mark.skipif(
        is_ci_environment() and not os.environ.get("GH_TOKEN"),
        reason="GitHub token required for private repo tests in CI",
    )
    def test_github_cli_operations(self, temp_workspace: Path):
        """Test GitHub CLI operations if available."""
        # Check if gh is available
        exit_code, stdout, stderr = run_command(["gh", "--version"], timeout=5)

        if exit_code != 0:
            pytest.skip("GitHub CLI not available")

        print(f"\n🐙 GitHub CLI version: {stdout.strip()}")

        # List public repos (doesn't require auth)
        exit_code, stdout, stderr = run_command(["gh", "repo", "list", "psf", "--limit", "5", "--public"], timeout=10)

        if exit_code == 0 and stdout:
            print("✅ Successfully listed public repositories")
            assert "psf/" in stdout, "No PSF repos found"
        else:
            print("⚠️  Could not list repos (may need authentication)")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "-s"])
