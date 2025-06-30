#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of execute_all_transactions from file_system_operations.py
# - This module orchestrates the execution of all transactions
# - Refactored to use submodules for better organization
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

from ..utils import (
    log_fs_op_message,
    log_collision_error,
)
from .constants import (
    RED_FG,
    RESET_STYLE,
    DIM_STYLE,
)
from .types import (
    LoggerType,
    TransactionType,
    TransactionStatus,
)
from .transaction_manager import (
    load_transactions,
    save_transactions,
    update_transaction_status_in_list,
)
from .file_processor import (
    group_and_process_file_transactions,
)

# Import from orchestrator submodules
from .orchestrator.collision_detector import check_rename_collision
from .orchestrator.interactive_handler import (
    prompt_user_for_transaction,
    print_transaction_result,
    print_execution_summary,
)
from .orchestrator.retry_handler import (
    identify_retryable_transactions,
    handle_retry_wait,
)
from .orchestrator.stats_manager import (
    initialize_stats,
    update_stats_for_status,
)
from .orchestrator.transaction_processor import (
    process_rename_transaction,
    should_skip_transaction,
    prepare_content_transaction,
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

    # Track which transactions we've seen to prevent duplicate processing
    if not dry_run and resume:
        for tx in transactions:
            if tx["STATUS"] == TransactionStatus.COMPLETED.value and tx.get("ERROR_MESSAGE") == "DRY_RUN":
                tx["STATUS"] = TransactionStatus.PENDING.value
                tx.pop("ERROR_MESSAGE", None)
    seen_transaction_ids = set([tx["id"] for tx in transactions])

    # If resuming, reset statuses that need processing
    if resume:
        reset_transactions = []
        for tx in transactions:
            if tx["STATUS"] in [
                TransactionStatus.FAILED.value,
                TransactionStatus.RETRY_LATER.value,
            ]:
                tx["STATUS"] = TransactionStatus.PENDING.value
                tx.pop("ERROR_MESSAGE", None)
                reset_transactions.append(tx)
        if reset_transactions and logger:
            logger.info(f"Reset {len(reset_transactions)} transactions to PENDING for retry.")

    finished = False
    pass_count = 0

    while not finished and pass_count < MAX_RETRY_PASSES:
        pass_count += 1
        items_still_requiring_retry = []

        for tx_item in [tx for tx in transactions if tx["id"] in seen_transaction_ids]:
            tx_id = tx_item["id"]
            tx_type = tx_item["TYPE"]
            relative_path_str = tx_item["PATH"]
            status = tx_item.get("STATUS", TransactionStatus.PENDING.value)

            if status != TransactionStatus.PENDING.value:
                continue

            # Check timeout
            if timeout_seconds is not None and (time.time() - start_time) > timeout_seconds:
                if logger:
                    logger.warning("Timeout reached during transaction execution retry loop.")
                finished = True
                break

            # Pre-check for collisions in interactive mode
            if (
                interactive_mode
                and not dry_run
                and tx_type
                in [
                    TransactionType.FILE_NAME.value,
                    TransactionType.FOLDER_NAME.value,
                ]
            ):
                has_collision, collision_path, collision_type = check_rename_collision(
                    tx_item,
                    root_dir,
                    path_translation_map,
                    path_cache,
                    dry_run,
                    logger,
                )

                if has_collision:
                    # Log the collision
                    current_abs_path = path_cache.get(relative_path_str) or root_dir / relative_path_str
                    log_collision_error(
                        root_dir,
                        tx_item,
                        current_abs_path,
                        collision_path,
                        collision_type,
                        logger,
                    )
                    # Update status
                    error_msg = f"Collision detected with {collision_path}"
                    update_transaction_status_in_list(
                        transactions,
                        tx_id,
                        TransactionStatus.FAILED,
                        error_msg,
                        logger=logger,
                    )
                    update_stats_for_status(stats, TransactionStatus.FAILED)
                    # Print result for user
                    print(f"{RED_FG}✗ FAILED{RESET_STYLE} - {tx_type}: {relative_path_str}")
                    print(f"  {DIM_STYLE}Collision with existing file/folder{RESET_STYLE}")
                    continue

            # Interactive mode prompt (only for non-collision cases)
            if interactive_mode and not dry_run:
                choice = prompt_user_for_transaction(tx_item)
                if choice == "SKIP":
                    update_transaction_status_in_list(
                        transactions,
                        tx_id,
                        TransactionStatus.SKIPPED,
                        "Skipped by user",
                        logger=logger,
                    )
                    update_stats_for_status(stats, TransactionStatus.SKIPPED)
                    print_transaction_result("SKIPPED")
                    continue
                elif choice == "QUIT":
                    if logger:
                        logger.info("Operation aborted by user.")
                    finished = True
                    break
                # else proceed with execution

            try:
                # Check if transaction should be skipped
                should_skip, skip_reason = should_skip_transaction(
                    tx_item,
                    skip_file_renaming,
                    skip_folder_renaming,
                    skip_content,
                )

                if should_skip:
                    update_transaction_status_in_list(
                        transactions,
                        tx_id,
                        TransactionStatus.SKIPPED,
                        skip_reason,
                        logger=logger,
                    )
                    update_stats_for_status(stats, TransactionStatus.SKIPPED)
                    continue

                # Process transaction based on type
                if tx_type in [TransactionType.FILE_NAME.value, TransactionType.FOLDER_NAME.value]:
                    status_result, error_msg_result, changed = process_rename_transaction(
                        tx_item,
                        root_dir,
                        path_translation_map,
                        path_cache,
                        dry_run,
                        logger,
                    )

                    # Update transaction status
                    if status_result == TransactionStatus.COMPLETED:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.COMPLETED,
                            "DRY_RUN" if dry_run else None,
                            logger=logger,
                        )
                        update_stats_for_status(stats, TransactionStatus.COMPLETED)
                        if interactive_mode and not dry_run:
                            print_transaction_result("COMPLETED")
                    elif status_result == TransactionStatus.SKIPPED:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.SKIPPED,
                            error_msg_result,
                            logger=logger,
                        )
                        update_stats_for_status(stats, TransactionStatus.SKIPPED)
                        if interactive_mode and not dry_run:
                            print_transaction_result("SKIPPED", error_msg_result)
                    else:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.FAILED,
                            error_msg_result,
                            logger=logger,
                        )
                        update_stats_for_status(stats, TransactionStatus.FAILED)
                        items_still_requiring_retry.append(tx_item)
                        if interactive_mode and not dry_run:
                            print_transaction_result("FAILED", error_msg_result)

                elif tx_type == TransactionType.FILE_CONTENT_LINE.value:
                    # Check if content should be skipped
                    should_skip, skip_reason = prepare_content_transaction(tx_item)
                    if should_skip:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.SKIPPED,
                            skip_reason,
                            logger=logger,
                        )
                        update_stats_for_status(stats, TransactionStatus.SKIPPED)
                        continue

                    if dry_run:
                        # For dry-run, mark as completed without modifying file
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.COMPLETED,
                            "DRY_RUN",
                            logger=logger,
                        )
                        update_stats_for_status(stats, TransactionStatus.COMPLETED)
                    else:
                        # Defer actual content line processing to batch/group processor
                        pass
                else:
                    update_transaction_status_in_list(
                        transactions,
                        tx_id,
                        TransactionStatus.SKIPPED,
                        "Unknown transaction type",
                        logger=logger,
                    )
                    update_stats_for_status(stats, TransactionStatus.SKIPPED)

            except Exception as e:
                update_transaction_status_in_list(
                    transactions,
                    tx_id,
                    TransactionStatus.FAILED,
                    f"Exception: {e}",
                    logger=logger,
                )
                update_stats_for_status(stats, TransactionStatus.FAILED)
                items_still_requiring_retry.append(tx_item)

            # Track we've processed this transaction
            if tx_id in seen_transaction_ids:
                seen_transaction_ids.remove(tx_id)

        if not items_still_requiring_retry:
            finished = True
            break

        # Identify and handle retries
        if items_still_requiring_retry:
            retryable_items = identify_retryable_transactions(
                items_still_requiring_retry,
                transactions,
                logger,
            )

            if retryable_items:
                handle_retry_wait(retryable_items, pass_count, logger)
            else:
                # No retryable items, we're done
                finished = True

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
