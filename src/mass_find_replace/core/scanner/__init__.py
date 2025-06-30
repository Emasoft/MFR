#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial creation of scanner submodule
# - Added exports for all scanner submodules
#

"""
Scanner submodule for Mass Find Replace.

This module breaks down the scanning functionality into smaller, focused components.
"""

from .binary_handler import search_binary_file, BINARY_CHUNK_SIZE
from .content_scanner import scan_file_content, log_binary_matches
from .directory_walker import walk_for_scan
from .file_type_detector import TEXT_EXTENSIONS, is_text_extension, should_process_content
from .item_processor import process_item, check_item_type
from .transaction_builder import (
    create_rename_transaction,
    create_content_transaction,
    is_duplicate_transaction,
)

__all__ = [
    # Binary handling
    "search_binary_file",
    "BINARY_CHUNK_SIZE",
    # Content scanning
    "scan_file_content",
    "log_binary_matches",
    # Directory walking
    "walk_for_scan",
    # File type detection
    "TEXT_EXTENSIONS",
    "is_text_extension",
    "should_process_content",
    # Item processing
    "process_item",
    "check_item_type",
    # Transaction building
    "create_rename_transaction",
    "create_content_transaction",
    "is_duplicate_transaction",
]
