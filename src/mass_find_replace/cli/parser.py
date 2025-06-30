#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of main_cli from mass_find_replace.py
# - This module contains the command-line interface and argument parsing
#

"""
Command-line interface parser for Mass Find Replace.

This module provides the main CLI entry point and argument parsing functionality.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

# Import color codes from ui module
from ..ui.display import (
    GREEN,
    RED,
    YELLOW,
    BLUE,
    DIM,
    RESET,
)

# Import constants - duplicated here to avoid circular imports
SCRIPT_NAME: Final[str] = "MFR - Mass Find Replace - A script to safely rename things in your project"
MAIN_TRANSACTION_FILE_NAME: Final[str] = "planned_transactions.json"
DEFAULT_REPLACEMENT_MAPPING_FILE: Final[str] = "replacement_mapping.json"

__all__ = ["main_cli"]


def _run_subprocess_command(command: list[str], description: str) -> bool:
    """Run a subprocess command and handle output.

    Args:
        command: Command to run
        description: Description of what the command does

    Returns:
        True if command succeeded, False otherwise
    """
    import subprocess

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return True
    except subprocess.CalledProcessError as e:
        print(f"{RED}Failed during {description}: {e}{RESET}", file=sys.stderr)
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        return False
    except FileNotFoundError:
        print(f"{RED}Command not found during {description}: {command[0]}{RESET}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"{RED}Unexpected error during {description}: {e}{RESET}", file=sys.stderr)
        return False


def main_cli() -> None:
    """Main CLI entry point for mass find replace."""
    import importlib.util

    # Check required dependencies
    required_deps = [("prefect", "prefect"), ("chardet", "chardet")]
    for module_name, display_name in required_deps:
        try:
            if importlib.util.find_spec(module_name) is None:
                sys.stderr.write(f"{RED}CRITICAL ERROR: Missing core dependency: {display_name}. Please install all required packages (e.g., via 'uv sync').{RESET}\n")
                sys.exit(1)
        except ImportError:
            sys.stderr.write(f"{RED}CRITICAL ERROR: Missing core dependency: {display_name} (import error during check). Please install all required packages.{RESET}\n")
            sys.exit(1)

    # Import constant at runtime to avoid circular imports
    from ..file_system_operations import BINARY_MATCHES_LOG_FILE

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

    args = parser.parse_args()

    if args.self_test:
        print(f"{BLUE}--- Running Self-Tests ---{RESET}")

        # Try installing with uv first, then fallback to pip
        install_cmd_uv = [sys.executable, "-m", "uv", "pip", "install", "-e", ".[dev]"]
        install_cmd_pip = [sys.executable, "-m", "pip", "install", "-e", ".[dev]"]

        print(f"{BLUE}Attempting to install/update dev dependencies using 'uv'...{RESET}")
        install_success = _run_subprocess_command(install_cmd_uv, "uv dev dependency installation")

        if not install_success:
            print(f"{YELLOW}'uv' command failed or not found. Attempting with 'pip'...{RESET}")
            install_success = _run_subprocess_command(install_cmd_pip, "pip dev dependency installation")

        if not install_success:
            print(f"{RED}Failed to install dev dependencies. Aborting self-tests.{RESET}")
            sys.exit(1)

        pytest_cmd = ["pytest", "tests/test_mass_find_replace.py"]  # Use system pytest
        print(f"{BLUE}Running pytest...{RESET}")
        test_passed = _run_subprocess_command(pytest_cmd, "pytest execution")
        sys.exit(0 if test_passed else 1)

    if not args.quiet:
        print(f"{BLUE}{SCRIPT_NAME}{RESET}")

    timeout_val_for_flow: int
    if args.timeout < 0:
        parser.error("--timeout cannot be negative.")
    if args.timeout == 0:
        timeout_val_for_flow = 0
    elif args.timeout < 1.0:
        if not args.quiet:
            print(f"{YELLOW}Warning: --timeout value {args.timeout} increased to minimum 1 minute.{RESET}")
        timeout_val_for_flow = 1
    else:
        timeout_val_for_flow = int(args.timeout)

    # Validate ignore file if gitignore is enabled
    if args.custom_ignore_file and args.use_gitignore:
        ignore_path = Path(args.custom_ignore_file)
        if not ignore_path.exists() or not ignore_path.is_file():
            sys.stderr.write(f"{RED}Error: Ignore file not found: {args.custom_ignore_file}{RESET}\n")
            sys.exit(1)

    # Import these here to avoid circular imports at runtime
    from ..file_system_operations import (
        BINARY_MATCHES_LOG_FILE,
        COLLISIONS_ERRORS_LOG_FILE,
        TRANSACTION_FILE_BACKUP_EXT,
    )

    auto_exclude_basenames = [
        MAIN_TRANSACTION_FILE_NAME,
        Path(args.mapping_file).name,
        BINARY_MATCHES_LOG_FILE,
        COLLISIONS_ERRORS_LOG_FILE,
        MAIN_TRANSACTION_FILE_NAME + TRANSACTION_FILE_BACKUP_EXT,
    ]
    # Remove duplicates while preserving order
    seen = set()
    final_exclude_files = []
    for item in args.exclude_files + auto_exclude_basenames:
        if item not in seen:
            seen.add(item)
            final_exclude_files.append(item)

    if args.verbose and not args.quiet:
        print("Verbose mode requested. Prefect log level will be set to DEBUG if flow runs.")

    ignore_symlinks_param = not args.process_symlink_names

    # Import main_flow here to avoid circular imports
    from ..mass_find_replace import main_flow

    main_flow(
        args.directory,
        args.mapping_file,
        args.extensions,
        args.exclude_dirs,
        final_exclude_files,
        args.dry_run,
        args.skip_scan,
        args.resume,
        args.force,
        ignore_symlinks_param,
        args.use_gitignore,
        args.custom_ignore_file,
        args.skip_file_renaming,
        args.skip_folder_renaming,
        args.skip_content,
        timeout_val_for_flow,
        args.quiet,
        args.verbose,
        args.interactive,
    )
