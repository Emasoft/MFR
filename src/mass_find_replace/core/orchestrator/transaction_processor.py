#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of transaction processing logic from transaction_orchestrator.py
# - This module handles individual transaction execution
#

"""
Transaction processor for the Mass Find Replace orchestrator.

This module provides functionality for processing individual transactions
including rename and content modification operations.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import LoggerType

from ..types import TransactionType, TransactionStatus
from ..transaction_manager import update_transaction_status_in_list
from ..transaction_executor import execute_rename_transaction as _execute_rename_transaction
from ... import replace_logic

__all__ = [
    "process_rename_transaction",
    "should_skip_transaction",
    "prepare_content_transaction",
]


def should_skip_transaction(
    tx_item: dict[str, Any],
    skip_file_renaming: bool,
    skip_folder_renaming: bool,
    skip_content: bool,
) -> tuple[bool, str | None]:
    """Check if a transaction should be skipped based on flags.

    Args:
        tx_item: Transaction dictionary
        skip_file_renaming: Skip file rename operations
        skip_folder_renaming: Skip folder rename operations
        skip_content: Skip content operations

    Returns:
        Tuple of (should_skip, skip_reason)
    """
    tx_type = tx_item["TYPE"]

    if tx_type == TransactionType.FILE_NAME.value and skip_file_renaming:
        return True, "Skipped by flags"
    elif tx_type == TransactionType.FOLDER_NAME.value and skip_folder_renaming:
        return True, "Skipped by flag"
    elif tx_type == TransactionType.FILE_CONTENT_LINE.value and skip_content:
        return True, "Skipped by flag"

    return False, None


def process_rename_transaction(
    tx_item: dict[str, Any],
    root_dir: Path,
    path_translation_map: dict[str, str],
    path_cache: dict[str, Path],
    dry_run: bool,
    logger: LoggerType = None,
) -> tuple[TransactionStatus, str | None, bool]:
    """Process a rename transaction.

    Args:
        tx_item: Transaction dictionary
        root_dir: Root directory
        path_translation_map: Path translation mapping
        path_cache: Path cache
        dry_run: Whether this is a dry run
        logger: Optional logger instance

    Returns:
        Tuple of (status, error_message, changed)
    """
    return _execute_rename_transaction(
        tx_item,
        root_dir,
        path_translation_map,
        path_cache,
        dry_run,
        logger,
    )


def prepare_content_transaction(
    tx_item: dict[str, Any],
) -> tuple[bool, str | None]:
    """Prepare a content transaction for processing.

    Args:
        tx_item: Transaction dictionary

    Returns:
        Tuple of (should_skip, skip_reason)
    """
    # Get content from transaction
    new_line_content = tx_item.get("NEW_LINE_CONTENT", "")
    original_line_content = tx_item.get("ORIGINAL_LINE_CONTENT", "")

    # Skip if no actual change
    if new_line_content == original_line_content:
        return True, "No change needed"

    return False, None
