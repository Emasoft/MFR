#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of display functions from mass_find_replace.py
# - This module contains UI display utilities
#

"""
Display utilities for Mass Find Replace.

This module provides functions for displaying information to users in a formatted way.
"""

from __future__ import annotations

import logging
from typing import Final

# Color codes
GREEN: Final[str] = "\033[92m"
RED: Final[str] = "\033[91m"
RESET: Final[str] = "\033[0m"
YELLOW: Final[str] = "\033[93m"
BLUE: Final[str] = "\033[94m"
DIM: Final[str] = "\033[2m"

__all__ = [
    "print_mapping_table",
    "get_operation_description",
    # Export color codes
    "GREEN",
    "RED",
    "RESET",
    "YELLOW",
    "BLUE",
    "DIM",
]


def print_mapping_table(
    mapping: dict[str, str],
    logger: logging.Logger | logging.LoggerAdapter[logging.Logger],
) -> None:
    """Print the replacement mapping as a formatted table.

    Args:
        mapping: Dictionary of search->replace mappings
        logger: Logger instance
    """
    if not mapping:
        logger.info("Replacement mapping is empty.")
        return

    # Calculate column widths
    max_key_len = max(len(k) for k in mapping)
    max_val_len = max(len(v) for v in mapping.values())
    col1_width = max(max_key_len, 15)
    col2_width = max(max_val_len, 15)

    # Unicode box drawing characters
    top_left = "┏"
    top_right = "┓"
    bottom_left = "┗"
    bottom_right = "┛"
    horizontal = "━"
    vertical = "┃"
    cross = "╋"
    t_down = "┳"
    t_up = "┻"

    # Header
    print(f"\n{YELLOW}Replacement Mapping:{RESET}")
    print(f"{top_left}{horizontal * (col1_width + 2)}{t_down}{horizontal * (col2_width + 2)}{top_right}")
    print(f"{vertical} {'Search'.center(col1_width)} {vertical} {'Replace'.center(col2_width)} {vertical}")
    print(f"{vertical}{horizontal * (col1_width + 2)}{cross}{horizontal * (col2_width + 2)}{vertical}")

    # Data rows
    for search_str, replace_str in mapping.items():
        print(f"{vertical} {search_str.ljust(col1_width)} {vertical} {replace_str.ljust(col2_width)} {vertical}")

    # Footer
    print(f"{bottom_left}{horizontal * (col1_width + 2)}{t_up}{horizontal * (col2_width + 2)}{bottom_right}")


def get_operation_description(skip_file: bool, skip_folder: bool, skip_content: bool) -> str:
    """Get a human-readable description of operations to be performed.

    Args:
        skip_file: Whether file renaming is skipped
        skip_folder: Whether folder renaming is skipped
        skip_content: Whether content modification is skipped

    Returns:
        Description string
    """
    operations = []
    if not skip_file:
        operations.append("file names")
    if not skip_folder:
        operations.append("folder names")
    if not skip_content:
        operations.append("file contents")

    if not operations:
        return "nothing (all operations skipped)"
    if len(operations) == 1:
        return operations[0]
    if len(operations) == 2:
        return f"{operations[0]} and {operations[1]}"
    return f"{operations[0]}, {operations[1]}, and {operations[2]}"
