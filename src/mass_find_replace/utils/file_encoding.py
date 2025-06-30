#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of file encoding detection from file_system_operations.py
# - Includes BOM detection, UTF-16 pattern detection, and chardet fallback
#

"""
File encoding detection utilities.

This module provides comprehensive encoding detection including BOM markers,
UTF-16 pattern detection, and character detection libraries.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Any
import chardet

from ..core.types import LoggerType
from ..core.constants import (
    DEFAULT_ENCODING_SAMPLE_SIZE,
    DEFAULT_ENCODING_FALLBACK,
    SMALL_FILE_SIZE_THRESHOLD,
)
from .logging_utils import log_fs_op_message


def get_file_encoding(file_path: Path, sample_size: int = DEFAULT_ENCODING_SAMPLE_SIZE, logger: LoggerType = None) -> str:
    """Detect file encoding using multiple strategies.

    This function uses a multi-step approach to detect file encoding:
    1. Check for BOM (Byte Order Mark) markers
    2. Detect UTF-16 by analyzing byte patterns
    3. Try UTF-8 decoding
    4. Use chardet library for detection
    5. Fall back to common encodings

    Args:
        file_path: Path to the file
        sample_size: Number of bytes to sample for detection
        logger: Optional logger instance

    Returns:
        Detected encoding name (e.g., 'utf-8', 'utf-16-le', 'cp1252')
    """
    if not file_path.is_file():
        return DEFAULT_ENCODING_FALLBACK

    try:
        file_size = file_path.stat().st_size

        # Read the file or sample
        if file_size <= SMALL_FILE_SIZE_THRESHOLD:
            raw_data = file_path.read_bytes()
        else:
            with file_path.open("rb") as f:
                raw_data = f.read(sample_size)

        if not raw_data:
            return DEFAULT_ENCODING_FALLBACK

        # 1. Check for BOM markers first
        if raw_data.startswith(b"\xff\xfe"):
            return "utf-16-le"
        if raw_data.startswith(b"\xfe\xff"):
            return "utf-16-be"
        if raw_data.startswith(b"\xff\xfe\x00\x00"):
            return "utf-32-le"
        if raw_data.startswith(b"\x00\x00\xfe\xff"):
            return "utf-32-be"
        if raw_data.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"

        # 2. Check for UTF-16 patterns by analyzing byte patterns
        if len(raw_data) >= 4:
            # Look for alternating null bytes with ASCII characters
            # Check up to 500 bytes for more reliable detection
            check_len = min(len(raw_data), 500)

            # Count ASCII characters with null bytes in UTF-16 LE pattern
            le_ascii_chars = 0
            be_ascii_chars = 0

            for i in range(0, check_len - 1, 2):
                # UTF-16 LE: ASCII byte followed by null
                if 0x20 <= raw_data[i] <= 0x7E and raw_data[i + 1] == 0:
                    le_ascii_chars += 1
                # UTF-16 BE: null followed by ASCII byte
                if raw_data[i] == 0 and 0x20 <= raw_data[i + 1] <= 0x7E:
                    be_ascii_chars += 1

            # If we found significant ASCII patterns, it's likely UTF-16
            min_ascii_threshold = 5  # At least 5 ASCII chars to be confident

            if le_ascii_chars > min_ascii_threshold and le_ascii_chars > be_ascii_chars:
                try:
                    raw_data.decode("utf-16-le", errors="strict")
                    return "utf-16-le"
                except UnicodeDecodeError:
                    pass
            elif be_ascii_chars > min_ascii_threshold:
                try:
                    raw_data.decode("utf-16-be", errors="strict")
                    return "utf-16-be"
                except UnicodeDecodeError:
                    pass

        # 3. Try UTF-8 for all files regardless of size
        try:
            if file_path.suffix.lower() != ".rtf":
                raw_data.decode("utf-8", errors="strict")
                return "utf-8"
        except UnicodeDecodeError:
            pass

        # RTF files use Latin-1
        if file_path.suffix.lower() == ".rtf":
            return "latin-1"

        # 4. Use chardet detection
        detected = chardet.detect(raw_data)
        encoding = detected.get("encoding") or DEFAULT_ENCODING_FALLBACK
        confidence = detected.get("confidence", 0)

        # Normalize GB2312 to GB18030
        if encoding and encoding.lower().startswith("gb2312"):
            encoding = "gb18030"

        # Only consider chardet results with reasonable confidence
        if confidence > 0.5 and encoding:
            encoding = encoding.lower()
            # Handle common encoding aliases
            try:
                raw_data.decode(encoding, errors="surrogateescape")
                return encoding
            except (UnicodeDecodeError, LookupError):
                pass

        # 5. Fallback explicit checks if UTF-8 and chardet's primary suggestion failed
        for enc_try in ["cp1252", "latin1", "iso-8859-1"]:
            try:
                if encoding != enc_try:
                    raw_data.decode(enc_try, errors="surrogateescape")
                    return enc_try
            except (UnicodeDecodeError, LookupError):
                pass

        log_fs_op_message(
            logging.DEBUG,
            f"Encoding for {file_path} could not be confidently determined. Chardet: {detected}. Using {DEFAULT_ENCODING_FALLBACK}.",
            logger,
        )
        return DEFAULT_ENCODING_FALLBACK

    except Exception as e:
        log_fs_op_message(
            logging.ERROR,
            f"Error detecting encoding for {file_path}: {e}. Using {DEFAULT_ENCODING_FALLBACK}",
            logger,
        )
        return DEFAULT_ENCODING_FALLBACK


def open_file_with_encoding(
    file_path: Path,
    mode: str = "r",
    encoding: str | None = None,
    logger: LoggerType = None,
) -> Any:
    """Open a file with proper encoding detection and error handling.

    This function wraps the standard open() function with automatic encoding
    detection when not specified.

    Args:
        file_path: Path to the file
        mode: File open mode (e.g., 'r', 'w', 'rb')
        encoding: Encoding to use (if None, will detect)
        logger: Optional logger instance

    Returns:
        File handle

    Raises:
        IOError: If file cannot be opened
    """
    if encoding is None and "b" not in mode:
        encoding = get_file_encoding(file_path, logger=logger)

    try:
        if "b" in mode:
            return open(file_path, mode)
        return open(file_path, mode, encoding=encoding, errors="surrogateescape", newline="")
    except OSError as e:
        log_fs_op_message(
            logging.ERROR,
            f"Cannot open file {file_path} in mode '{mode}' with encoding '{encoding}': {e}",
            logger,
        )
        raise
