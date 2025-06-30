#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of execute_all_transactions from file_system_operations.py
# - This module orchestrates the execution of all transactions
# - Refactored to use submodules for better organization
# - Further extracted execution loop to reduce file size
#

"""
Transaction orchestration for the Mass Find Replace application.

This module contains the main transaction execution orchestrator that
coordinates the execution of all rename and content modification transactions.
"""

from __future__ import annotations
import time
import logging
from pathlib import Path
from typing import Any

from ..utils import log_fs_op_message
from .types import (
    LoggerType,
    TransactionType,
    TransactionStatus,
)
from .transaction_manager import (
    load_transactions,
    save_transactions,
)
from .file_processor import (
    group_and_process_file_transactions,
)

# Import from orchestrator submodules
from .orchestrator.interactive_handler import print_execution_summary
from .orchestrator.stats_manager import initialize_stats
from .orchestrator.execution_loop import (
    prepare_transactions_for_resume,
    execute_transaction_loop,
)

__all__ = [
    "execute_all_transactions",
]


def execute_all_transactions(
    transactions_file_path: Path,
    root_dir: Path,
    dry_run: bool,
    resume: bool,
    timeout_minutes: int,
    skip_file_renaming: bool,
    skip_folder_renaming: bool,
    skip_content: bool,
    interactive_mode: bool,
    logger: LoggerType = None,
) -> dict[str, int]:
    """
    Execute all transactions in the transaction file.
    Returns statistics dictionary.
    """
    # Use timeout_minutes to control retry duration
    MAX_RETRY_PASSES = 1000000  # Large number to allow timeout control
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60 if timeout_minutes > 0 else None

    transactions = load_transactions(transactions_file_path, logger=logger)
    if transactions is None:
        if logger:
            logger.error("No transactions to execute.")
        return {}

    stats = initialize_stats(transactions)

    # Shared path translation for rename operations
    path_translation_map: dict[str, str] = {}
    path_cache: dict[str, Path] = {}

    # Prepare transactions for resume
    seen_transaction_ids = prepare_transactions_for_resume(
        transactions,
        dry_run,
        resume,
        logger,
    )

    # Execute the main transaction loop
    finished_normally = execute_transaction_loop(
        transactions,
        seen_transaction_ids,
        stats,
        root_dir,
        path_translation_map,
        path_cache,
        dry_run,
        interactive_mode,
        skip_file_renaming,
        skip_folder_renaming,
        skip_content,
        timeout_seconds,
        start_time,
        MAX_RETRY_PASSES,
        logger,
    )

    if not finished_normally:
        # User aborted
        save_transactions(transactions, transactions_file_path, logger=logger)
        return stats

    # After rename and individual transaction processing, process content transactions grouped by file
    content_txs = [tx for tx in transactions if tx["TYPE"] == TransactionType.FILE_CONTENT_LINE.value and tx["STATUS"] == TransactionStatus.PENDING.value]

    if content_txs:  # Only process if there are pending content transactions
        group_and_process_file_transactions(
            content_txs,
            root_dir,
            path_translation_map,
            path_cache,
            dry_run,
            skip_content,
            logger,
        )

    # Recalculate final stats from all transactions
    final_stats = {
        "total": len(transactions),
        "completed": sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.COMPLETED.value),
        "skipped": sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.SKIPPED.value),
        "failed": sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.FAILED.value),
        "retry_later": sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.RETRY_LATER.value),
    }

    save_transactions(transactions, transactions_file_path, logger=logger)
    if logger:
        logger.info(f"Execution phase complete. Stats: {final_stats}")

    # Print summary for interactive mode
    if interactive_mode and not dry_run:
        print_execution_summary(final_stats, root_dir)

    return final_stats
