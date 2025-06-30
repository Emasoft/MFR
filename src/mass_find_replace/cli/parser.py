#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of main_cli from mass_find_replace.py
# - This module contains the command-line interface and argument parsing
# - Refactored to use parser_modules for better organization
#

"""
Command-line interface parser for Mass Find Replace.

This module provides the main CLI entry point and argument parsing functionality.
"""

from __future__ import annotations

from typing import Final

# Import color codes from ui module
from ..ui.display import BLUE, RESET

# Import from parser submodules
from .parser_modules.dependency_checker import check_required_dependencies
from .parser_modules.self_test import run_self_tests
from .parser_modules.argument_parser import create_argument_parser
from .parser_modules.argument_processor import process_arguments

# Import constants - duplicated here to avoid circular imports
SCRIPT_NAME: Final[str] = "MFR - Mass Find Replace - A script to safely rename things in your project"

__all__ = ["main_cli"]


def main_cli() -> None:
    """Main CLI entry point for mass find replace."""
    # Check required dependencies
    check_required_dependencies()

    # Create and parse arguments
    parser = create_argument_parser()
    args = parser.parse_args()

    # Handle self-test mode
    if args.self_test:
        run_self_tests()

    # Print script name if not quiet
    if not args.quiet:
        print(f"{BLUE}{SCRIPT_NAME}{RESET}")

    # Process arguments
    processed_args = process_arguments(args, parser)

    # Import main_flow here to avoid circular imports
    from ..mass_find_replace import main_flow

    main_flow(
        processed_args["directory"],
        processed_args["mapping_file"],
        processed_args["extensions"],
        processed_args["exclude_dirs"],
        processed_args["exclude_files"],
        processed_args["dry_run"],
        processed_args["skip_scan"],
        processed_args["resume"],
        processed_args["force"],
        processed_args["ignore_symlinks"],
        processed_args["use_gitignore"],
        processed_args["custom_ignore_file"],
        processed_args["skip_file_renaming"],
        processed_args["skip_folder_renaming"],
        processed_args["skip_content"],
        processed_args["timeout"],
        processed_args["quiet"],
        processed_args["verbose"],
        processed_args["interactive"],
    )
