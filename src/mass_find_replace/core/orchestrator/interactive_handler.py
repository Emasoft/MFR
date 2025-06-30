#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of interactive mode handling from transaction_orchestrator.py
# - This module handles user prompts and decisions in interactive mode
#

"""
Interactive mode handler for the Mass Find Replace orchestrator.

This module provides functionality for user interaction during transaction
execution, including approval prompts and status display.
"""

from __future__ import annotations
from typing import Any, Literal
from pathlib import Path

from ..types import TransactionType
from ..constants import (
    GREEN_FG,
    YELLOW_FG,
    RED_FG,
    DIM_STYLE,
    BOLD_STYLE,
    RESET_STYLE,
    COLLISIONS_ERRORS_LOG_FILE,
    BINARY_MATCHES_LOG_FILE,
)
from ... import replace_logic

__all__ = [
    "prompt_user_for_transaction",
    "print_transaction_result",
    "print_execution_summary",
    "UserChoice",
]


# User choice enum
UserChoice = Literal["APPROVE", "SKIP", "QUIT"]


def prompt_user_for_transaction(
    tx_item: dict[str, Any],
) -> UserChoice:
    """Prompt user for approval of a transaction.

    Args:
        tx_item: Transaction dictionary

    Returns:
        User's choice: APPROVE, SKIP, or QUIT
    """
    tx_id = tx_item["id"]
    tx_type = tx_item["TYPE"]
    relative_path_str = tx_item["PATH"]

    # Show transaction details
    print(f"{DIM_STYLE}Transaction {tx_id} - Type: {tx_type}, Path: {relative_path_str}{RESET_STYLE}")

    if tx_type in [TransactionType.FILE_NAME.value, TransactionType.FOLDER_NAME.value]:
        original_name = tx_item.get("ORIGINAL_NAME", "")
        new_name = tx_item.get("NEW_NAME", replace_logic.replace_occurrences(original_name))
        print(f"  {original_name} → {new_name}")
    elif tx_type == TransactionType.FILE_CONTENT_LINE.value:
        line_num = tx_item.get("LINE_NUMBER", 0)
        print(f"  Line {line_num}: content replacement")

    # Get user input
    choice = input("Approve? (A/Approve, S/Skip, Q/Quit): ").strip().upper()

    if choice == "S":
        return "SKIP"
    elif choice == "Q":
        return "QUIT"
    else:
        return "APPROVE"


def print_transaction_result(
    status: str,
    error_msg: str | None = None,
) -> None:
    """Print the result of a transaction execution.

    Args:
        status: Transaction status
        error_msg: Optional error message
    """
    if status == "COMPLETED":
        print(f"{GREEN_FG}✓ SUCCESS{RESET_STYLE}")
    elif status == "SKIPPED":
        msg = f"{YELLOW_FG}⊘ SKIPPED{RESET_STYLE}"
        if error_msg:
            msg += f" - {error_msg}"
        print(msg)
    elif status == "FAILED":
        msg = f"{RED_FG}✗ FAILED{RESET_STYLE}"
        if error_msg:
            msg += f" - {error_msg}"
        print(msg)


def print_execution_summary(
    stats: dict[str, int],
    root_dir: Path,
) -> None:
    """Print execution summary for interactive mode.

    Args:
        stats: Statistics dictionary
        root_dir: Root directory
    """
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
