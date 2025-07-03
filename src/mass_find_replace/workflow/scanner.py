#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of scanning phase logic from mass_find_replace.py
# - This module handles the scanning and resume logic
#

"""
Scanner workflow for the Mass Find Replace application.

This module contains the scanning phase logic including resume functionality.
"""

from __future__ import annotations

import logging
import pathspec
from pathlib import Path
from typing import Any

from ..ui.display import YELLOW, RESET
from ..file_system_operations import (
    scan_directory_for_occurrences,
    save_transactions,
    load_transactions,
    TransactionStatus,
    BINARY_MATCHES_LOG_FILE,
)

__all__ = [
    "perform_scan_phase",
]


def perform_scan_phase(
    abs_root_dir: Path,
    txn_json_path: Path,
    skip_scan: bool,
    resume: bool,
    dry_run: bool,
    extensions: list[str] | None,
    exclude_dirs: list[str],
    exclude_files: list[str],
    ignore_symlinks_arg: bool,
    final_ignore_spec: pathspec.PathSpec | None,
    skip_file_renaming: bool,
    skip_folder_renaming: bool,
    skip_content: bool,
    replacement_mapping: dict[str, str],
    logger: logging.Logger | logging.LoggerAdapter[logging.Logger],
) -> list[dict[str, Any]] | None:
    """Perform the scanning phase of the workflow.

    Args:
        abs_root_dir: Absolute root directory
        txn_json_path: Path to transaction JSON file
        skip_scan: Whether to skip scanning phase
        resume: Whether to resume from existing transaction file
        dry_run: Whether this is a dry run
        extensions: File extensions to process
        exclude_dirs: Directories to exclude
        exclude_files: Files to exclude
        ignore_symlinks_arg: Whether to ignore symlinks
        final_ignore_spec: Ignore patterns spec
        skip_file_renaming: Whether to skip file renaming
        skip_folder_renaming: Whether to skip folder renaming
        skip_content: Whether to skip content modification
        replacement_mapping: Replacement mapping dictionary
        logger: Logger instance

    Returns:
        List of transactions or None if failed
    """
    if not skip_scan:
        # Clear old binary log at the beginning of scan (not resume)
        if not resume:
            binary_log_path = abs_root_dir / BINARY_MATCHES_LOG_FILE
            if binary_log_path.exists():
                try:
                    binary_log_path.unlink()
                    logger.debug(f"Cleared old binary log file: {binary_log_path}")
                except Exception as e:
                    logger.warning(f"Could not clear binary log file {binary_log_path}: {e}")

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
            return None

        return found_txns

    elif not txn_json_path.exists():
        logger.error(f"Error: --skip-scan used, but '{txn_json_path}' not found.")
        return None
    else:
        logger.info(f"Using existing transaction file: '{txn_json_path}'. Ensure it was generated with compatible settings.")
        return load_transactions(txn_json_path, logger=logger)
