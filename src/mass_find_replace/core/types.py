#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of type definitions from file_system_operations.py
# - Added type aliases and Enum classes
# - Added docstrings to all types
#

"""
Type definitions and enums for the Mass Find Replace application.

This module contains all type aliases and enum definitions that were
previously in file_system_operations.py.
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Union
import logging


# Type alias for logger types to avoid repetition
# Note: LoggerAdapter is not generic in Python 3.10, so we use Any
LoggerType = Union[logging.Logger, Any, None]


class TransactionType(str, Enum):
    """Types of transactions that can be performed on files and folders."""

    FILE_NAME = "FILE_NAME"
    FOLDER_NAME = "FOLDER_NAME"
    FILE_CONTENT_LINE = "FILE_CONTENT_LINE"


class TransactionStatus(str, Enum):
    """Status values for tracking transaction progress."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    RETRY_LATER = "RETRY_LATER"
