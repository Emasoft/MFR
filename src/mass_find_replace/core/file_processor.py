#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of file processing functionality from file_system_operations.py
# - Includes batch file processing and large file streaming functions
# - Refactored to use processor submodules for better organization
#

"""
File processing functionality for the Mass Find Replace application.

This module provides functions for efficiently processing file content
replacements, including batch processing and streaming for large files.
"""

from __future__ import annotations

# Import from processor submodules
from .processor.batch_processor import execute_file_content_batch
from .processor.stream_processor import process_large_file_content
from .processor.group_processor import group_and_process_file_transactions

__all__ = [
    "execute_file_content_batch",
    "process_large_file_content",
    "group_and_process_file_transactions",
]
