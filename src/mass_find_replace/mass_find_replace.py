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

import logging
import sys
from pathlib import Path
from typing import Any, Final

from prefect import flow

from . import replace_logic
from .file_system_operations import (
    load_transactions,
    save_transactions,
    TransactionStatus,
    TRANSACTION_FILE_BACKUP_EXT,
    BINARY_MATCHES_LOG_FILE,
    COLLISIONS_ERRORS_LOG_FILE,
)
from .ui.display import (
    print_mapping_table as _print_mapping_table,
    get_operation_description as _get_operation_description,
    GREEN,
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

SCRIPT_NAME: Final[str] = "MFR - Mass Find Replace - A script to safely rename things in your project"
MAIN_TRANSACTION_FILE_NAME: Final[str] = "planned_transactions.json"
DEFAULT_REPLACEMENT_MAPPING_FILE: Final[str] = "replacement_mapping.json"


def _get_logger(
    verbose_mode: bool = False,
) -> logging.Logger | logging.LoggerAdapter[logging.Logger]:
    """Get logger with appropriate configuration."""
    import logging

    try:
        # Try to get Prefect's context logger
        from prefect import get_run_logger
        from prefect.exceptions import MissingContextError

        try:
            logger: logging.Logger | logging.LoggerAdapter[logging.Logger] = get_run_logger()
            if verbose_mode:
                logger.setLevel(logging.DEBUG)
            # Type annotation helps mypy understand the logger type
            return logger
        except MissingContextError:
            pass
    except ImportError:
        pass

    # Create standard logger
    logger = logging.getLogger("mass_find_replace")
    logger.setLevel(logging.DEBUG if verbose_mode else logging.INFO)
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger


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
    from pathlib import Path
    import pathspec

    logger = _get_logger(verbose_mode)

    from .file_system_operations import (
        scan_directory_for_occurrences,
        execute_all_transactions,
    )

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
    final_ignore_spec: pathspec.PathSpec | None = None
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
            return
    if raw_patterns_list:
        try:
            final_ignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", raw_patterns_list)
            logger.info(f"Loaded {len(raw_patterns_list)} ignore patterns rules from specified files.")
        except Exception as e:
            logger.error(f"Error compiling combined ignore patterns: {e}")
            final_ignore_spec = None

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
            logger.info("Operation cancelled by user via prompt.")
            return

    if not skip_scan:
        logger.info(f"Scanning '{abs_root_dir}'...")
        current_txns_for_resume: list[dict[str, Any]] | None = None
        paths_to_force_rescan: set[str] | None = set()
        if resume and txn_json_path.exists():
            logger.info(f"Resume: Loading existing txns from {txn_json_path}...")
            current_txns_for_resume = load_transactions(txn_json_path, logger=logger)
            if not skip_scan and dry_run:
                # Always force rescan when resuming dry run
                logger.info("Resume+dry_run: Forcing full rescan of modified files")
                paths_to_force_rescan = None  # None means rescan everything
            if current_txns_for_resume is None:
                logger.warning(f"{YELLOW}Warn: Could not load txns. Fresh scan.{RESET}")
            elif not current_txns_for_resume:
                logger.warning(f"{YELLOW}Warn: Txn file empty. Fresh scan.{RESET}")
            else:
                logger.info("Checking for files modified since last processing...")
                path_last_processed_time: dict[str, float] = {}
                for tx in current_txns_for_resume:
                    tx_ts = tx.get("timestamp_processed", 0.0)
                    if (
                        tx.get("STATUS")
                        in [
                            TransactionStatus.COMPLETED.value,
                            TransactionStatus.FAILED.value,
                        ]
                        and tx_ts > 0
                    ):
                        path_last_processed_time[tx["PATH"]] = max(path_last_processed_time.get(tx["PATH"], 0.0), tx_ts)

                for item_fs in abs_root_dir.rglob("*"):
                    try:
                        if item_fs.is_file() and not item_fs.is_symlink():
                            rel_p = str(item_fs.relative_to(abs_root_dir)).replace("\\", "/")
                            if final_ignore_spec and final_ignore_spec.match_file(rel_p):
                                continue
                            mtime = item_fs.stat().st_mtime
                            if rel_p in path_last_processed_time and mtime > path_last_processed_time[rel_p]:
                                logger.info(f"File '{rel_p}' (mtime:{mtime:.0f}) modified after last process (ts:{path_last_processed_time[rel_p]:.0f}). Re-scan.")
                                if paths_to_force_rescan is not None:
                                    paths_to_force_rescan.add(rel_p)
                    except OSError as e:
                        logger.warning(f"Could not access or stat {item_fs} during resume check: {e}")
                    except Exception as e:
                        logger.warning(f"Unexpected error processing {item_fs} during resume check: {e}")

        found_txns = scan_directory_for_occurrences(
            root_dir=abs_root_dir,
            excluded_dirs=exclude_dirs,
            excluded_files=exclude_files,
            file_extensions=extensions,
            ignore_symlinks=ignore_symlinks_arg,
            ignore_spec=final_ignore_spec,
            resume_from_transactions=current_txns_for_resume if resume else None,
            paths_to_force_rescan=paths_to_force_rescan if resume else None,
            skip_file_renaming=skip_file_renaming,
            skip_folder_renaming=skip_folder_renaming,
            skip_content=skip_content,
            logger=logger,
        )

        save_transactions(found_txns or [], txn_json_path, logger=logger)
        logger.info(f"Scan complete. {len(found_txns or [])} transactions planned in '{txn_json_path}'")
        if not found_txns:
            logger.info("No actionable occurrences found by scan." if replacement_mapping else "Map empty and no scannable items found, or all items ignored.")
            return
    elif not txn_json_path.exists():
        logger.error(f"Error: --skip-scan used, but '{txn_json_path}' not found.")
        return
    else:
        logger.info(f"Using existing transaction file: '{txn_json_path}'. Ensure it was generated with compatible settings.")

    txns_for_exec = load_transactions(txn_json_path, logger=logger)
    if not txns_for_exec:
        logger.info(f"No transactions found in {txn_json_path} to execute. Exiting.")
        return

    # Validate transaction structure
    required_fields = ["id", "TYPE", "PATH", "STATUS"]
    for tx in txns_for_exec:
        missing_fields = [f for f in required_fields if f not in tx]
        if missing_fields:
            logger.error(f"Invalid transaction missing fields {missing_fields}: {tx}")
            return

    # Reset DRY_RUN completed transactions to PENDING for resume
    for tx in txns_for_exec:
        if tx["STATUS"] == TransactionStatus.COMPLETED.value and tx.get("ERROR_MESSAGE") == "DRY_RUN":
            tx["STATUS"] = TransactionStatus.PENDING.value
            tx.pop("ERROR_MESSAGE", None)

    op_type = "Dry run" if dry_run else "Execution"
    logger.info(f"{op_type}: Simulating execution of transactions..." if dry_run else "Starting execution phase...")
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
        logger=logger,
    )
    logger.info(f"{op_type} phase complete. Stats: {stats}")
    logger.info(f"Review '{txn_json_path}' for a detailed log of changes and their statuses.")

    binary_log = abs_root_dir / BINARY_MATCHES_LOG_FILE
    if binary_log.exists() and binary_log.stat().st_size > 0:
        logger.info(f"{YELLOW}Note: Matches were found in binary files. See '{binary_log}' for details. Binary file content was NOT modified.{RESET}")

    collisions_log = abs_root_dir / COLLISIONS_ERRORS_LOG_FILE
    if collisions_log.exists() and collisions_log.stat().st_size > 0:
        logger.info(f"{RED}Warning: File/folder rename collisions were detected. See '{collisions_log}' for details. These renames were skipped.{RESET}")


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
