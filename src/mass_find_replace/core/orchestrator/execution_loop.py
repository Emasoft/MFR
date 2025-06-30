#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of main execution loop from transaction_orchestrator.py
# - This module handles the main retry loop for transaction execution
#

"""
Main execution loop for the Mass Find Replace orchestrator.

This module contains the core transaction execution loop with retry logic
and state management.
"""

from __future__ import annotations
import time
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import LoggerType

from ..types import TransactionType, TransactionStatus
from ..constants import (
    RED_FG,
    RESET_STYLE,
    DIM_STYLE,
)
from ...utils import log_collision_error
from ..transaction_manager import update_transaction_status_in_list
from .collision_detector import check_rename_collision
from .interactive_handler import (
    prompt_user_for_transaction,
    print_transaction_result,
)
from .retry_handler import (
    identify_retryable_transactions,
    handle_retry_wait,
)
from .stats_manager import update_stats_for_status
from .transaction_processor import (
    process_rename_transaction,
    should_skip_transaction,
    prepare_content_transaction,
)

__all__ = [
    "prepare_transactions_for_resume",
    "execute_transaction_loop",
]


def prepare_transactions_for_resume(
    transactions: list[dict[str, Any]],
    dry_run: bool,
    resume: bool,
    logger: LoggerType = None,
) -> set[str]:
    """Prepare transactions for resume mode.

    Args:
        transactions: List of all transactions
        dry_run: Whether this is a dry run
        resume: Whether we're resuming
        logger: Optional logger instance

    Returns:
        Set of transaction IDs to process
    """
    seen_transaction_ids = set([tx["id"] for tx in transactions])

    # Reset dry-run completed transactions if not in dry-run mode
    if not dry_run and resume:
        for tx in transactions:
            if tx["STATUS"] == TransactionStatus.COMPLETED.value and tx.get("ERROR_MESSAGE") == "DRY_RUN":
                tx["STATUS"] = TransactionStatus.PENDING.value
                tx.pop("ERROR_MESSAGE", None)

    # Reset failed/retry transactions for resume
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

    return seen_transaction_ids


def execute_transaction_loop(
    transactions: list[dict[str, Any]],
    seen_transaction_ids: set[str],
    stats: dict[str, int],
    root_dir: Path,
    path_translation_map: dict[str, str],
    path_cache: dict[str, Path],
    dry_run: bool,
    interactive_mode: bool,
    skip_file_renaming: bool,
    skip_folder_renaming: bool,
    skip_content: bool,
    timeout_seconds: float | None,
    start_time: float,
    max_retry_passes: int,
    logger: LoggerType = None,
) -> bool:
    """Execute the main transaction processing loop.

    Args:
        transactions: List of all transactions
        seen_transaction_ids: Set of transaction IDs to process
        stats: Statistics dictionary
        root_dir: Root directory
        path_translation_map: Path translation mapping
        path_cache: Path cache
        dry_run: Whether this is a dry run
        interactive_mode: Whether to run in interactive mode
        skip_file_renaming: Skip file rename operations
        skip_folder_renaming: Skip folder rename operations
        skip_content: Skip content operations
        timeout_seconds: Timeout in seconds
        start_time: Start time for timeout calculation
        max_retry_passes: Maximum number of retry passes
        logger: Optional logger instance

    Returns:
        True if finished, False if aborted
    """
    finished = False
    pass_count = 0

    while not finished and pass_count < max_retry_passes:
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
                    return False  # Aborted
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

    return True  # Finished normally
