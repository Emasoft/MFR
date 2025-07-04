#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of pattern management from replace_logic.py
# - This module handles regex pattern compilation and management
#

"""
Pattern management for the Mass Find Replace replacer.

This module handles the creation and management of regex patterns used for
searching and replacing text based on the loaded mapping.
"""

from __future__ import annotations
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

__all__ = [
    "compile_patterns",
]


def compile_patterns(
    sorted_keys: list[str],
    logger: Logger | LoggerAdapter[Logger] | None = None,
) -> tuple[re.Pattern[str] | None, str]:
    """Compile regex patterns from sorted keys.

    Args:
        sorted_keys: List of keys sorted by length (longest first)
        logger: Optional logger instance

    Returns:
        Tuple of (compiled_pattern, error_message)
    """
    # Properly escape keys for regex pattern compilation to handle special regex characters
    pattern_keys_for_scan_and_replace: list[str] = [re.escape(k) for k in sorted_keys]

    combined_pattern_str = r"(" + r"|".join(pattern_keys_for_scan_and_replace) + r")"

    if logger:
        logger.debug(f"Pattern keys after escaping: {pattern_keys_for_scan_and_replace}")

    try:
        compiled_pattern = re.compile(combined_pattern_str)
        return compiled_pattern, ""
    except re.error as e:
        error_msg = f"Could not compile regex pattern: {e}. Regex tried: '{combined_pattern_str}'"
        return None, error_msg
