#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of collision detection logic from transaction_orchestrator.py
# - This module handles pre-flight collision checks for rename operations
#

"""
Collision detection for the Mass Find Replace orchestrator.

This module provides functionality to detect file/folder naming collisions
before attempting rename operations.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..types import LoggerType

from ..transaction_executor import _get_current_absolute_path
from ... import replace_logic

__all__ = [
    "check_rename_collision",
]


def check_rename_collision(
    tx_item: dict[str, Any],
    root_dir: Path,
    path_translation_map: dict[str, str],
    path_cache: dict[str, Path],
    dry_run: bool,
    logger: LoggerType = None,
) -> tuple[bool, Path | None, str | None]:
    """Check if a rename operation would cause a collision.

    Args:
        tx_item: Transaction dictionary
        root_dir: Root directory
        path_translation_map: Path translation mapping
        path_cache: Path cache
        dry_run: Whether this is a dry run
        logger: Optional logger instance

    Returns:
        Tuple of (has_collision, collision_path, collision_type)
    """
    relative_path_str = tx_item["PATH"]
    original_name = tx_item.get("ORIGINAL_NAME", "")
    new_name = tx_item.get("NEW_NAME", replace_logic.replace_occurrences(original_name))

    current_abs_path = _get_current_absolute_path(
        relative_path_str,
        root_dir,
        path_translation_map,
        path_cache,
        dry_run,
    )

    if not current_abs_path.exists():
        return False, None, None

    new_abs_path = current_abs_path.parent / new_name
    parent_dir = current_abs_path.parent
    new_name_lower = new_name.lower()

    # Check for exact match collision
    if new_abs_path.exists():
        return True, new_abs_path, "exact match"

    # Check case-insensitive collision
    try:
        for existing_item in parent_dir.iterdir():
            if existing_item != current_abs_path and existing_item.name.lower() == new_name_lower:
                return True, existing_item, "case-insensitive match"
    except OSError:
        pass

    return False, None, None
