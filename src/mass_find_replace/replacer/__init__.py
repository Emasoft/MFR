#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial creation of replacer submodule
# - Added exports for all replacer submodules
#

"""
Replacer submodule for Mass Find Replace.

This module breaks down the replacement logic into smaller, focused components.
"""

from .executor import replace_occurrences
from .loader import load_replacement_map
from .logging_utils import log_message
from .normalization import strip_diacritics, strip_control_characters
from .patterns import compile_patterns
from .state import (
    reset_module_state,
    get_raw_mapping,
    set_raw_mapping,
    get_scan_pattern,
    set_scan_pattern,
    get_replace_pattern,
    set_replace_pattern,
    is_mapping_loaded,
    set_mapping_loaded,
    get_sorted_keys,
    set_sorted_keys,
    get_module_logger,
    set_module_logger,
    get_key_character_set,
    add_key_characters,
    is_debug_enabled,
)
from .validation import validate_replacement_mapping_structure

__all__ = [
    # Executor
    "replace_occurrences",
    # Loader
    "load_replacement_map",
    # Logging
    "log_message",
    # Normalization
    "strip_diacritics",
    "strip_control_characters",
    # Patterns
    "compile_patterns",
    # State management
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
    # Validation
    "validate_replacement_mapping_structure",
]
