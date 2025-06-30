#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of argument processing logic from parser.py
# - This module processes and validates parsed arguments
#

"""
Argument processor for the Mass Find Replace CLI.

This module processes and validates parsed command-line arguments.
"""

from __future__ import annotations
import sys
import argparse
from pathlib import Path
from typing import Any, Final

from ...ui.display import RED, YELLOW, BLUE, RESET

# Import constants - duplicated here to avoid circular imports
MAIN_TRANSACTION_FILE_NAME: Final[str] = "planned_transactions.json"

__all__ = ["process_arguments", "validate_timeout", "prepare_exclude_files"]


def validate_timeout(timeout: float, quiet: bool, parser: argparse.ArgumentParser) -> int:
    """Validate and process timeout argument.

    Args:
        timeout: Timeout value from arguments
        quiet: Whether quiet mode is enabled
        parser: ArgumentParser instance for error reporting

    Returns:
        Processed timeout value as integer
    """
    if timeout < 0:
        parser.error("--timeout cannot be negative.")
    if timeout == 0:
        return 0
    elif timeout < 1.0:
        if not quiet:
            print(f"{YELLOW}Warning: --timeout value {timeout} increased to minimum 1 minute.{RESET}")
        return 1
    else:
        return int(timeout)


def prepare_exclude_files(exclude_files: list[str], mapping_file: str) -> list[str]:
    """Prepare the list of files to exclude.

    Args:
        exclude_files: User-provided exclude files
        mapping_file: Path to mapping file

    Returns:
        Final list of files to exclude
    """
    # Import these here to avoid circular imports at runtime
    from ...file_system_operations import (
        BINARY_MATCHES_LOG_FILE,
        COLLISIONS_ERRORS_LOG_FILE,
        TRANSACTION_FILE_BACKUP_EXT,
    )

    auto_exclude_basenames = [
        MAIN_TRANSACTION_FILE_NAME,
        Path(mapping_file).name,
        BINARY_MATCHES_LOG_FILE,
        COLLISIONS_ERRORS_LOG_FILE,
        MAIN_TRANSACTION_FILE_NAME + TRANSACTION_FILE_BACKUP_EXT,
    ]

    # Remove duplicates while preserving order
    seen = set()
    final_exclude_files = []
    for item in exclude_files + auto_exclude_basenames:
        if item not in seen:
            seen.add(item)
            final_exclude_files.append(item)

    return final_exclude_files


def process_arguments(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict[str, Any]:
    """Process and validate parsed arguments.

    Args:
        args: Parsed arguments from argparse
        parser: ArgumentParser instance for error reporting

    Returns:
        Dictionary of processed arguments ready for main_flow
    """
    # Process timeout
    timeout_val = validate_timeout(args.timeout, args.quiet, parser)

    # Validate ignore file if gitignore is enabled
    if args.custom_ignore_file and args.use_gitignore:
        ignore_path = Path(args.custom_ignore_file)
        if not ignore_path.exists() or not ignore_path.is_file():
            sys.stderr.write(f"{RED}Error: Ignore file not found: {args.custom_ignore_file}{RESET}\n")
            sys.exit(1)

    # Prepare exclude files
    final_exclude_files = prepare_exclude_files(args.exclude_files, args.mapping_file)

    # Print verbose mode message
    if args.verbose and not args.quiet:
        print("Verbose mode requested. Prefect log level will be set to DEBUG if flow runs.")

    # Process symlink parameter
    ignore_symlinks_param = not args.process_symlink_names

    return {
        "directory": args.directory,
        "mapping_file": args.mapping_file,
        "extensions": args.extensions,
        "exclude_dirs": args.exclude_dirs,
        "exclude_files": final_exclude_files,
        "dry_run": args.dry_run,
        "skip_scan": args.skip_scan,
        "resume": args.resume,
        "force": args.force,
        "ignore_symlinks": ignore_symlinks_param,
        "use_gitignore": args.use_gitignore,
        "custom_ignore_file": args.custom_ignore_file,
        "skip_file_renaming": args.skip_file_renaming,
        "skip_folder_renaming": args.skip_folder_renaming,
        "skip_content": args.skip_content,
        "timeout": timeout_val,
        "quiet": args.quiet,
        "verbose": args.verbose,
        "interactive": args.interactive,
    }
