#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of item processing logic from scanning.py
# - This module handles processing individual files and folders during scanning
#

"""
Item processor for the Mass Find Replace scanner.

This module handles the processing of individual files and folders during
the directory scan, determining what operations need to be performed.
"""

from __future__ import annotations

import logging
import unicodedata
from pathlib import Path
from typing import Any

from ..types import LoggerType, TransactionType
from ...utils import log_fs_op_message
from ... import replace_logic
from .transaction_builder import create_rename_transaction, create_content_transaction
from .content_scanner import scan_file_content
from .binary_handler import search_binary_file
from .file_type_detector import should_process_content
from isbinary import is_binary_file

__all__ = [
    "process_item",
    "check_item_type",
]


def check_item_type(
    item_path: Path,
    root_dir: Path,
    logger: LoggerType = None,
) -> tuple[bool, bool, bool]:
    """Check if item is a directory, file, or symlink.

    Args:
        item_path: Path to check
        root_dir: Root directory for symlink validation
        logger: Optional logger instance

    Returns:
        Tuple of (is_dir, is_file, is_symlink)
    """
    is_dir = False
    is_file = False
    is_symlink = False

    try:
        is_symlink = item_path.is_symlink()

        if not is_symlink:
            is_dir = item_path.is_dir()
        else:
            # Check if symlink points outside root
            try:
                target = item_path.resolve(strict=False)
            except Exception as e_resolve:
                log_fs_op_message(
                    logging.WARNING,
                    f"Could not resolve symlink target for {item_path}: {e_resolve}. Skipping.",
                    logger,
                )
                return (False, False, True)

            if root_dir not in target.parents and target != root_dir:
                log_fs_op_message(
                    logging.INFO,
                    f"Skipping external symlink: {item_path} -> {target}",
                    logger,
                )
                return (False, False, True)
            # Treat symlink as file for name replacement
            is_file = True

        if not is_dir and not is_file:
            # If not dir and not file, check if file (for symlink to file)
            is_file = item_path.is_file()

    except OSError as e_stat:
        log_fs_op_message(
            logging.WARNING,
            f"OS error checking type of {item_path}: {e_stat}. Skipping item.",
            logger,
        )

    return (is_dir, is_file, is_symlink)


def process_item(
    item_path: Path,
    relative_path: str,
    root_dir: Path,
    file_extensions: list[str] | None,
    skip_file_renaming: bool,
    skip_folder_renaming: bool,
    skip_content: bool,
    binary_log_path: Path,
    logger: LoggerType = None,
) -> list[dict[str, Any]]:
    """Process a single item (file or folder) for potential operations.

    Args:
        item_path: Absolute path to item
        relative_path: Relative path from root
        root_dir: Root directory
        file_extensions: List of file extensions for content scan
        skip_file_renaming: Skip file renaming operations
        skip_folder_renaming: Skip folder renaming operations
        skip_content: Skip content modifications
        binary_log_path: Path to binary matches log file
        logger: Optional logger instance

    Returns:
        List of transaction dictionaries for this item
    """
    transactions: list[dict[str, Any]] = []

    # Get scan pattern
    scan_pattern = replace_logic.get_scan_pattern()
    if not scan_pattern:
        return transactions

    # Check item type
    is_dir, is_file, is_symlink = check_item_type(item_path, root_dir, logger)

    # Process name replacements
    original_name = item_path.name
    searchable_name = unicodedata.normalize(
        "NFC",
        replace_logic.strip_control_characters(replace_logic.strip_diacritics(original_name)),
    )

    if scan_pattern.search(searchable_name):
        new_name = replace_logic.replace_occurrences(original_name)
        if new_name != original_name:
            if is_dir and not skip_folder_renaming:
                transactions.append(
                    create_rename_transaction(
                        relative_path,
                        original_name,
                        TransactionType.FOLDER_NAME,
                    )
                )
            elif (is_file or is_symlink) and not skip_file_renaming:
                transactions.append(
                    create_rename_transaction(
                        relative_path,
                        original_name,
                        TransactionType.FILE_NAME,
                    )
                )

    # Process content if applicable
    if not skip_content and is_file:
        # First check for binary files (regardless of extension)
        is_rtf = item_path.suffix.lower() == ".rtf"
        skip_binary_check = is_rtf  # RTF files need special handling

        # Check for binary file
        if not skip_binary_check:
            try:
                if is_binary_file(str(item_path)):
                    # It's binary - search for patterns and log
                    raw_keys = replace_logic.get_raw_stripped_keys()
                    if raw_keys:
                        search_binary_file(
                            item_path,
                            relative_path,
                            raw_keys,
                            binary_log_path,
                            root_dir,
                            logger,
                        )
                    return transactions  # Don't process content of binary files
            except Exception as e:
                log_fs_op_message(
                    logging.WARNING,
                    f"Could not determine if {item_path} is binary: {e}. Skipping content scan.",
                    logger,
                )
                return transactions

        # Check if we should process this file's content
        if should_process_content(item_path, file_extensions):
            # Scan text file content
            content_transactions = scan_file_content(
                item_path,
                relative_path,
                skip_binary_check=True,  # We already checked
                logger=logger,
            )
            transactions.extend(content_transactions)

    return transactions
