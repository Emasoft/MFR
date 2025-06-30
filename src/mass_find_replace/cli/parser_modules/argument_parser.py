#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of argument parser creation from parser.py
# - This module creates and configures the argparse parser
#

"""
Argument parser configuration for the Mass Find Replace CLI.

This module provides the argparse configuration with all command-line options.
"""

from __future__ import annotations
import argparse
from typing import Final

# Import constants - duplicated here to avoid circular imports
SCRIPT_NAME: Final[str] = "MFR - Mass Find Replace - A script to safely rename things in your project"
MAIN_TRANSACTION_FILE_NAME: Final[str] = "planned_transactions.json"
DEFAULT_REPLACEMENT_MAPPING_FILE: Final[str] = "replacement_mapping.json"

__all__ = ["create_argument_parser"]


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    # Import constant at runtime to avoid circular imports
    from ...file_system_operations import BINARY_MATCHES_LOG_FILE

    parser = argparse.ArgumentParser(
        description=f"{SCRIPT_NAME}\nFind and replace strings in files and filenames/foldernames within a project directory. "
        "It operates in three phases: Scan, Plan (creating a transaction log), and Execute. "
        "The process is designed to be resumable and aims for surgical precision in replacements. "
        f"Binary file content is NOT modified; matches within them are logged to '{BINARY_MATCHES_LOG_FILE}'.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Root directory to process (default: current directory).",
    )
    parser.add_argument(
        "--mapping-file",
        default=DEFAULT_REPLACEMENT_MAPPING_FILE,
        help=f"Path to the JSON file with replacement mappings (default: ./{DEFAULT_REPLACEMENT_MAPPING_FILE}).",
    )
    parser.add_argument(
        "--extensions",
        nargs="+",
        help="List of file extensions for content scan (e.g. .py .txt .rtf). Default: attempts to process recognized text-like files.",
    )
    parser.add_argument(
        "--exclude-dirs",
        nargs="+",
        default=[".git", ".venv", "venv", "node_modules", "__pycache__"],
        help="Directory names to exclude (space-separated). Default: .git .venv etc.",
    )
    parser.add_argument(
        "--exclude-files",
        nargs="+",
        default=[],
        help="Specific files or relative paths to exclude (space-separated).",
    )

    ignore_group = parser.add_argument_group("Ignore File Options")
    ignore_group.add_argument(
        "--no-gitignore",
        action="store_false",
        dest="use_gitignore",
        default=True,
        help="Disable using .gitignore file for exclusions. Custom ignore files will also be skipped.",
    )
    ignore_group.add_argument(
        "--ignore-file",
        dest="custom_ignore_file",
        metavar="PATH",
        help="Path to a custom .gitignore-style file for additional exclusions.",
    )

    symlink_group = parser.add_argument_group("Symlink Handling")
    symlink_group.add_argument(
        "--process-symlink-names",
        action="store_true",
        help="If set, symlink names WILL BE PROCESSED for renaming. Default: symlink names are NOT processed for renaming. Symlink targets are never followed for content modification by this script.",
    )

    skip_group = parser.add_argument_group("Skip Operation Options")
    skip_group.add_argument(
        "--skip-file-renaming",
        action="store_true",
        help="Skip all file renaming operations.",
    )
    skip_group.add_argument(
        "--skip-folder-renaming",
        action="store_true",
        help="Skip all folder renaming operations.",
    )
    skip_group.add_argument(
        "--skip-content",
        action="store_true",
        help="Skip all file content modifications. If all three --skip-* options are used, the script will exit with 'nothing to do'.",
    )

    execution_group = parser.add_argument_group("Execution Control")
    execution_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and plan changes, but do not execute them. Reports what would be changed.",
    )
    execution_group.add_argument(
        "--skip-scan",
        action="store_true",
        help=f"Skip scan phase; use existing '{MAIN_TRANSACTION_FILE_NAME}' in the root directory for execution.",
    )
    execution_group.add_argument(
        "--resume",
        action="store_true",
        help="Resume operation from existing transaction file, attempting to complete pending/failed items and scan for new/modified ones.",
    )
    execution_group.add_argument(
        "--force",
        "--yes",
        "-y",
        action="store_true",
        help="Force execution without confirmation prompt (use with caution).",
    )
    execution_group.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        help="Run in interactive mode, prompting for approval before each change.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        metavar="MINUTES",
        help="Maximum minutes for the retry phase when files are locked/inaccessible. Set to 0 for indefinite retries (until CTRL-C). Minimum 1 minute if not 0. Default: 10 minutes.",
    )

    output_group = parser.add_argument_group("Output Control")
    output_group.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress initial script name print and some informational messages from direct print statements (Prefect logs are separate). Also suppresses the confirmation prompt, implying 'yes'.",
    )
    output_group.add_argument(
        "--verbose",
        action="store_true",
        help="Enable more verbose output, setting Prefect logger to DEBUG level.",
    )

    dev_group = parser.add_argument_group("Developer Options")
    dev_group.add_argument("--self-test", action="store_true", help="Run automated tests for this script.")

    return parser
