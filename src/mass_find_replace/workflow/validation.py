#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of validation logic from mass_find_replace.py
# - This module contains workflow validation functions
#

"""
Validation utilities for the Mass Find Replace workflow.

This module provides functions for validating directories, files, and workflow state.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..file_system_operations import (
    load_transactions,
    TransactionStatus,
)
from typing import Final

# Import constants from core
from ..core.config import MAIN_TRANSACTION_FILE_NAME

__all__ = [
    "check_existing_transactions",
    "validate_directory",
    "validate_mapping_file",
]


def check_existing_transactions(directory: Path, logger: logging.Logger | logging.LoggerAdapter[logging.Logger]) -> tuple[bool, int]:
    """Check for existing incomplete transactions.

    Args:
        directory: Directory to check for transaction file
        logger: Logger instance

    Returns:
        Tuple of (has_existing_transactions, completion_percentage)
    """
    txn_file = directory / MAIN_TRANSACTION_FILE_NAME
    if not txn_file.exists():
        return False, 0

    try:
        transactions = load_transactions(txn_file, logger=logger)
        if not transactions:
            return False, 0

        total = len(transactions)
        completed = sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.COMPLETED.value)
        skipped = sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.SKIPPED.value)
        progress = int((completed + skipped) / total * 100) if total > 0 else 0

        # Check if there are any incomplete transactions
        has_incomplete = any(tx.get("STATUS") not in [TransactionStatus.COMPLETED.value, TransactionStatus.SKIPPED.value] for tx in transactions)

        return has_incomplete, progress
    except Exception as e:
        logger.warning(f"Could not read existing transaction file: {e}")
        return False, 0


def validate_directory(directory: str, logger: logging.Logger | logging.LoggerAdapter[logging.Logger]) -> Path | None:
    """Validate and normalize the directory path.

    Args:
        directory: Directory path to validate
        logger: Logger instance

    Returns:
        Normalized absolute path or None if validation fails
    """
    try:
        abs_root_dir = Path(directory).resolve(strict=False)
    except Exception as e:
        logger.error(f"Error: Invalid directory path '{directory}': {e}")
        return None

    if not abs_root_dir.exists():
        logger.error(f"Error: Root directory '{abs_root_dir}' not found.")
        return None
    if not abs_root_dir.is_dir():
        logger.error(f"Error: Path '{abs_root_dir}' is not a directory.")
        return None

    # Check if directory is empty
    try:
        if not any(abs_root_dir.iterdir()):
            logger.info(f"Target directory '{abs_root_dir}' is empty. Nothing to do.")
            return None
    except FileNotFoundError:
        logger.error(f"Error: Root directory '{abs_root_dir}' disappeared before empty check.")
        return None
    except OSError as e:
        logger.error(f"Error accessing directory '{abs_root_dir}' for empty check: {e}")
        return None

    return abs_root_dir


def validate_mapping_file(mapping_file: str, logger: logging.Logger | logging.LoggerAdapter[logging.Logger]) -> Path | None:
    """Validate the mapping file path.

    Args:
        mapping_file: Path to mapping file
        logger: Logger instance

    Returns:
        Normalized absolute path or None if validation fails
    """
    try:
        map_file_path = Path(mapping_file).resolve(strict=False)
    except Exception as e:
        logger.error(f"Error: Invalid mapping file path '{mapping_file}': {e}")
        return None

    if not map_file_path.is_file():
        logger.error(f"Error: Mapping file '{map_file_path}' not found or is not a file.")
        return None

    return map_file_path
