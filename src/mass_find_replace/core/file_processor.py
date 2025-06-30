#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of file processing functionality from file_system_operations.py
# - Includes batch file processing and large file streaming functions
#

"""
File processing functionality for the Mass Find Replace application.

This module provides functions for efficiently processing file content
replacements, including batch processing and streaming for large files.
"""

from __future__ import annotations
import os
import uuid
import logging
from pathlib import Path
from typing import Any

from .. import replace_logic
from ..utils import (
    log_fs_op_message,
    open_file_with_encoding,
)
from .constants import (
    DEFAULT_ENCODING_FALLBACK,
    SMALL_FILE_SIZE_THRESHOLD,
    SAFE_LINE_LENGTH_THRESHOLD,
    CHUNK_SIZE,
    FALLBACK_CHUNK_SIZE,
)
from .types import (
    LoggerType,
    TransactionStatus,
    TransactionType,
)
from .transaction_executor import _get_current_absolute_path


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
