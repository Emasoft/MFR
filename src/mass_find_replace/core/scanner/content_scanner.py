#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of content scanning logic from scanning.py
# - This module handles scanning file contents for replacements
#

"""
Content scanner for the Mass Find Replace application.

This module provides functions to scan file contents and detect lines that need replacement.
"""

from __future__ import annotations

import logging
import unicodedata
from pathlib import Path
from typing import Any

from striprtf.striprtf import rtf_to_text
from isbinary import is_binary_file

from ..constants import (
    SAFE_LINE_LENGTH_THRESHOLD,
    DEFAULT_ENCODING_FALLBACK,
)
from ..types import LoggerType
from ...utils import (
    get_file_encoding,
    open_file_with_encoding,
    log_fs_op_message,
)
from ... import replace_logic
from .file_type_detector import is_text_extension
from .transaction_builder import create_content_transaction

__all__ = [
    "scan_file_content",
    "log_binary_matches",
]


def scan_file_content(
    file_path: Path,
    relative_path: str,
    skip_binary_check: bool = False,
    logger: LoggerType = None,
) -> list[dict[str, Any]]:
    """Scan a file's content for lines that need replacement.

    Args:
        file_path: Absolute path to file
        relative_path: Relative path from root
        skip_binary_check: Whether to skip binary file detection
        logger: Optional logger instance

    Returns:
        List of content transaction dictionaries
    """
    transactions: list[dict[str, Any]] = []

    # Check if it's an RTF file
    is_rtf = file_path.suffix.lower() == ".rtf"

    # Skip binary check if requested or if it's a known text extension
    if not skip_binary_check and not is_text_extension(file_path):
        if is_binary_file(str(file_path)):
            return transactions

    # Get the scan pattern
    scan_pattern = replace_logic.get_scan_pattern()
    if not scan_pattern:
        return transactions

    # Detect encoding
    detected_encoding = get_file_encoding(file_path)
    if not detected_encoding:
        log_fs_op_message(
            logging.WARNING,
            f"Could not detect encoding for '{relative_path}'. Skipping content scan.",
            logger,
        )
        return transactions

    try:
        with open_file_with_encoding(file_path, "r", detected_encoding) as f:
            if is_rtf:
                # Read entire RTF file and convert
                rtf_content = f.read()
                try:
                    plain_content = rtf_to_text(rtf_content)
                    lines = plain_content.splitlines(keepends=True)
                except Exception as rtf_error:
                    log_fs_op_message(
                        logging.WARNING,
                        f"Could not parse RTF file '{relative_path}': {rtf_error}. Skipping content scan.",
                        logger,
                    )
                    return transactions
            else:
                lines = f.readlines()

        # Process lines
        for line_idx, line in enumerate(lines):
            line_num = line_idx + 1

            # Skip very long lines
            if len(line) > SAFE_LINE_LENGTH_THRESHOLD:
                continue

            # Normalize and search
            normalized_line = unicodedata.normalize("NFC", line)
            searchable_line = replace_logic.strip_control_characters(replace_logic.strip_diacritics(normalized_line))

            if scan_pattern.search(searchable_line):
                new_line = replace_logic.replace_occurrences(line)
                if new_line != line:
                    transactions.append(
                        create_content_transaction(
                            relative_path,
                            line_num,
                            line,
                            new_line,
                            detected_encoding,
                        )
                    )

    except OSError as e:
        log_fs_op_message(
            logging.WARNING,
            f"Could not read file '{relative_path}': {e}",
            logger,
        )
    except UnicodeDecodeError as e:
        log_fs_op_message(
            logging.WARNING,
            f"Unicode decode error in '{relative_path}': {e}",
            logger,
        )
    except Exception as e:
        log_fs_op_message(
            logging.WARNING,
            f"Unexpected error scanning '{relative_path}': {e}",
            logger,
        )

    return transactions


def log_binary_matches(
    file_path: Path,
    relative_path: str,
    binary_log_path: Path,
    raw_keys: list[bytes],
    logger: LoggerType = None,
) -> None:
    """Log matches found in binary files.

    Args:
        file_path: Absolute path to binary file
        relative_path: Relative path from root
        binary_log_path: Path to binary matches log file
        raw_keys: List of raw byte patterns to search for
        logger: Optional logger instance
    """
    if not raw_keys:
        return

    try:
        # Read file in chunks to handle large files
        matches_found = []
        with open(file_path, "rb") as f:
            content = f.read(10 * 1024 * 1024)  # Read first 10MB

        for key in raw_keys:
            if key in content:
                matches_found.append(key.decode(DEFAULT_ENCODING_FALLBACK, errors="replace"))

        if matches_found:
            # Log the matches
            with open(binary_log_path, "a", encoding=DEFAULT_ENCODING_FALLBACK) as log_file:
                log_file.write(f"\n{relative_path}:\n")
                log_file.write(f"  Binary file contains matches for: {', '.join(matches_found)}\n")

            log_fs_op_message(
                logging.INFO,
                f"Binary file '{relative_path}' contains matches (not modified)",
                logger,
            )

    except Exception as e:
        log_fs_op_message(
            logging.WARNING,
            f"Error checking binary file '{relative_path}': {e}",
            logger,
        )
