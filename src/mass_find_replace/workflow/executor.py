#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of workflow execution logic from mass_find_replace.py
# - This module handles the main workflow execution after validation
#

"""
Workflow executor for the Mass Find Replace application.

This module contains the main workflow execution logic after validation and setup.
"""

from __future__ import annotations

import logging
import pathspec
import sys
from pathlib import Path
from typing import Any

from ..ui.display import (
    GREEN,
    RED,
    YELLOW,
    BLUE,
    DIM,
    RESET,
    print_mapping_table as _print_mapping_table,
    get_operation_description as _get_operation_description,
)
from ..file_system_operations import (
    load_transactions,
    execute_all_transactions,
    BINARY_MATCHES_LOG_FILE,
    COLLISIONS_ERRORS_LOG_FILE,
)
from .. import replace_logic

__all__ = [
    "load_ignore_patterns",
    "get_user_confirmation",
    "execute_workflow",
]


def load_ignore_patterns(
    use_gitignore: bool,
    custom_ignore_file_path: str | None,
    abs_root_dir: Path,
    quiet_mode: bool,
    logger: logging.Logger | logging.LoggerAdapter[logging.Logger],
) -> pathspec.PathSpec | None:
    """Load ignore patterns from gitignore and custom ignore files.

    Args:
        use_gitignore: Whether to use .gitignore file
        custom_ignore_file_path: Path to custom ignore file
        abs_root_dir: Absolute root directory
        quiet_mode: Whether to suppress output
        logger: Logger instance

    Returns:
        PathSpec object or None
    """
    raw_patterns_list: list[str] = []

    if use_gitignore:
        gitignore_path = abs_root_dir / ".gitignore"
        if gitignore_path.is_file():
            if not quiet_mode:
                print(f"{GREEN}✓ Found .gitignore file - exclusion patterns will be applied{RESET}")
            logger.info(f"Using .gitignore file: {gitignore_path}")
            try:
                with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f_git:
                    raw_patterns_list.extend(p for p in (line.strip() for line in f_git) if p and not p.startswith("#"))
            except Exception as e:
                logger.warning(f"{YELLOW}Warning: Could not read .gitignore file {gitignore_path}: {e}{RESET}")
        elif not quiet_mode:
            logger.info(".gitignore not found in root, skipping.")

    if custom_ignore_file_path and use_gitignore:
        custom_ignore_abs_path = Path(custom_ignore_file_path).resolve()
        if custom_ignore_abs_path.is_file():
            logger.info(f"Using custom ignore file: {custom_ignore_abs_path}")
            try:
                with open(custom_ignore_abs_path, "r", encoding="utf-8", errors="ignore") as f_custom:
                    raw_patterns_list.extend(p for p in (line.strip() for line in f_custom) if p and not p.startswith("#"))
            except Exception as e:
                logger.warning(f"{YELLOW}Warning: Could not read custom ignore file {custom_ignore_abs_path}: {e}{RESET}")
        else:
            logger.error(f"Ignore file not found: {custom_ignore_abs_path}. Aborting")
            return None

    if raw_patterns_list:
        try:
            final_ignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", raw_patterns_list)
            logger.info(f"Loaded {len(raw_patterns_list)} ignore patterns rules from specified files.")
            return final_ignore_spec
        except Exception as e:
            logger.error(f"Error compiling combined ignore patterns: {e}")

    return None


def get_user_confirmation(
    abs_root_dir: Path,
    map_file_path: Path,
    extensions: list[str] | None,
    exclude_dirs: list[str],
    exclude_files: list[str],
    use_gitignore: bool,
    custom_ignore_file_path: str | None,
    final_ignore_spec: pathspec.PathSpec | None,
    ignore_symlinks_arg: bool,
    skip_file_renaming: bool,
    skip_folder_renaming: bool,
    skip_content: bool,
    timeout_minutes: int,
    dry_run: bool,
    force_execution: bool,
    resume: bool,
    quiet_mode: bool,
    interactive_mode: bool,
    replacement_mapping: dict[str, str],
) -> bool:
    """Get user confirmation for the operation.

    Returns:
        True if user confirms, False otherwise
    """
    # Confirmation prompt. Suppressed by dry_run, force_execution, resume, quiet_mode, or interactive_mode.
    if not dry_run and not force_execution and not resume and not quiet_mode and not interactive_mode:
        print(f"{BLUE}--- Proposed Operation ---{RESET}")
        print(f"Root Directory: {abs_root_dir}")
        print(f"Replacement Map File: {map_file_path}")
        mapping_size = replace_logic.get_mapping_size()
        if mapping_size > 0:
            print(f"Loaded {mapping_size} replacement rules.")
        else:
            print("Replacement map is empty. No string replacements will occur.")
        print(f"File Extensions for content scan: {extensions if extensions else 'All non-binary (heuristic)'}")
        print(f"Exclude Dirs (explicit): {exclude_dirs}")
        print(f"Exclude Files (explicit): {exclude_files}")
        if use_gitignore:
            print(f"Using .gitignore: Yes (if found at {abs_root_dir / '.gitignore'})")
        if custom_ignore_file_path:
            print(f"Custom Ignore File: {custom_ignore_file_path}")
        if final_ignore_spec:
            print(f"Effective ignore patterns: {len(final_ignore_spec.patterns)} compiled from ignore files.")

        symlink_processing_message = "Symlinks will be ignored (names not renamed, targets not processed for content)." if ignore_symlinks_arg else "Symlink names WILL BE PROCESSED for renaming; targets not processed for content."
        print(f"Symlink Handling: {symlink_processing_message}")

        print(f"Skip File Renaming: {skip_file_renaming}")
        print(f"Skip Folder Renaming: {skip_folder_renaming}")
        print(f"Skip Content Modification: {skip_content}")
        print(f"Retry Timeout: {timeout_minutes} minutes (0 for indefinite retries)")
        print(f"{BLUE}-------------------------{RESET}")
        sys.stdout.flush()

        if not replacement_mapping and (skip_file_renaming or not extensions) and (skip_folder_renaming or not extensions) and skip_content:
            print(f"{YELLOW}Warning: No replacement rules and no operations enabled that don't require rules. Likely no operations will be performed.{RESET}")

        confirm = input("Proceed with these changes? (yes/no): ")
        if confirm.lower() != "yes":
            print("Operation cancelled by user.")
            return False

    return True


def execute_workflow(
    abs_root_dir: Path,
    txn_json_path: Path,
    final_ignore_spec: pathspec.PathSpec | None,
    extensions: list[str] | None,
    exclude_dirs: list[str],
    exclude_files: list[str],
    skip_scan: bool,
    resume: bool,
    dry_run: bool,
    skip_file_renaming: bool,
    skip_folder_renaming: bool,
    skip_content: bool,
    timeout_minutes: int,
    quiet_mode: bool,
    interactive_mode: bool,
    logger: logging.Logger | logging.LoggerAdapter[logging.Logger],
) -> None:
    """Execute the main workflow after validation and confirmation.

    Args:
        abs_root_dir: Absolute root directory
        txn_json_path: Path to transaction JSON file
        final_ignore_spec: Ignore patterns spec
        extensions: File extensions to process
        exclude_dirs: Directories to exclude
        exclude_files: Files to exclude
        skip_scan: Whether to skip scanning phase
        resume: Whether to resume from existing transaction file
        dry_run: Whether this is a dry run
        skip_file_renaming: Whether to skip file renaming
        skip_folder_renaming: Whether to skip folder renaming
        skip_content: Whether to skip content modification
        timeout_minutes: Timeout for retries
        quiet_mode: Whether to suppress output
        interactive_mode: Whether to run in interactive mode
        logger: Logger instance
    """
    # Clear old collision log if starting fresh (but NOT the binary log - that's created during scan!)
    if not resume and not skip_scan:
        collision_log_path = abs_root_dir / COLLISIONS_ERRORS_LOG_FILE
        if collision_log_path.exists():
            try:
                collision_log_path.unlink()
                logger.debug(f"Cleared old collision log file: {collision_log_path}")
            except Exception as e:
                logger.warning(f"Could not clear collision log file {collision_log_path}: {e}")

    # Load transactions (already created by perform_scan_phase)
    if not txn_json_path.exists():
        logger.error(f"Transaction file not found: {txn_json_path}")
        return

    transactions = load_transactions(txn_json_path, logger=logger)
    if transactions is None:
        logger.error("Failed to load transaction file.")
        return

    if not quiet_mode:
        print(f"\n{BLUE}=== Phase 1/3: Scanning complete ==={RESET}")
        print(f"{GREEN}✓ Found {len(transactions)} potential changes.{RESET}")

    # Phase 2: Plan (display what will be done)
    if not quiet_mode:
        print(f"\n{BLUE}=== Phase 2/3: Planning changes ==={RESET}")
        total_tx = len(transactions) if transactions else 0
        rename_tx = sum(1 for tx in transactions if tx["TYPE"] in ["FILE_NAME", "FOLDER_NAME"]) if transactions else 0
        content_tx = sum(1 for tx in transactions if tx["TYPE"] == "FILE_CONTENT_LINE") if transactions else 0

        print(f"Total transactions: {total_tx}")
        print(f"  - Rename operations: {rename_tx}")
        print(f"  - Content modifications: {content_tx}")

        if dry_run:
            print(f"\n{DIM}This is a DRY RUN - no changes will be made{RESET}")

    # Phase 3: Execute (unless dry_run)
    if not quiet_mode:
        print(f"\n{BLUE}=== Phase 3/3: Executing changes ==={RESET}")

    if dry_run and not quiet_mode:
        print(f"{YELLOW}DRY RUN: Simulating execution...{RESET}")

    stats = execute_all_transactions(
        txn_json_path,
        abs_root_dir,
        dry_run,
        resume,
        timeout_minutes,
        skip_file_renaming,
        skip_folder_renaming,
        skip_content,
        interactive_mode,
        logger,
    )

    # Display summary
    if not quiet_mode and stats:
        print(f"\n{BLUE}=== Execution Summary ==={RESET}")
        print(f"Total transactions: {stats.get('total', 0)}")
        print(f"{GREEN}Completed: {stats.get('completed', 0)}{RESET}")
        print(f"{YELLOW}Skipped: {stats.get('skipped', 0)}{RESET}")
        print(f"{RED}Failed: {stats.get('failed', 0)}{RESET}")
        if stats.get("retry_later", 0) > 0:
            print(f"{YELLOW}Retry later: {stats.get('retry_later', 0)}{RESET}")

    # Display warnings about logs
    binary_log = abs_root_dir / BINARY_MATCHES_LOG_FILE
    collisions_log = abs_root_dir / COLLISIONS_ERRORS_LOG_FILE

    if binary_log.exists() and binary_log.stat().st_size > 0:
        logger.info(f"{YELLOW}Info: Matches found in binary files. See '{binary_log}' for details. Binary files were not modified.{RESET}")

    if collisions_log.exists() and collisions_log.stat().st_size > 0:
        logger.info(f"{RED}Warning: File/folder rename collisions were detected. See '{collisions_log}' for details. These renames were skipped.{RESET}")
