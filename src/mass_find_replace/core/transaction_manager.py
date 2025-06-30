#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of transaction management functionality from file_system_operations.py
# - Includes save/load transactions and status update functions
#

"""
Transaction management functionality for the Mass Find Replace application.

This module provides functions for saving, loading, and managing transaction
files that track all planned file system operations.
"""

from __future__ import annotations
import os
import json
import uuid
import logging
from pathlib import Path
from typing import Any

from ..utils import (
    SurrogateHandlingEncoder,
    decode_surrogate_escaped_json,
    file_lock,
    log_fs_op_message,
)
from .types import (
    LoggerType,
    TransactionStatus,
)


def save_transactions(
    transactions: list[dict[str, Any]],
    transactions_file_path: Path,
    logger: LoggerType = None,
) -> None:
    """
    Save the list of transactions to a JSON file atomically with file locking.

    Args:
        transactions: List of transaction dictionaries
        transactions_file_path: Path to save the transactions file
        logger: Optional logger instance
    """
    if not transactions:
        log_fs_op_message(logging.WARNING, "No transactions to save.", logger)
        return
    # Use unique temp file name to avoid conflicts
    temp_file_path = transactions_file_path.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
    try:
        with Path(temp_file_path).open("w", encoding="utf-8") as f, file_lock(f, exclusive=True):
            json.dump(transactions, f, indent=2, ensure_ascii=False, cls=SurrogateHandlingEncoder)
        # Atomically replace original file
        os.replace(temp_file_path, transactions_file_path)
    except TimeoutError as e:
        log_fs_op_message(logging.ERROR, f"Could not acquire lock to save transactions: {e}", logger)
        try:
            if temp_file_path.exists():
                os.remove(temp_file_path)
        except OSError:
            pass
        raise
    except Exception as e:
        log_fs_op_message(logging.ERROR, f"Error saving transactions: {e}", logger)
        try:
            if temp_file_path.exists():
                os.remove(temp_file_path)
        except Exception as cleanup_e:
            log_fs_op_message(
                logging.WARNING,
                f"Error cleaning up temp transaction file: {cleanup_e}",
                logger,
            )
        raise


def load_transactions(transactions_file_path: Path, logger: LoggerType = None) -> list[dict[str, Any]] | None:
    """
    Load transactions from a JSON file with file locking.

    Args:
        transactions_file_path: Path to the transactions file
        logger: Optional logger instance

    Returns:
        List of transaction dictionaries or None if file not found/invalid
    """
    if not transactions_file_path.is_file():
        log_fs_op_message(
            logging.WARNING,
            f"Transaction file not found: {transactions_file_path}",
            logger,
        )
        return None
    try:
        with Path(transactions_file_path).open("r", encoding="utf-8") as f:
            with file_lock(f, exclusive=False):  # Shared lock for reading
                data = json.load(f)
        if not isinstance(data, list):
            log_fs_op_message(
                logging.ERROR,
                f"Transaction file {transactions_file_path} does not contain a list.",
                logger,
            )
            return None
        # Decode any surrogate-escaped strings
        decoded_data = decode_surrogate_escaped_json(data)
        # Type check - we know this is a list from the check above
        if not isinstance(decoded_data, list):
            raise TypeError("Decoded transaction data must be a list")
        return decoded_data
    except TimeoutError as e:
        log_fs_op_message(
            logging.ERROR,
            f"Could not acquire lock to read transactions: {e}",
            logger,
        )
        return None
    except Exception as e:
        log_fs_op_message(
            logging.ERROR,
            f"Error loading transactions from {transactions_file_path}: {e}",
            logger,
        )
        return None


def update_transaction_status_in_list(
    transactions: list[dict[str, Any]],
    transaction_id: str,
    new_status: TransactionStatus,
    error_message: str | None = None,
    logger: LoggerType = None,
) -> bool:
    """Update the status and optional error message of a transaction in the list by id.

    Args:
        transactions: List of transaction dictionaries to update
        transaction_id: ID of the transaction to update
        new_status: New status to set
        error_message: Optional error message to add
        logger: Optional logger instance

    Returns:
        True if transaction was found and updated, False otherwise
    """
    for tx in transactions:
        if tx.get("id") == transaction_id:
            tx["STATUS"] = new_status.value
            if error_message is not None:
                tx["ERROR_MESSAGE"] = error_message
            if logger:
                logger.debug(f"Transaction {transaction_id} updated to {new_status.value} with error: {error_message}")
            return True
    if logger:
        logger.warning(f"Transaction {transaction_id} not found for status update.")
    return False
