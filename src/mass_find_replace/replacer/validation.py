#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of mapping validation from replace_logic.py
# - This module handles validation of replacement mapping structure
#

"""
Validation utilities for the Mass Find Replace replacer.

This module provides functions to validate the structure and content of
replacement mapping data loaded from JSON files.
"""

from __future__ import annotations
from typing import Any

__all__ = [
    "validate_replacement_mapping_structure",
]


def validate_replacement_mapping_structure(
    data: Any,
    logger: Any = None,  # Avoid circular import
) -> tuple[bool, str]:
    """Validate the structure of the replacement mapping data.

    Args:
        data: The loaded JSON data
        logger: Optional logger instance

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Root element must be a dictionary/object"

    if "REPLACEMENT_MAPPING" not in data:
        return False, "'REPLACEMENT_MAPPING' key not found"

    raw_mapping = data.get("REPLACEMENT_MAPPING")
    if not isinstance(raw_mapping, dict):
        return False, "'REPLACEMENT_MAPPING' must be a dictionary/object"

    # Check all entries are string -> string
    for key, value in raw_mapping.items():
        if not isinstance(key, str):
            return False, f"Key {repr(key)} is not a string (type: {type(key).__name__})"
        if not isinstance(value, str):
            return False, f"Value for key '{key}' is not a string (type: {type(value).__name__})"

    return True, ""
