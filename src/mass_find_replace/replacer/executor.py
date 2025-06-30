#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of replacement execution logic from replace_logic.py
# - This module handles the actual text replacement operations
#

"""
Replacement executor for the Mass Find Replace replacer.

This module handles the actual execution of text replacements based on
the loaded mapping and compiled patterns.
"""

from __future__ import annotations
import re
import logging
import unicodedata
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

from .normalization import strip_diacritics, strip_control_characters
from .state import (
    get_raw_mapping,
    get_replace_pattern,
    is_mapping_loaded,
    get_module_logger,
    is_debug_enabled,
)
from .logging_utils import log_message

__all__ = [
    "replace_occurrences",
]


def _actual_replace_callback(match: re.Match[str]) -> str:
    """Callback function for regex replacement.

    Args:
        match: Regex match object

    Returns:
        Replacement string or original if not found
    """
    matched_text_from_input = match.group(0)

    temp_stripped_no_controls = strip_control_characters(matched_text_from_input)
    temp_stripped_no_diacritics = strip_diacritics(temp_stripped_no_controls)
    lookup_key = unicodedata.normalize("NFC", temp_stripped_no_diacritics)

    log_message(
        logging.DEBUG,
        f"DEBUG_CALLBACK: Matched segment (original from input)='{matched_text_from_input}'",
        get_module_logger(),
    )
    log_message(
        logging.DEBUG,
        f"  Canonicalized lookup_key='{lookup_key}' (len {len(lookup_key)}, " f"ords={[ord(c) for c in lookup_key]})",
        get_module_logger(),
    )

    raw_mapping = get_raw_mapping()
    log_message(
        logging.DEBUG,
        f"  _RAW_REPLACEMENT_MAPPING at callback (first 5 keys): " f"{list(raw_mapping.keys())[:5]}...",
        get_module_logger(),
    )

    replacement_value = raw_mapping.get(lookup_key)

    if replacement_value is not None:
        log_message(
            logging.DEBUG,
            f"  Found in map. Replacing with: '{replacement_value}'",
            get_module_logger(),
        )
        return replacement_value

    warning_msg = (
        f"REPLACE_LOGIC_WARN_CALLBACK_LOOKUP_FAILED: lookup_key '{lookup_key}' "
        f"(ords={[ord(c) for c in lookup_key]}) "
        f"derived from matched_text_from_input '{matched_text_from_input}' "
        f"(ords={[ord(c) for c in matched_text_from_input]}) "
        f"NOT FOUND in _RAW_REPLACEMENT_MAPPING (size: {len(raw_mapping)}). "
        f"Returning original matched text."
    )
    log_message(logging.WARNING, warning_msg, get_module_logger())
    log_message(
        logging.DEBUG,
        f"  Full _RAW_REPLACEMENT_MAPPING keys (first 20): " f"{list(raw_mapping.keys())[:20]}...",
        get_module_logger(),
    )
    return matched_text_from_input


def replace_occurrences(input_string: str) -> str:
    """Replace all occurrences of mapped strings in the input.

    Args:
        input_string: String to process for replacements

    Returns:
        String with all replacements applied
    """
    if is_debug_enabled():
        entry_debug_msg = f"REPLACE_OCC_ENTRY: input='{input_string[:30] if isinstance(input_string, str) else str(input_string)[:30]}...', " f"_MAPPING_LOADED={is_mapping_loaded()}, " f"pattern_is_set={get_replace_pattern() is not None}, " f"map_is_populated={bool(get_raw_mapping())}"
        log_message(logging.DEBUG, entry_debug_msg, get_module_logger())

    # Ensure input is normalized to NFC for consistent matching
    if isinstance(input_string, str):
        normalized_input = unicodedata.normalize("NFC", input_string)
    else:
        normalized_input = input_string

    pattern = get_replace_pattern()
    raw_mapping = get_raw_mapping()

    if not is_mapping_loaded() or not pattern or not raw_mapping or not isinstance(normalized_input, str):
        log_message(
            logging.DEBUG,
            f"DEBUG_REPLACE_OCCURRENCES: Early exit. _MAPPING_LOADED={is_mapping_loaded()}, " f"_COMPILED_PATTERN_FOR_ACTUAL_REPLACE is {'None' if pattern is None else 'Set'}, " f"_RAW_REPLACEMENT_MAPPING is {'Empty' if not raw_mapping else 'Populated'}",
            get_module_logger(),
        )
        return normalized_input if isinstance(normalized_input, str) else input_string

    # Use the normalized version for matching
    search_result = pattern.search(normalized_input)
    log_message(
        logging.DEBUG,
        f"DEBUG_REPLACE_OCCURRENCES: Input (original): {input_string!r}, " f"Search found: {'YES' if search_result else 'NO'}",
        get_module_logger(),
    )
    if search_result:
        log_message(
            logging.DEBUG,
            f"DEBUG_REPLACE_OCCURRENCES: Search match object: {search_result}",
            get_module_logger(),
        )

    # Perform actual replacement using the normalized version
    result = pattern.sub(_actual_replace_callback, normalized_input)
    log_message(
        logging.DEBUG,
        f"DEBUG_REPLACE_OCCURRENCES: Result after replacement: {result!r}",
        get_module_logger(),
    )
    return result
