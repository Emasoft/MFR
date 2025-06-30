#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of binary file handling logic from scanning.py
# - This module handles searching for patterns in binary files
#

"""
Binary file handler for the Mass Find Replace scanner.

This module provides functionality to search for patterns in binary files
and log matches without modifying the files.
"""

from __future__ import annotations

import time
import logging
from pathlib import Path
from typing import Any

from ..constants import DEFAULT_ENCODING_FALLBACK
from ..types import LoggerType
from ...utils import log_fs_op_message

__all__ = [
    "search_binary_file",
    "BINARY_CHUNK_SIZE",
]

# Process binary files in 1MB chunks
BINARY_CHUNK_SIZE: int = 1_048_576


def search_binary_file(
    file_path: Path,
    relative_path: str,
    raw_keys: list[str],
    binary_log_path: Path,
    root_dir: Path,
    logger: LoggerType = None,
) -> None:
    """Search for patterns in a binary file and log matches.

    Args:
        file_path: Absolute path to binary file
        relative_path: Relative path from root
        raw_keys: List of string patterns to search for
        binary_log_path: Path to binary matches log file
        root_dir: Root directory for relative path calculation
        logger: Optional logger instance
    """
    if not raw_keys:
        return

    try:
        # Process binary file in chunks to avoid memory exhaustion
        with file_path.open("rb") as bf:
            # Pre-encode keys for efficiency
            encoded_keys = []
            for key_str in raw_keys:
                try:
                    encoded_keys.append((key_str, key_str.encode("utf-8")))
                except UnicodeEncodeError:
                    continue

            if not encoded_keys:
                return

            # Track global offset for reporting
            global_offset = 0
            overlap_size = max(len(kb[1]) for kb in encoded_keys) - 1

            # Process file in chunks with overlap
            while True:
                chunk = bf.read(BINARY_CHUNK_SIZE)
                if not chunk:
                    break

                # For subsequent chunks, prepend overlap from previous chunk
                if global_offset > 0 and overlap_size > 0:
                    # Seek back to get overlap
                    bf.seek(global_offset - overlap_size)
                    overlap_chunk = bf.read(overlap_size)
                    chunk = overlap_chunk + chunk
                    search_offset = -overlap_size
                else:
                    search_offset = 0

                # Search for each key in this chunk
                for key_str, key_bytes in encoded_keys:
                    offset = 0
                    while True:
                        idx = chunk.find(key_bytes, offset)
                        if idx == -1:
                            break
                        # Only report if match is not in overlap region of subsequent chunks
                        if idx >= search_offset:
                            actual_offset = global_offset + idx - (0 if search_offset >= 0 else -search_offset)
                            # Ensure relative path is used in log
                            if not Path(relative_path).is_absolute():
                                log_path_str = relative_path
                            else:
                                log_path_str = str(file_path.relative_to(root_dir)).replace("\\", "/")
                            with binary_log_path.open("a", encoding="utf-8") as log_f:
                                log_f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - MATCH: " f"File: {log_path_str}, Key: '{key_str}', Offset: {actual_offset}\n")
                        offset = idx + len(key_bytes)

                # Update global offset
                global_offset += len(chunk) - (0 if search_offset >= 0 else -search_offset)

                # If we read less than chunk size, we're at EOF
                if len(chunk) < BINARY_CHUNK_SIZE + (overlap_size if global_offset > BINARY_CHUNK_SIZE else 0):
                    break

    except OSError as e_bin_read:
        log_fs_op_message(
            logging.WARNING,
            f"OS error reading binary file {file_path} for logging: {e_bin_read}",
            logger,
        )
    except Exception as e_bin_proc:
        log_fs_op_message(
            logging.WARNING,
            f"Error processing binary {file_path} for logging: {e_bin_proc}",
            logger,
        )
