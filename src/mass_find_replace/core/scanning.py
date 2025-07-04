#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of scanning functionality from file_system_operations.py
# - Includes directory walking and file scanning logic
# - Refactored to use submodules for better organization
# - Extracted directory walking to directory_walker.py
# - Extracted binary handling to binary_handler.py
# - Extracted item processing to item_processor.py
# - Extracted content scanning to content_scanner.py
# - Extracted transaction building to transaction_builder.py
#

"""
Directory scanning functionality for the Mass Find Replace application.

This module provides functions for scanning directories to find files and folders
that need renaming or content replacement based on configured patterns.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Any
import pathspec

from .. import replace_logic
from ..utils import log_fs_op_message
from .constants import BINARY_MATCHES_LOG_FILE
from .types import LoggerType, TransactionType

# Import from scanner submodules
from .scanner.directory_walker import walk_for_scan
from .scanner.item_processor import process_item
from .scanner.transaction_builder import is_duplicate_transaction

__all__ = [
    "scan_directory_for_occurrences",
]


def scan_directory_for_occurrences(
    root_dir: Path,
    excluded_dirs: list[str],
    excluded_files: list[str],
    file_extensions: list[str] | None,
    ignore_symlinks: bool,
    ignore_spec: pathspec.PathSpec | None,
    resume_from_transactions: list[dict[str, Any]] | None = None,
    paths_to_force_rescan: set[str] | None = None,
    skip_file_renaming: bool = False,
    skip_folder_renaming: bool = False,
    skip_content: bool = False,
    logger: LoggerType = None,
) -> list[dict[str, Any]]:
    """Scan directory for all occurrences that need replacement.

    Args:
        root_dir: Root directory to scan
        excluded_dirs: Directory names to exclude
        excluded_files: Files or relative paths to exclude
        file_extensions: List of file extensions for content scan
        ignore_symlinks: Whether to ignore symlinks
        ignore_spec: PathSpec for gitignore-style exclusions
        resume_from_transactions: Existing transactions for resume
        paths_to_force_rescan: Paths to force rescan or None for all
        skip_file_renaming: Skip file renaming operations
        skip_folder_renaming: Skip folder renaming operations
        skip_content: Skip content modifications
        logger: Optional logger instance

    Returns:
        List of transaction dictionaries
    """
    processed_transactions: list[dict[str, Any]] = []
    existing_transaction_ids: set[tuple[str, str, int]] = set()

    # Handle None as "rescan everything"
    rescan_all = paths_to_force_rescan is None
    paths_to_force_rescan_internal: set[str] = set() if rescan_all else (paths_to_force_rescan if paths_to_force_rescan is not None else set())

    binary_log_path = root_dir / BINARY_MATCHES_LOG_FILE

    if resume_from_transactions is not None:
        processed_transactions = list(resume_from_transactions)

        # Backfill NEW_NAME for existing rename transactions if missing
        for tx in resume_from_transactions:
            if tx["TYPE"] in [TransactionType.FILE_NAME.value, TransactionType.FOLDER_NAME.value] and "NEW_NAME" not in tx:
                tx["NEW_NAME"] = replace_logic.replace_occurrences(tx["ORIGINAL_NAME"])

        # Build existing transaction IDs set
        for tx in resume_from_transactions:
            tx_rel_path = tx.get("PATH")
            if (rescan_all or tx_rel_path in paths_to_force_rescan_internal) and tx.get("TYPE") == TransactionType.FILE_CONTENT_LINE.value:
                continue
            tx_type, tx_line = tx.get("TYPE"), tx.get("LINE_NUMBER", 0)
            if tx_type and tx_rel_path:
                existing_transaction_ids.add((tx_rel_path, tx_type, tx_line))

    # Resolve excluded directories to absolute paths
    resolved_abs_excluded_dirs = []
    for d_str in excluded_dirs:
        try:
            resolved_abs_excluded_dirs.append(root_dir.joinpath(d_str).resolve(strict=False))
        except Exception:
            resolved_abs_excluded_dirs.append(root_dir.joinpath(d_str).absolute())

    # Process excluded files
    excluded_basenames = {Path(f).name for f in excluded_files if Path(f).name == f and "/" not in f and "\\" not in f}
    excluded_relative_paths_set = {f.replace("\\", "/") for f in excluded_files if "/" in f or "\\" in f}

    # Walk directory tree
    item_iterator = walk_for_scan(
        root_dir,
        resolved_abs_excluded_dirs,
        ignore_symlinks,
        ignore_spec,
        logger=logger,
    )

    # Collect items with depth for proper ordering
    all_items_with_depth = []
    for item_abs_path in item_iterator:
        try:
            # Calculate depth for ordering
            depth = len(item_abs_path.relative_to(root_dir).parts)
            all_items_with_depth.append((depth, item_abs_path))
        except ValueError:
            log_fs_op_message(
                logging.WARNING,
                f"Could not get relative path for {item_abs_path} against {root_dir}. Skipping.",
                logger,
            )
            continue

    # Sort by depth (shallow first), then by path for consistent ordering
    all_items_with_depth.sort(key=lambda x: (x[0], x[1]))

    # Process each item
    for depth, item_abs_path in all_items_with_depth:
        try:
            relative_path_str = str(item_abs_path.relative_to(root_dir)).replace("\\", "/")
        except ValueError:
            log_fs_op_message(
                logging.WARNING,
                f"Could not get relative path for {item_abs_path} against {root_dir}. Skipping.",
                logger,
            )
            continue

        # Check exclusions
        if item_abs_path.name in excluded_basenames or relative_path_str in excluded_relative_paths_set:
            continue

        # Process the item
        item_transactions = process_item(
            item_abs_path,
            relative_path_str,
            root_dir,
            file_extensions,
            skip_file_renaming,
            skip_folder_renaming,
            skip_content,
            binary_log_path,
            logger,
        )

        # Add new transactions if not duplicates
        for tx in item_transactions:
            tx_type = tx["TYPE"]
            tx_line = tx.get("LINE_NUMBER", 0)
            tx_id_tuple = (relative_path_str, tx_type, tx_line)

            if not is_duplicate_transaction(tx_id_tuple, existing_transaction_ids):
                processed_transactions.append(tx)
                existing_transaction_ids.add(tx_id_tuple)

    # Order transactions: folders first (shallow to deep), then files, then content
    folder_txs = [tx for tx in processed_transactions if tx["TYPE"] == TransactionType.FOLDER_NAME.value]
    file_txs = [tx for tx in processed_transactions if tx["TYPE"] == TransactionType.FILE_NAME.value]
    content_txs = [tx for tx in processed_transactions if tx["TYPE"] == TransactionType.FILE_CONTENT_LINE.value]

    # Sort folders by depth (shallow then deep) and path for deterministic order
    folder_txs.sort(key=lambda tx: (len(Path(tx["PATH"]).parts), tx["PATH"]))

    return folder_txs + file_txs + content_txs
