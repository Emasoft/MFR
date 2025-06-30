#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of execute_all_transactions from file_system_operations.py
# - This module orchestrates the execution of all transactions
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
    QUICK_RETRY_COUNT,
    QUICK_RETRY_DELAY,
    MAX_RETRY_WAIT_TIME,
    RETRY_BACKOFF_MULTIPLIER,
    COLLISIONS_ERRORS_LOG_FILE,
    BINARY_MATCHES_LOG_FILE,
    GREEN_FG,
    YELLOW_FG,
    RED_FG,
    DIM_STYLE,
    BOLD_STYLE,
    RESET_STYLE,
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
from .transaction_executor import (
    execute_rename_transaction as _execute_rename_transaction,
    _get_current_absolute_path,
)
from .file_processor import (
    group_and_process_file_transactions,
)
from .. import replace_logic


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

    stats = {
        "total": len(transactions),
        "completed": 0,
        "failed": 0,
        "skipped": 0,
        "retry_later": 0,
    }

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

            # Pre-check for collisions in interactive mode to avoid prompting for doomed transactions
            if interactive_mode and not dry_run and tx_type in [TransactionType.FILE_NAME.value, TransactionType.FOLDER_NAME.value]:
                # Pre-flight collision check
                original_name = tx_item.get("ORIGINAL_NAME", "")
                new_name = tx_item.get("NEW_NAME", replace_logic.replace_occurrences(original_name))
                current_abs_path = _get_current_absolute_path(
                    relative_path_str,
                    root_dir,
                    path_translation_map,
                    path_cache,
                    dry_run,
                )
                if current_abs_path.exists():
                    new_abs_path = current_abs_path.parent / new_name
                    parent_dir = current_abs_path.parent
                    new_name_lower = new_name.lower()

                    # Check for collision
                    has_collision = False
                    collision_path = None
                    collision_type = None

                    if new_abs_path.exists():
                        has_collision = True
                        collision_path = new_abs_path
                        collision_type = "exact match"
                    else:
                        # Check case-insensitive
                        try:
                            for existing_item in parent_dir.iterdir():
                                if existing_item != current_abs_path and existing_item.name.lower() == new_name_lower:
                                    has_collision = True
                                    collision_path = existing_item
                                    collision_type = "case-insensitive match"
                                    break
                        except OSError:
                            pass

                    if has_collision:
                        # Log the collision
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
                        stats["failed"] += 1
                        # Print result for user
                        print(f"{RED_FG}✗ FAILED{RESET_STYLE} - {tx_type}: {relative_path_str}")
                        print(f"  {DIM_STYLE}Collision with existing file/folder{RESET_STYLE}")
                        continue

            # Interactive mode prompt (only for non-collision cases)
            if interactive_mode and not dry_run:
                # Show transaction details and ask for approval
                print(f"{DIM_STYLE}Transaction {tx_id} - Type: {tx_type}, Path: {relative_path_str}{RESET_STYLE}")
                if tx_type in [
                    TransactionType.FILE_NAME.value,
                    TransactionType.FOLDER_NAME.value,
                ]:
                    original_name = tx_item.get("ORIGINAL_NAME", "")
                    new_name = tx_item.get("NEW_NAME", replace_logic.replace_occurrences(original_name))
                    print(f"  {original_name} → {new_name}")
                elif tx_type == TransactionType.FILE_CONTENT_LINE.value:
                    line_num = tx_item.get("LINE_NUMBER", 0)
                    print(f"  Line {line_num}: content replacement")

                choice = input("Approve? (A/Approve, S/Skip, Q/Quit): ").strip().upper()
                if choice == "S":
                    update_transaction_status_in_list(
                        transactions,
                        tx_id,
                        TransactionStatus.SKIPPED,
                        "Skipped by user",
                        logger=logger,
                    )
                    stats["skipped"] += 1
                    print(f"{YELLOW_FG}⊘ SKIPPED{RESET_STYLE}")
                    continue
                if choice == "Q":
                    if logger:
                        logger.info("Operation aborted by user.")
                    finished = True
                    break
                # else proceed with execution

            try:
                if tx_type in [
                    TransactionType.FILE_NAME.value,
                    TransactionType.FOLDER_NAME.value,
                ]:
                    if (tx_type == TransactionType.FILE_NAME.value and skip_file_renaming) or (tx_type == TransactionType.FOLDER_NAME.value and skip_folder_renaming):
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.SKIPPED,
                            "Skipped by flags",
                            logger=logger,
                        )
                        stats["skipped"] += 1
                        continue
                    status_result, error_msg, changed = _execute_rename_transaction(
                        tx_item,
                        root_dir,
                        path_translation_map,
                        path_cache,
                        dry_run,
                        logger,
                    )
                    if status_result == TransactionStatus.COMPLETED:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.COMPLETED,
                            "DRY_RUN" if dry_run else None,
                            logger=logger,
                        )
                        stats["completed"] += 1
                        if interactive_mode and not dry_run:
                            print(f"{GREEN_FG}✓ SUCCESS{RESET_STYLE}")
                    elif status_result == TransactionStatus.SKIPPED:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.SKIPPED,
                            error_msg,
                            logger=logger,
                        )
                        stats["skipped"] += 1
                        if interactive_mode and not dry_run:
                            print(f"{YELLOW_FG}⊘ SKIPPED{RESET_STYLE} - {error_msg}")
                    else:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.FAILED,
                            error_msg,
                            logger=logger,
                        )
                        stats["failed"] += 1
                        items_still_requiring_retry.append(tx_item)
                        if interactive_mode and not dry_run:
                            print(f"{RED_FG}✗ FAILED{RESET_STYLE} - {error_msg}")
                elif tx_type == TransactionType.FILE_CONTENT_LINE.value:
                    if skip_content:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.SKIPPED,
                            "Skipped by flag",
                            logger=logger,
                        )
                        stats["skipped"] += 1
                        continue

                    # Get new content from transaction
                    new_line_content = tx_item.get("NEW_LINE_CONTENT", "")
                    original_line_content = tx_item.get("ORIGINAL_LINE_CONTENT", "")

                    # Skip if no actual change (shouldn't happen but added as safeguard)
                    if new_line_content == original_line_content:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.SKIPPED,
                            "No change needed",
                            logger=logger,
                        )
                        stats["skipped"] += 1
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
                        stats["completed"] += 1
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
                    stats["skipped"] += 1
            except Exception as e:
                update_transaction_status_in_list(
                    transactions,
                    tx_id,
                    TransactionStatus.FAILED,
                    f"Exception: {e}",
                    logger=logger,
                )
                stats["failed"] += 1
                items_still_requiring_retry.append(tx_item)

            # Track we've processed this transaction
            if tx_id in seen_transaction_ids:
                seen_transaction_ids.remove(tx_id)

        if not items_still_requiring_retry:
            finished = True
            break

        # Wait and retry logic
        if items_still_requiring_retry:
            # Check if any are retryable errors
            retryable_items = []
            for tx in items_still_requiring_retry:
                error_msg = tx.get("ERROR_MESSAGE", "")
                if any(err_str in error_msg.lower() for err_str in ["permission", "access", "busy", "locked"]):
                    retryable_items.append(tx)
                    update_transaction_status_in_list(
                        transactions,
                        tx["id"],
                        TransactionStatus.RETRY_LATER,
                        error_msg,
                        logger=logger,
                    )

            if retryable_items and pass_count < QUICK_RETRY_COUNT:
                if logger:
                    logger.info(f"Retrying {len(retryable_items)} transactions (pass {pass_count})...")
                time.sleep(QUICK_RETRY_DELAY)  # Brief pause between retries
            elif retryable_items:
                # After quick retries, wait longer
                wait_time = min(MAX_RETRY_WAIT_TIME, RETRY_BACKOFF_MULTIPLIER * (pass_count - 2))
                if logger:
                    logger.info(f"Waiting {wait_time}s before retry (pass {pass_count})...")
                time.sleep(wait_time)
            else:
                # No retryable items, we're done
                finished = True

    # After rename and individual transaction processing, process content transactions grouped by file
    # Only process content transactions that are still pending (not already handled in dry-run)
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

    # Update stats for content transactions after batch processing
    stats["completed"] += sum(1 for tx in content_txs if tx.get("STATUS") == TransactionStatus.COMPLETED.value)
    stats["skipped"] += sum(1 for tx in content_txs if tx.get("STATUS") == TransactionStatus.SKIPPED.value)
    stats["failed"] += sum(1 for tx in content_txs if tx.get("STATUS") == TransactionStatus.FAILED.value)

    # Count all RETRY_LATER transactions in the final stats
    stats["retry_later"] = sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.RETRY_LATER.value)

    save_transactions(transactions, transactions_file_path, logger=logger)
    if logger:
        logger.info(f"Execution phase complete. Stats: {stats}")

    # Print summary for interactive mode
    if interactive_mode and not dry_run:
        print(f"\n{BOLD_STYLE}=== Execution Summary ==={RESET_STYLE}")
        print(f"Total transactions: {stats['total']}")
        print(f"{GREEN_FG}Completed: {stats['completed']}{RESET_STYLE}")
        print(f"{YELLOW_FG}Skipped: {stats['skipped']}{RESET_STYLE}")
        print(f"{RED_FG}Failed: {stats['failed']}{RESET_STYLE}")

        # Check for collision and binary logs
        collision_log_path = root_dir / COLLISIONS_ERRORS_LOG_FILE
        binary_log_path = root_dir / BINARY_MATCHES_LOG_FILE

        if collision_log_path.exists() and collision_log_path.stat().st_size > 0:
            print(f"\n{RED_FG}⚠ File/folder rename collisions were detected.{RESET_STYLE}")
            print(f"  See '{collision_log_path.name}' for details.")

        if binary_log_path.exists() and binary_log_path.stat().st_size > 0:
            print(f"\n{YELLOW_FG}ℹ Matches were found in binary files.{RESET_STYLE}")
            print(f"  See '{binary_log_path.name}' for details.")
            print(f"  {DIM_STYLE}(Binary files were not modified){RESET_STYLE}")

    return stats
