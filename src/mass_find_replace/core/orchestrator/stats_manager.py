#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of statistics management from transaction_orchestrator.py
# - This module handles transaction execution statistics
#

"""
Statistics manager for the Mass Find Replace orchestrator.

This module provides functionality for tracking and updating execution
statistics during transaction processing.
"""

from __future__ import annotations
from typing import Any

from ..types import TransactionStatus

__all__ = [
    "initialize_stats",
    "update_stats_for_status",
    "calculate_final_stats",
]


def initialize_stats(transactions: list[dict[str, Any]]) -> dict[str, int]:
    """Initialize statistics dictionary.

    Args:
        transactions: List of all transactions

    Returns:
        Statistics dictionary
    """
    return {
        "total": len(transactions),
        "completed": 0,
        "failed": 0,
        "skipped": 0,
        "retry_later": 0,
    }


def update_stats_for_status(
    stats: dict[str, int],
    status: TransactionStatus,
) -> None:
    """Update statistics based on transaction status.

    Args:
        stats: Statistics dictionary to update
        status: Transaction status
    """
    if status == TransactionStatus.COMPLETED:
        stats["completed"] += 1
    elif status == TransactionStatus.FAILED:
        stats["failed"] += 1
    elif status == TransactionStatus.SKIPPED:
        stats["skipped"] += 1
    elif status == TransactionStatus.RETRY_LATER:
        stats["retry_later"] += 1


def calculate_final_stats(
    transactions: list[dict[str, Any]],
    content_txs: list[dict[str, Any]],
) -> dict[str, int]:
    """Calculate final statistics after all processing.

    Args:
        transactions: All transactions
        content_txs: Content transactions that were batch processed

    Returns:
        Final statistics dictionary
    """
    stats = {
        "total": len(transactions),
        "completed": 0,
        "failed": 0,
        "skipped": 0,
        "retry_later": 0,
    }

    # Count statuses from all transactions
    for tx in transactions:
        status = tx.get("STATUS", "")
        if status == TransactionStatus.COMPLETED.value:
            stats["completed"] += 1
        elif status == TransactionStatus.FAILED.value:
            stats["failed"] += 1
        elif status == TransactionStatus.SKIPPED.value:
            stats["skipped"] += 1
        elif status == TransactionStatus.RETRY_LATER.value:
            stats["retry_later"] += 1

    return stats
