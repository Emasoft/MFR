#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE CODE:
# - Consolidated redundant empty map checks into a single check in main_flow.
# - Removed unused skip_scan parameter from execute_all_transactions call.
# - Added explicit flushing of Prefect's log handler after subprocess output printing to avoid Prefect shutdown logging errors.
# - Replaced bare except with except Exception to comply with linting rules.
# - Extracted CLI functionality to cli/parser.py module.
# - Extracted display functions to ui/display.py module.
# - Extracted validation functions to workflow/validation.py module.
#
# Copyright (c) 2024 Emasoft
#
# This software is licensed under the MIT License.
# Refer to the LICENSE file for more details.

from __future__ import annotations

import sys
from pathlib import Path

from prefect import flow

from . import replace_logic
from .ui.display import (
    print_mapping_table as _print_mapping_table,
    get_operation_description as _get_operation_description,
    RED,
    RESET,
    YELLOW,
    BLUE,
    DIM,
)
from .workflow.validation import (
    check_existing_transactions as _check_existing_transactions,
    validate_directory,
    validate_mapping_file,
)
from .workflow.executor import (
    load_ignore_patterns,
    get_user_confirmation,
    execute_workflow,
)
from .workflow.scanner import perform_scan_phase
from .utils.logger import get_logger as _get_logger

# Import constants from core.config
from .core.config import (
    SCRIPT_NAME,
    MAIN_TRANSACTION_FILE_NAME,
    DEFAULT_REPLACEMENT_MAPPING_FILE,
)


# The logger function has been moved to utils.logger module


# The display and validation functions have been moved to their respective modules:
# - _print_mapping_table -> ui.display.print_mapping_table
# - _get_operation_description -> ui.display.get_operation_description
# - _check_existing_transactions -> workflow.validation.check_existing_transactions


@flow(name="Mass Find Replace")
def main_flow(
    directory: str,
    mapping_file: str,
    extensions: list[str] | None,
    exclude_dirs: list[str],
    exclude_files: list[str],
    dry_run: bool,
    skip_scan: bool,
    resume: bool,
    force_execution: bool,
    ignore_symlinks_arg: bool,
    use_gitignore: bool,
    custom_ignore_file_path: str | None,
    skip_file_renaming: bool,
    skip_folder_renaming: bool,
    skip_content: bool,
    timeout_minutes: int,
    quiet_mode: bool,
    verbose_mode: bool,
    interactive_mode: bool,
) -> None:
    """Main workflow for mass find and replace operations.

    Args:
        directory: Root directory to process
        mapping_file: Path to JSON file with replacement mappings
        extensions: List of file extensions for content scan
        exclude_dirs: Directory names to exclude
        exclude_files: Files or relative paths to exclude
        dry_run: Simulate changes without executing them
        skip_scan: Use existing transaction file for execution
        resume: Resume from existing transaction file
        force_execution: Skip confirmation prompt
        ignore_symlinks_arg: Whether to ignore symlinks
        use_gitignore: Use .gitignore file for exclusions
        custom_ignore_file_path: Path to custom ignore file
        skip_file_renaming: Skip all file renaming operations
        skip_folder_renaming: Skip all folder renaming operations
        skip_content: Skip all file content modifications
        timeout_minutes: Maximum minutes for retry phase
        quiet_mode: Suppress informational messages
        verbose_mode: Enable verbose output
        interactive_mode: Prompt for approval before each change
    """

    logger = _get_logger(verbose_mode)


    if verbose_mode:
        logger.debug("Verbose mode enabled.")

    # Explicitly reset replace_logic module state before any operations for this flow run
    replace_logic.reset_module_state()

    # Validate and normalize the directory path
    abs_root_dir = validate_directory(directory, logger)
    if abs_root_dir is None:
        return

    # Check for existing incomplete transactions
    if not quiet_mode and not resume and not skip_scan:
        has_existing, progress = _check_existing_transactions(abs_root_dir, logger)
        if has_existing:
            print(f"\n{YELLOW}An incomplete previous run was detected ({progress}% completed).{RESET}")
            choice = input("Do you want to resume it? (y/n): ").strip().lower()
            if choice == "y":
                resume = True
                logger.info("Resuming previous run...")
            else:
                # Clear the existing transaction file
                txn_file = abs_root_dir / MAIN_TRANSACTION_FILE_NAME
                try:
                    if txn_file.exists():
                        txn_file.unlink()
                        logger.info("Previous transaction file cleared.")
                except Exception as e:
                    logger.error(f"Error clearing transaction file: {e}")
                    return

    if skip_file_renaming and skip_folder_renaming and skip_content:
        logger.info("All processing types (file rename, folder rename, content) are skipped. Nothing to do.")
        return

    # Empty directory check is already done in validate_directory

    # Validate mapping file path
    map_file_path = validate_mapping_file(mapping_file, logger)
    if map_file_path is None:
        return

    if not replace_logic.load_replacement_map(map_file_path, logger=logger):
        logger.error(f"Aborting due to issues with replacement mapping file: {map_file_path}")
        return

    # Type-safety reinforcement
    if not replace_logic.is_mapping_loaded():
        logger.error(f"Critical Error: Map {map_file_path} not loaded by replace_logic.")
        return

    # Display mapping table and get confirmation (unless in quiet mode or force mode)
    replacement_mapping = replace_logic.get_replacement_mapping()
    if not quiet_mode and not force_execution and replacement_mapping:
        _print_mapping_table(replacement_mapping, logger)

        operations_desc = _get_operation_description(skip_file_renaming, skip_folder_renaming, skip_content)
        print(f"\n{BLUE}This will replace the strings in the 'Search' column with those in the 'Replace' column.{RESET}")
        print(f"{BLUE}Operations will be performed on: {operations_desc}{RESET}")

        if dry_run:
            print(f"{DIM}(DRY RUN - no actual changes will be made){RESET}")

        confirm = input("\nDo you want to proceed? (y/n): ").strip().lower()
        if confirm != "y":
            logger.info("Operation cancelled by user.")
            return

    # Consolidated empty map check
    if not replacement_mapping:
        if not (skip_file_renaming or skip_folder_renaming or skip_content):
            logger.info("Map is empty and no operations are configured that would proceed without map rules. Nothing to execute.")
            return
        logger.info("Map is empty. No string-based replacements will occur.")

    elif not replace_logic.get_scan_pattern() and replacement_mapping:
        logger.error("Critical Error: Map loaded but scan regex pattern compilation failed or resulted in no patterns.")
        return

    txn_json_path: Path = abs_root_dir / MAIN_TRANSACTION_FILE_NAME

    # Load ignore patterns
    final_ignore_spec = load_ignore_patterns(use_gitignore, custom_ignore_file_path, abs_root_dir, quiet_mode, logger)
    if custom_ignore_file_path and use_gitignore and final_ignore_spec is None:
        # load_ignore_patterns already logged the error
        return

    # Get user confirmation
    if not get_user_confirmation(
        abs_root_dir,
        map_file_path,
        extensions,
        exclude_dirs,
        exclude_files,
        use_gitignore,
        custom_ignore_file_path,
        final_ignore_spec,
        ignore_symlinks_arg,
        skip_file_renaming,
        skip_folder_renaming,
        skip_content,
        timeout_minutes,
        dry_run,
        force_execution,
        resume,
        quiet_mode,
        interactive_mode,
        replacement_mapping,
    ):
        logger.info("Operation cancelled by user.")
        return

    # Perform scan phase
    transactions = perform_scan_phase(
        abs_root_dir,
        txn_json_path,
        skip_scan,
        resume,
        dry_run,
        extensions,
        exclude_dirs,
        exclude_files,
        ignore_symlinks_arg,
        final_ignore_spec,
        skip_file_renaming,
        skip_folder_renaming,
        skip_content,
        replacement_mapping,
        logger,
    )

    if transactions is None:
        return

    # Execute workflow
    execute_workflow(
        abs_root_dir,
        txn_json_path,
        final_ignore_spec,
        extensions,
        exclude_dirs,
        exclude_files,
        skip_scan,
        resume,
        dry_run,
        skip_file_renaming,
        skip_folder_renaming,
        skip_content,
        timeout_minutes,
        quiet_mode,
        interactive_mode,
        logger,
    )


# The CLI functions have been moved to their respective modules:
# - main_cli -> cli.parser.main_cli
# - _run_subprocess_command -> cli.parser._run_subprocess_command


# Export main components
__all__ = [
    "main_flow",
    "SCRIPT_NAME",
    "MAIN_TRANSACTION_FILE_NAME",
    "DEFAULT_REPLACEMENT_MAPPING_FILE",
]


if __name__ == "__main__":
    import sys
    import traceback
    from .cli.parser import main_cli

    try:
        main_cli()
    except Exception as e:
        sys.stderr.write(RED + f"An unexpected error occurred in __main__: {e}" + RESET + "\n")
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)
