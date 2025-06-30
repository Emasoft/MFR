#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of self-test functionality from parser.py
# - This module handles the --self-test option
#

"""
Self-test runner for the Mass Find Replace CLI.

This module provides functionality for running automated tests
when the --self-test option is used.
"""

from __future__ import annotations
import sys

from ...ui.display import BLUE, RED, YELLOW, RESET
from .subprocess_runner import run_subprocess_command

__all__ = ["run_self_tests"]


def run_self_tests() -> None:
    """Run automated tests for the application.

    Exits with appropriate exit code based on test results.
    """
    print(f"{BLUE}--- Running Self-Tests ---{RESET}")

    # Try installing with uv first, then fallback to pip
    install_cmd_uv = [sys.executable, "-m", "uv", "pip", "install", "-e", ".[dev]"]
    install_cmd_pip = [sys.executable, "-m", "pip", "install", "-e", ".[dev]"]

    print(f"{BLUE}Attempting to install/update dev dependencies using 'uv'...{RESET}")
    install_success = run_subprocess_command(install_cmd_uv, "uv dev dependency installation")

    if not install_success:
        print(f"{YELLOW}'uv' command failed or not found. Attempting with 'pip'...{RESET}")
        install_success = run_subprocess_command(install_cmd_pip, "pip dev dependency installation")

    if not install_success:
        print(f"{RED}Failed to install dev dependencies. Aborting self-tests.{RESET}")
        sys.exit(1)

    pytest_cmd = ["pytest", "tests/test_mass_find_replace.py"]  # Use system pytest
    print(f"{BLUE}Running pytest...{RESET}")
    test_passed = run_subprocess_command(pytest_cmd, "pytest execution")
    sys.exit(0 if test_passed else 1)
