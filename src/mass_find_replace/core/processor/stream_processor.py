#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of streaming file processing from file_processor.py
# - This module handles streaming processing for large files
#

"""
Stream file processor for the Mass Find Replace application.

This module provides functionality for processing file content replacements
using a streaming approach for large files.
"""

from __future__ import annotations
import os
import uuid
import logging
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import LoggerType

from ... import replace_logic
from ...utils import (
    log_fs_op_message,
    open_file_with_encoding,
)
from ..constants import (
    SAFE_LINE_LENGTH_THRESHOLD,
    CHUNK_SIZE,
    FALLBACK_CHUNK_SIZE,
)
from ..types import TransactionStatus

__all__ = [
    "process_large_file_content",
]


def process_large_file_content(
    txns_for_file: list[dict[str, Any]],
    abs_filepath: Path,
    file_encoding: str,
    is_rtf: bool,
    logger: LoggerType = None,
) -> None:
    """Process content replacements for large files using streaming approach.

    Args:
        txns_for_file: List of transactions for this file
        abs_filepath: Absolute path to the file
        file_encoding: File encoding to use
        is_rtf: Whether file is RTF format
        logger: Optional logger instance
    """
    if is_rtf:
        for tx in txns_for_file:
            tx["STATUS"] = TransactionStatus.SKIPPED.value
            tx["ERROR_MESSAGE"] = "RTF content modification not supported"
        return

    # Get all characters that might be in replacement keys
    key_characters = replace_logic.get_key_characters()

    # Sort transactions by line number
    txns_sorted = sorted(txns_for_file, key=lambda tx: tx["LINE_NUMBER"])
    max_line = txns_sorted[-1]["LINE_NUMBER"]

    # Map from line number to transaction with precomputed new content
    txn_map = {tx["LINE_NUMBER"]: tx for tx in txns_sorted}

    # Use unique temp file name
    temp_file = abs_filepath.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")

    try:
        with open_file_with_encoding(abs_filepath, "r", file_encoding, logger) as src_file:
            with open_file_with_encoding(temp_file, "w", file_encoding, logger) as dst_file:
                # Track state between lines
                current_line = 1

                # Process file line by line, receiving from src_file
                while current_line <= max_line:
                    if current_line in txn_map:
                        # This line will be modified
                        tx = txn_map[current_line]
                        # Load replacement content for transaction
                        upgrade_content = tx.get("NEW_LINE_CONTENT", "")
                    else:
                        # This line won't be modified
                        upgrade_content = None

                    # Read full line using readline() with size hint
                    line_buffer = []
                    while True:
                        # Implement safe fetching with fragmented reads
                        part = src_file.readline()
                        if not part:
                            break
                        line_buffer.append(part)
                        if part.endswith("\n") or part.endswith("\r"):
                            break
                    current_line_content = "".join(line_buffer)

                    # Skip empty lines
                    if not current_line_content:
                        current_line += 1
                        continue

                    # Only process long lines with chunked approach
                    if len(current_line_content) > SAFE_LINE_LENGTH_THRESHOLD and not upgrade_content:
                        # Process in safe chunks for unmmodified long lines
                        buffer_idx = 0
                        while buffer_idx < len(current_line_content):
                            end_idx = buffer_idx + CHUNK_SIZE
                            if end_idx >= len(current_line_content):
                                dst_file.write(current_line_content[buffer_idx:])
                                break

                            # Find safe split position - scan backward to find a character not in keys
                            split_pos = end_idx
                            search_pos = min(end_idx - 1, len(current_line_content) - 1)

                            # Use key characters already obtained at the start of the function

                            while search_pos >= buffer_idx:
                                if current_line_content[search_pos] not in key_characters:
                                    split_pos = search_pos + 1
                                    break
                                search_pos -= 1

                            # Special case: if we didn't find any non-key character
                            if split_pos == end_idx and search_pos < buffer_idx:
                                # Backtrack further if necessary (shouldn't happen often)
                                split_pos = min(buffer_idx + FALLBACK_CHUNK_SIZE, len(current_line_content))

                            # Process and write the chunk
                            dst_file.write(current_line_content[buffer_idx:split_pos])
                            buffer_idx = split_pos
                    # Regular line processing (short line or modified line)
                    elif upgrade_content is not None:
                        # Write precomputed content if available
                        dst_file.write(upgrade_content)
                    else:
                        # Write line as is
                        dst_file.write(current_line_content)

                    # Update transaction status
                    if current_line in txn_map:
                        txn_map[current_line]["STATUS"] = TransactionStatus.COMPLETED.value

                    current_line += 1

                # Handle potential trailing lines not in transactions
                trailing_content = src_file.read()
                dst_file.write(trailing_content)

        # Atomically replace file after successful write
        os.replace(temp_file, abs_filepath)

    except Exception as e:
        # Handle file errors
        for tx in txns_for_file:
            if tx.get("STATUS") != TransactionStatus.COMPLETED.value:
                tx["STATUS"] = TransactionStatus.FAILED.value
                tx["ERROR_MESSAGE"] = f"File processing error: {e}"
        try:
            if temp_file.exists():
                os.remove(temp_file)
        except Exception as cleanup_e:
            log_fs_op_message(
                logging.WARNING,
                f"Could not remove temp file {temp_file}: {cleanup_e}",
                logger,
            )
    finally:
        # Ensure temp file is cleaned up
        try:
            if temp_file.exists():
                os.remove(temp_file)
        except OSError:
            pass
