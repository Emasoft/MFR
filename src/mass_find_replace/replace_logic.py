#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE CODE:
# - Fixed regex pattern compilation in load_replacement_map to properly escape keys containing regex special characters.
# - Fixed replace_occurrences to normalize input string to NFC before searching and replacing to ensure consistency.
# - Added tracking of all characters used in replacement keys for optimization purposes.
# - Added accessor function get_key_characters() to retrieve the set of characters used in keys.
# - Refactored to use submodules for better organization and reduced file size
#
# Copyright (c) 2024 Emasoft
#
# This software is licensed under the MIT License.
# Refer to the LICENSE file for more details.

"""
Replacement logic for the Mass Find Replace application.

This module provides the core functionality for loading replacement mappings
and applying text replacements based on configured patterns.
"""

from __future__ import annotations

# Import from submodules
from .replacer.normalization import strip_diacritics, strip_control_characters
from .replacer.validation import validate_replacement_mapping_structure
from .replacer.loader import load_replacement_map
from .replacer.executor import replace_occurrences
from .replacer.state import (
    reset_module_state,
    get_scan_pattern,
    get_sorted_keys,
    get_key_character_set,
    get_raw_mapping,
    is_mapping_loaded,
)


# For backward compatibility, alias some functions
def get_raw_stripped_keys() -> list[str]:
    """Get the sorted list of normalized keys.

    Returns:
        List of keys sorted by length (longest first)
    """
    return get_sorted_keys().copy() if is_mapping_loaded() else []


def get_key_characters() -> set[str]:
    """
    Returns the set of all characters appearing in replacement keys.

    Returns:
        A copy of the set to prevent external modification
    """
    return get_key_character_set().copy()


def get_replacement_mapping() -> dict[str, str]:
    """Get the loaded replacement mapping.

    Returns:
        A copy of the replacement mapping dictionary
    """
    return get_raw_mapping().copy() if is_mapping_loaded() else {}


def get_mapping_size() -> int:
    """Get the number of replacement rules loaded.

    Returns:
        Number of replacement rules
    """
    return len(get_raw_mapping()) if is_mapping_loaded() else 0


# Re-export all public functions
__all__ = [
    # From normalization
    "strip_diacritics",
    "strip_control_characters",
    # From validation
    "validate_replacement_mapping_structure",
    # From loader
    "load_replacement_map",
    # From executor
    "replace_occurrences",
    # From state
    "reset_module_state",
    "get_scan_pattern",
    "is_mapping_loaded",
    # Local compatibility functions
    "get_raw_stripped_keys",
    "get_key_characters",
    "get_replacement_mapping",
    "get_mapping_size",
]
