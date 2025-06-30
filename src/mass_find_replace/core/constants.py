#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of constants from file_system_operations.py
# - Organized constants by category for better readability
#

"""
Constants used throughout the Mass Find Replace application.

This module contains all constants that were previously in file_system_operations.py,
organized by their purpose and usage.
"""

from typing import Final

# File size thresholds
SMALL_FILE_SIZE_THRESHOLD: Final[int] = 1_048_576  # 1 MB - files smaller than this are read entirely
LARGE_FILE_SIZE_THRESHOLD: Final[int] = 100_000_000  # 100 MB - files larger than this are skipped for content scan
DEFAULT_ENCODING_SAMPLE_SIZE: Final[int] = 10240  # 10 KB - sample size for encoding detection

# Retry logic constants
QUICK_RETRY_COUNT: Final[int] = 3  # Number of quick retries with short delay
QUICK_RETRY_DELAY: Final[int] = 1  # Seconds between quick retries
MAX_RETRY_WAIT_TIME: Final[int] = 30  # Maximum wait time between retries in seconds
RETRY_BACKOFF_MULTIPLIER: Final[int] = 5  # Multiplier for exponential backoff

# Large file processing constants
SAFE_LINE_LENGTH_THRESHOLD: Final[int] = 1000  # Characters - lines longer than this use chunked processing
CHUNK_SIZE: Final[int] = 1000  # Characters - chunk size for processing long lines
FALLBACK_CHUNK_SIZE: Final[int] = 1000  # Characters - fallback chunk size if no safe split found

# File and encoding defaults
DEFAULT_ENCODING_FALLBACK: Final[str] = "utf-8"
TRANSACTION_FILE_BACKUP_EXT: Final[str] = ".bak"
SELF_TEST_ERROR_FILE_BASENAME: Final[str] = "error_file_test.txt"

# Log file names
BINARY_MATCHES_LOG_FILE: Final[str] = "binary_files_matches.log"
COLLISIONS_ERRORS_LOG_FILE: Final[str] = "collisions_errors.log"

# OS error numbers that are retryable
import errno

RETRYABLE_OS_ERRORNOS: Final[set[int]] = {
    errno.EACCES,
    errno.EBUSY,
    errno.ETXTBSY,
}

# ANSI escape codes for interactive mode
GREEN_FG: Final[str] = "\033[32m"
YELLOW_FG: Final[str] = "\033[33m"
BLUE_FG: Final[str] = "\033[94m"
MAGENTA_FG: Final[str] = "\033[35m"
CYAN_FG: Final[str] = "\033[36m"
RED_FG: Final[str] = "\033[31m"
DIM_STYLE: Final[str] = "\033[2m"
BOLD_STYLE: Final[str] = "\033[1m"
RESET_STYLE: Final[str] = "\033[0m"
