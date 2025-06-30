#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of batch file processing from file_processor.py
# - This module handles batch processing for small files
#

"""
Batch file processor for the Mass Find Replace application.

This module provides functionality for processing file content replacements
in batch for small files.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import LoggerType

from ..constants import DEFAULT_ENCODING_FALLBACK
from ..types import TransactionStatus
from ...utils import open_file_with_encoding

__all__ = [
    "execute_file_content_batch",
]


def execute_file_content_batch(
    abs_filepath: Path,
    transactions: list[dict[str, Any]],
    logger: LoggerType = None,
) -> tuple[int, int, int]:
    """
    Execute content line transactions for a single file in batch.
    Returns (completed_count, skipped_count, failed_count).
    """
    try:
        # Read entire file content
        if not abs_filepath.exists():
            for tx in transactions:
                tx["STATUS"] = TransactionStatus.FAILED.value
                tx["ERROR_MESSAGE"] = f"File not found: {abs_filepath}"
            return (0, 0, len(transactions))

        file_encoding = transactions[0].get("ORIGINAL_ENCODING", DEFAULT_ENCODING_FALLBACK)
        is_rtf = transactions[0].get("IS_RTF", False)
        if is_rtf:
            for tx in transactions:
                tx["STATUS"] = TransactionStatus.SKIPPED.value
                tx["ERROR_MESSAGE"] = "RTF content modification not supported"
            return (0, 0, len(transactions))

        with open_file_with_encoding(abs_filepath, "r", file_encoding, logger) as f:
            lines = f.readlines()

        # Apply replacements
        for tx in transactions:
            line_no = tx["LINE_NUMBER"]
            if 1 <= line_no <= len(lines):
                new_line = tx.get("NEW_LINE_CONTENT", "")
                if lines[line_no - 1] != new_line:
                    lines[line_no - 1] = new_line
                    tx["STATUS"] = TransactionStatus.COMPLETED.value
                else:
                    tx["STATUS"] = TransactionStatus.SKIPPED.value
                    tx["ERROR_MESSAGE"] = "Line already matches target"
            else:
                tx["STATUS"] = TransactionStatus.FAILED.value
                tx["ERROR_MESSAGE"] = f"Line number {line_no} out of range"

        # Write back
        with open_file_with_encoding(abs_filepath, "w", file_encoding, logger) as f:
            f.writelines(lines)

        completed = sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.COMPLETED.value)
        skipped = sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.SKIPPED.value)
        failed = sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.FAILED.value)
        return (completed, skipped, failed)
    except Exception as e:
        for tx in transactions:
            tx["STATUS"] = TransactionStatus.FAILED.value
            tx["ERROR_MESSAGE"] = f"Unhandled error: {e}"
        return (0, 0, len(transactions))
