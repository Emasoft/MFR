#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of transaction execution functionality from file_system_operations.py
# - Includes rename and content line transaction execution functions
#

"""
Transaction execution functionality for the Mass Find Replace application.

This module provides functions for executing individual transactions including
file/folder renames and content line replacements.
"""

from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Any

from .. import replace_logic
from ..utils import (
    log_fs_op_message,
    log_collision_error,
    open_file_with_encoding,
)
from .constants import DEFAULT_ENCODING_FALLBACK
from .types import (
    LoggerType,
    TransactionStatus,
    TransactionType,
)


def _get_current_absolute_path(
    original_relative_path_str: str,
    root_dir: Path,
    path_translation_map: dict[str, str],
    cache: dict[str, Path],
    dry_run: bool = False,
) -> Path:
    """Get the current absolute path for a relative path, accounting for renames.

    This function handles path resolution during the execution phase, taking into
    account any parent directories that may have been renamed.

    Args:
        original_relative_path_str: Original relative path from transaction
        root_dir: Root directory of the project
        path_translation_map: Map of paths to their new names after renames
        cache: Cache of resolved paths for performance
        dry_run: Whether this is a dry-run execution

    Returns:
        Current absolute path accounting for any renames
    """
    if dry_run:
        # During dry run, update virtual mapping to enable child transactions to resolve correctly
        if original_relative_path_str not in path_translation_map:
            # Use original name as fallback
            path_translation_map[original_relative_path_str] = Path(original_relative_path_str).name
        # Compose current absolute path using virtual mapping
        if original_relative_path_str in cache:
            return cache[original_relative_path_str]
        if original_relative_path_str == ".":
            cache["."] = root_dir
            return root_dir
        original_path_obj = Path(original_relative_path_str)
        parent_rel_str = "." if original_path_obj.parent == Path() else str(original_path_obj.parent)
        current_parent_abs_path = _get_current_absolute_path(parent_rel_str, root_dir, path_translation_map, cache, dry_run)
        current_item_name = path_translation_map.get(original_relative_path_str, original_path_obj.name)
        current_abs_path = current_parent_abs_path / current_item_name
        cache[original_relative_path_str] = current_abs_path
        return current_abs_path

    if original_relative_path_str in cache:
        return cache[original_relative_path_str]
    if original_relative_path_str == ".":
        cache["."] = root_dir
        return root_dir
    original_path_obj = Path(original_relative_path_str)
    parent_rel_str = "." if original_path_obj.parent == Path() else str(original_path_obj.parent)
    current_parent_abs_path = _get_current_absolute_path(parent_rel_str, root_dir, path_translation_map, cache, dry_run)
    current_item_name = path_translation_map.get(original_relative_path_str, original_path_obj.name)
    current_abs_path = current_parent_abs_path / current_item_name
    cache[original_relative_path_str] = current_abs_path
    return current_abs_path


def execute_rename_transaction(
    tx: dict[str, Any],
    root_dir: Path,
    path_translation_map: dict[str, str],
    path_cache: dict[str, Path],
    dry_run: bool,
    logger: LoggerType = None,
) -> tuple[TransactionStatus, str, bool]:
    """
    Execute a rename transaction (file or folder).
    Returns (status, error_message, changed_bool).
    """
    original_relative_path_str = tx["PATH"]
    original_name = tx.get("ORIGINAL_NAME", "")
    tx_type = tx["TYPE"]

    # Use precomputed NEW_NAME if available
    new_name = tx.get("NEW_NAME", replace_logic.replace_occurrences(original_name))

    current_abs_path = _get_current_absolute_path(original_relative_path_str, root_dir, path_translation_map, path_cache, dry_run)
    if not dry_run and not current_abs_path.exists():
        return TransactionStatus.FAILED, f"Path not found: {current_abs_path}", False

    if new_name == original_name:
        return TransactionStatus.SKIPPED, f"No change needed: '{original_name}' would remain the same", False

    new_abs_path = current_abs_path.parent / new_name

    # Check for exact match first
    if new_abs_path.exists():
        log_collision_error(root_dir, tx, current_abs_path, new_abs_path, "exact match", logger)
        return (
            TransactionStatus.FAILED,
            f"Target path already exists: {new_abs_path}",
            False,
        )

    # Case-insensitive collision check
    parent_dir = current_abs_path.parent
    new_name_lower = new_name.lower()

    try:
        for existing_item in parent_dir.iterdir():
            # Skip self
            if existing_item == current_abs_path:
                continue
            # Check for case-insensitive match
            if existing_item.name.lower() == new_name_lower:
                log_collision_error(
                    root_dir,
                    tx,
                    current_abs_path,
                    existing_item,
                    "case-insensitive match",
                    logger,
                )
                return (
                    TransactionStatus.FAILED,
                    f"Case-insensitive collision with existing path: {existing_item}",
                    False,
                )
    except OSError as e:
        log_fs_op_message(
            logging.WARNING,
            f"Could not check for collisions in {parent_dir}: {e}",
            logger,
        )

    try:
        if dry_run:
            # Special handling for folders to simulate cascading renames
            if tx_type in [TransactionType.FOLDER_NAME.value]:
                # Create virtual path for simulation
                if original_relative_path_str not in path_translation_map:
                    path_translation_map[original_relative_path_str] = original_name
                path_translation_map[original_relative_path_str] = new_name
                path_cache.pop(original_relative_path_str, None)
                return TransactionStatus.COMPLETED, "DRY_RUN", True
            # Only simulate changes, don't update real path mappings
            return TransactionStatus.COMPLETED, "DRY_RUN", False

        # Actual rename
        os.rename(current_abs_path, new_abs_path)
        path_translation_map[original_relative_path_str] = new_name
        path_cache.pop(original_relative_path_str, None)
        return TransactionStatus.COMPLETED, "", True
    except Exception as e:
        return TransactionStatus.FAILED, f"Rename error: {e}", False


def execute_content_line_transaction(
    tx: dict[str, Any],
    root_dir: Path,
    path_translation_map: dict[str, str],
    path_cache: dict[str, Path],
    logger: LoggerType = None,
) -> tuple[TransactionStatus, str, bool]:
    """
    Execute a content line transaction.
    Returns (status, error_message, changed_bool).
    """
    relative_path_str = tx["PATH"]
    line_no = tx["LINE_NUMBER"]  # 1-indexed
    file_encoding = tx.get("ORIGINAL_ENCODING", DEFAULT_ENCODING_FALLBACK)
    is_rtf = tx.get("IS_RTF", False)

    # Skip RTF as they're converted text files with unique formatting
    if is_rtf:
        return (
            TransactionStatus.SKIPPED,
            "RTF content modification not supported",
            False,
        )

    try:
        # Get current file location (accounts for renames)
        current_abs_path = _get_current_absolute_path(relative_path_str, root_dir, path_translation_map, path_cache, dry_run=False)

        # Read file with original encoding
        with open_file_with_encoding(current_abs_path, "r", file_encoding, logger) as f:
            lines = f.readlines()  # Preserve line endings

        if line_no - 1 < 0 or line_no - 1 >= len(lines):
            return (
                TransactionStatus.FAILED,
                f"Line number {line_no} out of range. File has {len(lines)} lines.",
                False,
            )

        # Get new content from transaction
        new_line_content = tx.get("NEW_LINE_CONTENT", "")

        # Skip if line didn't change (shouldn't happen but safeguard)
        if lines[line_no - 1] == new_line_content:
            return (TransactionStatus.SKIPPED, "Line already matches target", False)

        # Update the line
        lines[line_no - 1] = new_line_content

        # Write back with same encoding
        with open_file_with_encoding(current_abs_path, "w", file_encoding, logger) as f:
            f.writelines(lines)

        return (TransactionStatus.COMPLETED, "", True)
    except Exception as e:
        return (TransactionStatus.FAILED, f"Content update failed: {e}", False)
