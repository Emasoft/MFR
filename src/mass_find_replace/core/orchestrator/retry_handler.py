#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of retry logic from transaction_orchestrator.py
# - This module handles retry logic with backoff for failed transactions
#

"""
Retry handler for the Mass Find Replace orchestrator.

This module provides functionality for handling transaction retries
with configurable backoff strategies.
"""

from __future__ import annotations
import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import LoggerType

from ..types import TransactionStatus
from ..constants import (
    QUICK_RETRY_COUNT,
    QUICK_RETRY_DELAY,
    MAX_RETRY_WAIT_TIME,
    RETRY_BACKOFF_MULTIPLIER,
)
from ..transaction_manager import update_transaction_status_in_list

__all__ = [
    "identify_retryable_transactions",
    "calculate_retry_wait_time",
    "handle_retry_wait",
]


def identify_retryable_transactions(
    failed_transactions: list[dict[str, Any]],
    all_transactions: list[dict[str, Any]],
    logger: LoggerType = None,
) -> list[dict[str, Any]]:
    """Identify which failed transactions should be retried.

    Args:
        failed_transactions: List of failed transaction items
        all_transactions: All transactions list (for status updates)
        logger: Optional logger instance

    Returns:
        List of retryable transactions
    """
    retryable_items = []

    for tx in failed_transactions:
        error_msg = tx.get("ERROR_MESSAGE", "")
        # Check if error is retryable (permission, access, busy, locked)
        if any(err_str in error_msg.lower() for err_str in ["permission", "access", "busy", "locked"]):
            retryable_items.append(tx)
            update_transaction_status_in_list(
                all_transactions,
                tx["id"],
                TransactionStatus.RETRY_LATER,
                error_msg,
                logger=logger,
            )

    return retryable_items


def calculate_retry_wait_time(pass_count: int) -> float:
    """Calculate wait time based on retry pass count.

    Args:
        pass_count: Current retry pass number

    Returns:
        Wait time in seconds
    """
    if pass_count < QUICK_RETRY_COUNT:
        return QUICK_RETRY_DELAY
    else:
        # After quick retries, wait longer with exponential backoff
        return min(MAX_RETRY_WAIT_TIME, RETRY_BACKOFF_MULTIPLIER * (pass_count - 2))


def handle_retry_wait(
    retryable_items: list[dict[str, Any]],
    pass_count: int,
    logger: LoggerType = None,
) -> None:
    """Handle waiting between retries.

    Args:
        retryable_items: List of transactions to retry
        pass_count: Current retry pass number
        logger: Optional logger instance
    """
    if not retryable_items:
        return

    wait_time = calculate_retry_wait_time(pass_count)

    if pass_count < QUICK_RETRY_COUNT:
        if logger:
            logger.info(f"Retrying {len(retryable_items)} transactions (pass {pass_count})...")
    else:
        if logger:
            logger.info(f"Waiting {wait_time}s before retry (pass {pass_count})...")

    time.sleep(wait_time)
