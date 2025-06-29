#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial creation for core module exports
# - Re-exports all constants, exceptions, and types for backward compatibility
#

"""
Core module containing constants, exceptions, and type definitions.

This module re-exports all core components to maintain backward compatibility
with existing code that imports from file_system_operations.
"""

# Re-export all constants
from .constants import (
    SMALL_FILE_SIZE_THRESHOLD,
    LARGE_FILE_SIZE_THRESHOLD,
    DEFAULT_ENCODING_SAMPLE_SIZE,
    QUICK_RETRY_COUNT,
    QUICK_RETRY_DELAY,
    MAX_RETRY_WAIT_TIME,
    RETRY_BACKOFF_MULTIPLIER,
    SAFE_LINE_LENGTH_THRESHOLD,
    CHUNK_SIZE,
    FALLBACK_CHUNK_SIZE,
    DEFAULT_ENCODING_FALLBACK,
    TRANSACTION_FILE_BACKUP_EXT,
    SELF_TEST_ERROR_FILE_BASENAME,
    BINARY_MATCHES_LOG_FILE,
    COLLISIONS_ERRORS_LOG_FILE,
    RETRYABLE_OS_ERRORNOS,
    GREEN_FG,
    YELLOW_FG,
    BLUE_FG,
    MAGENTA_FG,
    CYAN_FG,
    RED_FG,
    DIM_STYLE,
    BOLD_STYLE,
    RESET_STYLE,
)

# Re-export all exceptions
from .exceptions import (
    SandboxViolationError,
    MockableRetriableError,
)

# Re-export all types
from .types import (
    LoggerType,
    TransactionType,
    TransactionStatus,
)

__all__ = [
    # Constants
    "SMALL_FILE_SIZE_THRESHOLD",
    "LARGE_FILE_SIZE_THRESHOLD",
    "DEFAULT_ENCODING_SAMPLE_SIZE",
    "QUICK_RETRY_COUNT",
    "QUICK_RETRY_DELAY",
    "MAX_RETRY_WAIT_TIME",
    "RETRY_BACKOFF_MULTIPLIER",
    "SAFE_LINE_LENGTH_THRESHOLD",
    "CHUNK_SIZE",
    "FALLBACK_CHUNK_SIZE",
    "DEFAULT_ENCODING_FALLBACK",
    "TRANSACTION_FILE_BACKUP_EXT",
    "SELF_TEST_ERROR_FILE_BASENAME",
    "BINARY_MATCHES_LOG_FILE",
    "COLLISIONS_ERRORS_LOG_FILE",
    "RETRYABLE_OS_ERRORNOS",
    "GREEN_FG",
    "YELLOW_FG",
    "BLUE_FG",
    "MAGENTA_FG",
    "CYAN_FG",
    "RED_FG",
    "DIM_STYLE",
    "BOLD_STYLE",
    "RESET_STYLE",
    # Exceptions
    "SandboxViolationError",
    "MockableRetriableError",
    # Types
    "LoggerType",
    "TransactionType",
    "TransactionStatus",
]
