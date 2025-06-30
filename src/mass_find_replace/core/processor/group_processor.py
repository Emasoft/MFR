#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of file grouping and processing from file_processor.py
# - This module handles grouping transactions by file and processing them
#

"""
Group file processor for the Mass Find Replace application.

This module provides functionality for grouping transactions by file
and processing them efficiently.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import LoggerType

from ..constants import (
    DEFAULT_ENCODING_FALLBACK,
    SMALL_FILE_SIZE_THRESHOLD,
)
from ..types import (
    TransactionStatus,
    TransactionType,
)
from ..transaction_executor import _get_current_absolute_path
from .batch_processor import execute_file_content_batch
from .stream_processor import process_large_file_content

__all__ = [
    "group_and_process_file_transactions",
]


def group_and_process_file_transactions(
    transactions: list[dict[str, Any]],
    root_dir: Path,
    path_translation_map: dict[str, str],
    path_cache: dict[str, Path],
    dry_run: bool,
    skip_content: bool,
    logger: LoggerType = None,
) -> None:
    """Group transactions by file and process them efficiently.

    Groups content line transactions by their target file and processes
    each file once, applying all changes in a single pass for efficiency.

    Args:
        transactions: List of FILE_CONTENT_LINE transactions to process
        root_dir: Root directory of the project
        path_translation_map: Map of original paths to renamed paths
        path_cache: Cache of resolved paths
        dry_run: If True, simulate without actual changes
        skip_content: If True, skip all content modifications
        logger: Optional logger instance
    """
    # Group transactions by file path
    file_groups = {}
    for tx in transactions:
        if tx["TYPE"] != TransactionType.FILE_CONTENT_LINE.value:
            continue

        abs_path = _get_current_absolute_path(tx["PATH"], root_dir, path_translation_map, path_cache, dry_run)
        file_id = str(abs_path.resolve())

        if file_id not in file_groups:
            file_groups[file_id] = {
                "abs_path": abs_path,
                "txns": [],
                "encoding": tx.get("ORIGINAL_ENCODING", DEFAULT_ENCODING_FALLBACK),
                "is_rtf": tx.get("IS_RTF", False),
            }
        file_groups[file_id]["txns"].append(tx)

    # Process each file group
    for file_data in file_groups.values():
        abs_path = file_data["abs_path"]

        if skip_content:
            # Mark all as skipped
            for tx in file_data["txns"]:
                tx["STATUS"] = TransactionStatus.SKIPPED.value
            continue

        if dry_run:
            # Dry-run completes without actual write
            for tx in file_data["txns"]:
                tx["STATUS"] = TransactionStatus.COMPLETED.value
                tx["ERROR_MESSAGE"] = "DRY_RUN"
            continue

        try:
            # Get file stats
            file_size = abs_path.stat().st_size

            if file_size <= SMALL_FILE_SIZE_THRESHOLD:
                # Small file - use existing method
                execute_file_content_batch(abs_path, file_data["txns"], logger)
            else:
                # Large file - new streaming method
                process_large_file_content(
                    file_data["txns"],
                    abs_path,
                    file_data["encoding"],
                    file_data["is_rtf"],
                    logger,
                )

        except Exception as e:
            # Mark all transactions as failed
            for tx in file_data["txns"]:
                tx["STATUS"] = TransactionStatus.FAILED.value
                tx["ERROR_MESSAGE"] = f"File group processing error: {e}"

    # Return nothing - transactions modified in-place
