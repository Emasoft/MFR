#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of dependency checking from parser.py
# - This module verifies required dependencies are installed
#

"""
Dependency checker for the Mass Find Replace CLI.

This module provides functionality for checking that required
dependencies are installed before running the application.
"""

from __future__ import annotations
import sys
import importlib.util

from ...ui.display import RED, RESET

__all__ = ["check_required_dependencies"]


def check_required_dependencies() -> None:
    """Check that all required dependencies are installed.

    Exits with error code 1 if any dependencies are missing.
    """
    required_deps = [("prefect", "prefect"), ("chardet", "chardet")]
    for module_name, display_name in required_deps:
        try:
            if importlib.util.find_spec(module_name) is None:
                sys.stderr.write(f"{RED}CRITICAL ERROR: Missing core dependency: {display_name}. Please install all required packages (e.g., via 'uv sync').{RESET}\n")
                sys.exit(1)
        except ImportError:
            sys.stderr.write(f"{RED}CRITICAL ERROR: Missing core dependency: {display_name} (import error during check). Please install all required packages.{RESET}\n")
            sys.exit(1)
