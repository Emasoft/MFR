#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of subprocess running functionality from parser.py
# - This module handles running subprocess commands with error handling
#

"""
Subprocess runner for the Mass Find Replace CLI.

This module provides functionality for running subprocess commands
with proper output and error handling.
"""

from __future__ import annotations
import sys
import subprocess

from ...ui.display import RED

__all__ = ["run_subprocess_command"]


def run_subprocess_command(command: list[str], description: str) -> bool:
    """Run a subprocess command and handle output.

    Args:
        command: Command to run
        description: Description of what the command does

    Returns:
        True if command succeeded, False otherwise
    """
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"{RED}Failed during {description}: {e}", file=sys.stderr)
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        return False
    except FileNotFoundError:
        print(f"{RED}Command not found during {description}: {command[0]}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"{RED}Unexpected error during {description}: {e}", file=sys.stderr)
        return False
