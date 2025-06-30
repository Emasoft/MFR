#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of module state management from replace_logic.py
# - This module handles global state for the replacer
#

"""
State management for the Mass Find Replace replacer.

This module manages the global state of the replacer including loaded mappings,
compiled patterns, and other module-level variables.
"""

from __future__ import annotations
import re
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

# --- Module-level state ---
_RAW_REPLACEMENT_MAPPING: dict[str, str] = {}  # Stores (normalized stripped key) -> (stripped value) from JSON.
_COMPILED_PATTERN_FOR_SCAN: re.Pattern[str] | None = None  # For initial scan. Now case-sensitive.
_MAPPING_LOADED: bool = False
_SORTED_RAW_KEYS_FOR_REPLACE: list[str] = []  # Normalized stripped keys, sorted by length desc.
_COMPILED_PATTERN_FOR_ACTUAL_REPLACE: re.Pattern[str] | None = None  # For actual replacement. Now case-sensitive.
_MODULE_LOGGER: Logger | LoggerAdapter[Logger] | None = None  # Module-level logger instance
_KEY_CHARACTER_SET: set[str] = set()

# --- START DEBUG CONFIG ---
# Set to True to enable verbose debug prints in this module
_DEBUG_REPLACE_LOGIC = False
# --- END DEBUG CONFIG ---

__all__ = [
    "reset_module_state",
    "get_raw_mapping",
    "set_raw_mapping",
    "get_scan_pattern",
    "set_scan_pattern",
    "get_replace_pattern",
    "set_replace_pattern",
    "is_mapping_loaded",
    "set_mapping_loaded",
    "get_sorted_keys",
    "set_sorted_keys",
    "get_module_logger",
    "set_module_logger",
    "get_key_character_set",
    "add_key_characters",
    "is_debug_enabled",
    "_DEBUG_REPLACE_LOGIC",
]


def reset_module_state() -> None:
    """
    Resets all global module-level variables to their initial states.
    This is crucial for ensuring a clean state when the module's functions
    might be called multiple times within the same process, e.g., in tests
    or sequential script runs.
    """
    global _RAW_REPLACEMENT_MAPPING, _COMPILED_PATTERN_FOR_SCAN, _MAPPING_LOADED
    global _SORTED_RAW_KEYS_FOR_REPLACE, _COMPILED_PATTERN_FOR_ACTUAL_REPLACE
    global _MODULE_LOGGER, _KEY_CHARACTER_SET

    _RAW_REPLACEMENT_MAPPING = {}
    _COMPILED_PATTERN_FOR_SCAN = None
    _MAPPING_LOADED = False
    _SORTED_RAW_KEYS_FOR_REPLACE = []
    _COMPILED_PATTERN_FOR_ACTUAL_REPLACE = None
    _MODULE_LOGGER = None  # Reset logger; it will be (re)set by load_replacement_map
    _KEY_CHARACTER_SET.clear()


# Getter/Setter functions for module state
def get_raw_mapping() -> dict[str, str]:
    """Get the raw replacement mapping."""
    return _RAW_REPLACEMENT_MAPPING


def set_raw_mapping(mapping: dict[str, str]) -> None:
    """Set the raw replacement mapping."""
    global _RAW_REPLACEMENT_MAPPING
    _RAW_REPLACEMENT_MAPPING = mapping


def get_scan_pattern() -> re.Pattern[str] | None:
    """Get the compiled scan pattern."""
    return _COMPILED_PATTERN_FOR_SCAN


def set_scan_pattern(pattern: re.Pattern[str] | None) -> None:
    """Set the compiled scan pattern."""
    global _COMPILED_PATTERN_FOR_SCAN
    _COMPILED_PATTERN_FOR_SCAN = pattern


def get_replace_pattern() -> re.Pattern[str] | None:
    """Get the compiled replace pattern."""
    return _COMPILED_PATTERN_FOR_ACTUAL_REPLACE


def set_replace_pattern(pattern: re.Pattern[str] | None) -> None:
    """Set the compiled replace pattern."""
    global _COMPILED_PATTERN_FOR_ACTUAL_REPLACE
    _COMPILED_PATTERN_FOR_ACTUAL_REPLACE = pattern


def is_mapping_loaded() -> bool:
    """Check if mapping is loaded."""
    return _MAPPING_LOADED


def set_mapping_loaded(loaded: bool) -> None:
    """Set mapping loaded state."""
    global _MAPPING_LOADED
    _MAPPING_LOADED = loaded


def get_sorted_keys() -> list[str]:
    """Get sorted keys for replacement."""
    return _SORTED_RAW_KEYS_FOR_REPLACE


def set_sorted_keys(keys: list[str]) -> None:
    """Set sorted keys for replacement."""
    global _SORTED_RAW_KEYS_FOR_REPLACE
    _SORTED_RAW_KEYS_FOR_REPLACE = keys


def get_module_logger() -> Logger | LoggerAdapter[Logger] | None:
    """Get the module logger."""
    return _MODULE_LOGGER


def set_module_logger(logger: Logger | LoggerAdapter[Logger] | None) -> None:
    """Set the module logger."""
    global _MODULE_LOGGER
    _MODULE_LOGGER = logger


def get_key_character_set() -> set[str]:
    """Get the set of all characters in keys."""
    return _KEY_CHARACTER_SET


def add_key_characters(chars: str) -> None:
    """Add characters to the key character set."""
    for char in chars:
        _KEY_CHARACTER_SET.add(char)


def is_debug_enabled() -> bool:
    """Check if debug mode is enabled."""
    return _DEBUG_REPLACE_LOGIC
