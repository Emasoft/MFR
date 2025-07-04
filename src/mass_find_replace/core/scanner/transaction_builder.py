#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of transaction building logic from scanning.py
# - This module handles creating transaction entries for different operation types
#

"""
Transaction builder utilities for the Mass Find Replace scanner.

This module provides functions to create transaction entries for file/folder
renaming and content modification operations.
"""

from __future__ import annotations

import time
import uuid
from typing import Any

from ..types import TransactionType, TransactionStatus
from ... import replace_logic

__all__ = [
    "create_rename_transaction",
    "create_content_transaction",
    "is_duplicate_transaction",
]


def create_rename_transaction(
    relative_path: str,
    original_name: str,
    transaction_type: TransactionType,
) -> dict[str, Any]:
    """Create a rename transaction entry.

    Args:
        relative_path: Relative path from root
        original_name: Original file/folder name
        transaction_type: Type of rename (FILE_NAME or FOLDER_NAME)

    Returns:
        Transaction dictionary
    """
    new_name = replace_logic.replace_occurrences(original_name)

    return {
        "id": str(uuid.uuid4()),
        "TYPE": transaction_type.value,
        "PATH": relative_path,
        "ORIGINAL_NAME": original_name,
        "NEW_NAME": new_name,
        "LINE_NUMBER": 0,
        "STATUS": TransactionStatus.PENDING.value,
        "timestamp_created": time.time(),
        "retry_count": 0,
    }


def create_content_transaction(
    relative_path: str,
    line_number: int,
    original_content: str,
    new_content: str,
    encoding: str | None = None,
) -> dict[str, Any]:
    """Create a content modification transaction entry.

    Args:
        relative_path: Relative path from root
        line_number: Line number in file (1-based)
        original_content: Original line content
        new_content: New line content after replacement
        encoding: Optional file encoding

    Returns:
        Transaction dictionary
    """
    transaction = {
        "id": str(uuid.uuid4()),
        "TYPE": TransactionType.FILE_CONTENT_LINE.value,
        "PATH": relative_path,
        "LINE_NUMBER": line_number,
        "ORIGINAL_LINE_CONTENT": original_content,
        "NEW_LINE_CONTENT": new_content,
        "STATUS": TransactionStatus.PENDING.value,
        "timestamp_created": time.time(),
        "retry_count": 0,
    }

    if encoding:
        transaction["ORIGINAL_ENCODING"] = encoding

    return transaction


def is_duplicate_transaction(
    tx_id_tuple: tuple[str, str, int],
    existing_ids: set[tuple[str, str, int]],
) -> bool:
    """Check if a transaction already exists.

    Args:
        tx_id_tuple: Tuple of (path, type, line_number)
        existing_ids: Set of existing transaction ID tuples

    Returns:
        True if transaction is a duplicate
    """
    return tx_id_tuple in existing_ids
