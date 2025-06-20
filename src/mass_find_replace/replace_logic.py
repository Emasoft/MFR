#!/usr/bin/env python3
#
# HERE IS THE CHANGELOG FOR THIS VERSION OF THE CODE:
# - Fixed regex pattern compilation in load_replacement_map to properly escape keys containing regex special characters.
# - Fixed replace_occurrences to normalize input string to NFC before searching and replacing to ensure consistency.
# - Added tracking of all characters used in replacement keys for optimization purposes.
# - Added accessor function get_key_characters() to retrieve the set of characters used in keys.
#
# Copyright (c) 2024 Emasoft
#
# This software is licensed under the MIT License.
# Refer to the LICENSE file for more details.

from __future__ import annotations

import re
import json
from pathlib import Path
import unicodedata
import logging
import sys  # For sys.stdout/stderr in fallback logger

# --- Module-level state ---
_RAW_REPLACEMENT_MAPPING: dict[str, str] = {}  # Stores (normalized stripped key) -> (stripped value) from JSON.
_COMPILED_PATTERN_FOR_SCAN: re.Pattern[str] | None = None  # For initial scan. Now case-sensitive.
_MAPPING_LOADED: bool = False
_SORTED_RAW_KEYS_FOR_REPLACE: list[str] = []  # Normalized stripped keys, sorted by length desc.
_COMPILED_PATTERN_FOR_ACTUAL_REPLACE: re.Pattern[str] | None = None  # For actual replacement. Now case-sensitive.
_MODULE_LOGGER: logging.Logger | logging.LoggerAdapter[logging.Logger] | None = None  # Module-level logger instance
_KEY_CHARACTER_SET: set[str] = set()

# --- START DEBUG CONFIG ---
# Set to True to enable verbose debug prints in this module
_DEBUG_REPLACE_LOGIC = False
# --- END DEBUG CONFIG ---


def reset_module_state() -> None:
    """
    Resets all global module-level variables to their initial states.
    This is crucial for ensuring a clean state when the module's functions
    might be called multiple times within the same process, e.g., in tests
    or sequential script runs.
    """
    global \
        _RAW_REPLACEMENT_MAPPING, \
        _COMPILED_PATTERN_FOR_SCAN, \
        _MAPPING_LOADED, \
        _SORTED_RAW_KEYS_FOR_REPLACE, \
        _COMPILED_PATTERN_FOR_ACTUAL_REPLACE, \
        _MODULE_LOGGER, \
        _KEY_CHARACTER_SET

    _RAW_REPLACEMENT_MAPPING = {}
    _COMPILED_PATTERN_FOR_SCAN = None
    _MAPPING_LOADED = False
    _SORTED_RAW_KEYS_FOR_REPLACE = []
    _COMPILED_PATTERN_FOR_ACTUAL_REPLACE = None
    _MODULE_LOGGER = None  # Reset logger; it will be (re)set by load_replacement_map
    _KEY_CHARACTER_SET.clear()


def _log_message(
    level: int,
    message: str,
    logger: logging.Logger | logging.LoggerAdapter[logging.Logger] | None = None,
) -> None:
    """Helper to log messages using provided logger or print as fallback."""
    effective_logger = logger if logger else _MODULE_LOGGER

    if _DEBUG_REPLACE_LOGIC and level == logging.DEBUG:
        # Print DEBUG messages directly to stderr when _DEBUG_REPLACE_LOGIC is True
        print(f"RL_DBG_STDERR: {message}", file=sys.stderr)
        sys.stderr.flush()
        # Optionally, also log to the intended logger if it's different
        if effective_logger:
            effective_logger.debug(message)
        return

    # For other levels, or if not _DEBUG_REPLACE_LOGIC for DEBUG level
    if effective_logger:
        effective_logger.log(level, message)
    elif level >= logging.INFO:  # Fallback print for INFO and above if no logger
        prefix = ""
        if level == logging.ERROR:
            prefix = "ERROR: "
        elif level == logging.WARNING:
            prefix = "WARNING: "
        elif level == logging.INFO:
            prefix = "INFO: "
        print(
            f"{prefix}{message}",
            file=sys.stderr if level >= logging.WARNING else sys.stdout,
        )
        if level >= logging.WARNING:
            sys.stderr.flush()
        else:
            sys.stdout.flush()


def strip_diacritics(text: str) -> str:
    """Remove diacritical marks from text.

    Args:
        text: Input string

    Returns:
        String with diacritical marks removed
    """
    if not isinstance(text, str):
        return text
    nfd_form = unicodedata.normalize("NFD", text)
    return "".join([c for c in nfd_form if not unicodedata.combining(c)])


def strip_control_characters(text: str) -> str:
    """Remove control characters from text.

    Args:
        text: Input string

    Returns:
        String with control characters removed
    """
    if not isinstance(text, str):
        return text
    return "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")


def load_replacement_map(
    mapping_file_path: Path,
    logger: logging.Logger | logging.LoggerAdapter[logging.Logger] | None = None,
) -> bool:
    """
    Loads and processes the replacement mapping from the given JSON file.
    Assumes that `reset_module_state()` has been called prior to this function
    if a clean state is required.
    """
    global \
        _RAW_REPLACEMENT_MAPPING, \
        _COMPILED_PATTERN_FOR_SCAN, \
        _MAPPING_LOADED, \
        _SORTED_RAW_KEYS_FOR_REPLACE, \
        _COMPILED_PATTERN_FOR_ACTUAL_REPLACE, \
        _MODULE_LOGGER, \
        _KEY_CHARACTER_SET

    _MODULE_LOGGER = logger
    _KEY_CHARACTER_SET.clear()

    try:
        with open(mapping_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        _log_message(
            logging.ERROR,
            f"Replacement mapping file not found: {mapping_file_path}",
            logger,
        )
        return False
    except json.JSONDecodeError as e:
        _log_message(logging.ERROR, f"Invalid JSON in replacement mapping file: {e}", logger)
        return False
    except Exception as e:
        _log_message(
            logging.ERROR,
            f"Could not read replacement mapping file {mapping_file_path}: {e}",
            logger,
        )
        return False

    raw_mapping_from_json = data.get("REPLACEMENT_MAPPING")
    if not isinstance(raw_mapping_from_json, dict):
        _log_message(
            logging.ERROR,
            f"'REPLACEMENT_MAPPING' key not found or not a dictionary in {mapping_file_path}",
            logger,
        )
        return False

    temp_raw_mapping: dict[str, str] = {}
    _log_message(
        logging.DEBUG,
        f"DEBUG MAP LOAD: Loading map from {mapping_file_path.name}",
        logger,
    )

    for k_orig_json, v_original in raw_mapping_from_json.items():
        if not isinstance(k_orig_json, str) or not isinstance(v_original, str):
            _log_message(
                logging.WARNING,
                f"Skipping invalid key-value pair (must be strings): {k_orig_json}:{v_original}",
                logger,
            )
            continue

        temp_stripped_key_no_controls = strip_control_characters(k_orig_json)
        temp_stripped_key_no_diacritics = strip_diacritics(temp_stripped_key_no_controls)
        canonical_key = unicodedata.normalize("NFC", temp_stripped_key_no_diacritics)

        if not canonical_key:
            _log_message(
                logging.WARNING,
                f"Skipping empty key after normalization from original: {k_orig_json!r}",
                logger,
            )
            continue

        if not v_original:
            _log_message(
                logging.WARNING,
                f"Skipping empty value for key: {k_orig_json!r}",
                logger,
            )
            continue

        _log_message(
            logging.DEBUG,
            f"  DEBUG MAP LOAD: JSON Key='{k_orig_json}' (len {len(k_orig_json)}, ords={[ord(c) for c in k_orig_json]})",
            logger,
        )
        _log_message(
            logging.DEBUG,
            f"    -> NoControls='{temp_stripped_key_no_controls}' (len {len(temp_stripped_key_no_controls)}, ords={[ord(c) for c in temp_stripped_key_no_controls]})",
            logger,
        )
        _log_message(
            logging.DEBUG,
            f"    -> NoDiacritics='{temp_stripped_key_no_diacritics}' (len {len(temp_stripped_key_no_diacritics)}, ords={[ord(c) for c in temp_stripped_key_no_diacritics]})",
            logger,
        )
        _log_message(
            logging.DEBUG,
            f"    -> CanonicalKey (NFC)='{canonical_key}' (len {len(canonical_key)}, ords={[ord(c) for c in canonical_key]})",
            logger,
        )
        _log_message(logging.DEBUG, f"    -> Maps to Value: '{v_original}'", logger)

        # Track all characters in keys
        for char in canonical_key:
            _KEY_CHARACTER_SET.add(char)

        temp_raw_mapping[canonical_key] = v_original

    _RAW_REPLACEMENT_MAPPING = temp_raw_mapping
    _log_message(
        logging.DEBUG,
        f"DEBUG MAP LOAD: _RAW_REPLACEMENT_MAPPING populated with {len(_RAW_REPLACEMENT_MAPPING)} entries: {list(_RAW_REPLACEMENT_MAPPING.keys())[:10]}...",
        logger,
    )

    if not _RAW_REPLACEMENT_MAPPING:
        _log_message(
            logging.WARNING,
            "No valid replacement rules found in the mapping file after initial loading/stripping.",
            logger,
        )
        _MAPPING_LOADED = True
        return True

    all_canonical_keys_for_recursion_check = set(_RAW_REPLACEMENT_MAPPING.keys())
    for key_canonical, value_original_from_map in _RAW_REPLACEMENT_MAPPING.items():
        value_stripped_for_check = strip_control_characters(strip_diacritics(value_original_from_map))
        normalized_value_stripped_for_check = unicodedata.normalize("NFC", value_stripped_for_check)
        if normalized_value_stripped_for_check in all_canonical_keys_for_recursion_check:
            original_json_key_for_error_report = key_canonical
            for orig_k_json, orig_v_json in raw_mapping_from_json.items():
                temp_s_k = strip_control_characters(strip_diacritics(orig_k_json))
                norm_s_k = unicodedata.normalize("NFC", temp_s_k)
                if norm_s_k == key_canonical and orig_v_json == value_original_from_map:
                    original_json_key_for_error_report = orig_k_json
                    break
            _log_message(
                logging.ERROR,
                f"Recursive mapping potential! Value '{value_original_from_map}' (for original JSON key '{original_json_key_for_error_report}', its canonical form '{normalized_value_stripped_for_check}' is also a canonical key). This is disallowed. Aborting.",
                logger,
            )
            _RAW_REPLACEMENT_MAPPING = {}
            return False

    # STORE SORTED KEYS (by longest first) for binary scanning and in what order?
    _SORTED_RAW_KEYS_FOR_REPLACE = sorted(_RAW_REPLACEMENT_MAPPING.keys(), key=len, reverse=True)

    # Fix: Properly escape keys for regex pattern compilation to handle special regex characters
    pattern_keys_for_scan_and_replace: list[str] = [re.escape(k) for k in _SORTED_RAW_KEYS_FOR_REPLACE]
    # pattern_keys_for_scan_and_replace.sort(key=len, reverse=True)  -> No need to sort again

    combined_pattern_str = r"(" + r"|".join(pattern_keys_for_scan_and_replace) + r")"

    _log_message(
        logging.DEBUG,
        f"Pattern keys after escaping: {pattern_keys_for_scan_and_replace}",
        logger,
    )

    try:
        _COMPILED_PATTERN_FOR_SCAN = re.compile(combined_pattern_str)
        _COMPILED_PATTERN_FOR_ACTUAL_REPLACE = _COMPILED_PATTERN_FOR_SCAN
    except re.error as e:
        _log_message(
            logging.ERROR,
            f"Could not compile regex pattern: {e}. Regex tried: '{combined_pattern_str}'",
            logger,
        )
        _RAW_REPLACEMENT_MAPPING = {}
        return False

    _MAPPING_LOADED = True
    return True


def get_scan_pattern() -> re.Pattern[str] | None:
    """Get the compiled regex pattern for scanning.

    Returns:
        Compiled regex pattern or None if not loaded
    """
    return _COMPILED_PATTERN_FOR_SCAN if _MAPPING_LOADED else None


def get_raw_stripped_keys() -> list[str]:
    """Get the sorted list of normalized keys.

    Returns:
        List of keys sorted by length (longest first)
    """
    return _SORTED_RAW_KEYS_FOR_REPLACE.copy() if _MAPPING_LOADED else []


def get_key_characters() -> set[str]:
    """
    Returns the set of all characters appearing in replacement keys.

    Returns:
        A copy of the set to prevent external modification
    """
    return _KEY_CHARACTER_SET.copy()


def get_replacement_mapping() -> dict[str, str]:
    """Get the loaded replacement mapping.

    Returns:
        A copy of the replacement mapping dictionary
    """
    return _RAW_REPLACEMENT_MAPPING.copy() if _MAPPING_LOADED else {}


def is_mapping_loaded() -> bool:
    """Check if the replacement mapping has been loaded.

    Returns:
        True if mapping is loaded, False otherwise
    """
    return _MAPPING_LOADED


def get_mapping_size() -> int:
    """Get the number of replacement rules loaded.

    Returns:
        Number of replacement rules
    """
    return len(_RAW_REPLACEMENT_MAPPING) if _MAPPING_LOADED else 0


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

    _log_message(
        logging.DEBUG,
        f"DEBUG_CALLBACK: Matched segment (original from input)='{matched_text_from_input}'",
        _MODULE_LOGGER,
    )
    _log_message(
        logging.DEBUG,
        f"  Canonicalized lookup_key='{lookup_key}' (len {len(lookup_key)}, ords={[ord(c) for c in lookup_key]})",
        _MODULE_LOGGER,
    )
    _log_message(
        logging.DEBUG,
        f"  _RAW_REPLACEMENT_MAPPING at callback (first 5 keys): {list(_RAW_REPLACEMENT_MAPPING.keys())[:5]}...",
        _MODULE_LOGGER,
    )

    replacement_value = _RAW_REPLACEMENT_MAPPING.get(lookup_key)

    if replacement_value is not None:
        _log_message(
            logging.DEBUG,
            f"  Found in map. Replacing with: '{replacement_value}'",
            _MODULE_LOGGER,
        )
        return replacement_value
    warning_msg = (
        f"REPLACE_LOGIC_WARN_CALLBACK_LOOKUP_FAILED: lookup_key '{lookup_key}' (ords={[ord(c) for c in lookup_key]}) "
        f"derived from matched_text_from_input '{matched_text_from_input}' (ords={[ord(c) for c in matched_text_from_input]}) "
        f"NOT FOUND in _RAW_REPLACEMENT_MAPPING (size: {len(_RAW_REPLACEMENT_MAPPING)}). "
        f"Returning original matched text."
    )
    _log_message(logging.WARNING, warning_msg, _MODULE_LOGGER)  # Goes to main logger or print
    _log_message(
        logging.DEBUG,
        f"  Full _RAW_REPLACEMENT_MAPPING keys (first 20): {list(_RAW_REPLACEMENT_MAPPING.keys())[:20]}...",
        _MODULE_LOGGER,
    )  # Goes to stderr if _DEBUG_REPLACE_LOGIC
    return matched_text_from_input


def replace_occurrences(input_string: str) -> str:
    """Replace all occurrences of mapped strings in the input.

    Args:
        input_string: String to process for replacements

    Returns:
        String with all replacements applied
    """
    if _DEBUG_REPLACE_LOGIC:
        entry_debug_msg = (
            f"REPLACE_OCC_ENTRY: input='{input_string[:30] if isinstance(input_string, str) else str(input_string)[:30]}...', "
            f"_MAPPING_LOADED={_MAPPING_LOADED}, "
            f"pattern_is_set={_COMPILED_PATTERN_FOR_ACTUAL_REPLACE is not None}, "
            f"map_is_populated={bool(_RAW_REPLACEMENT_MAPPING)}"
        )
        _log_message(logging.DEBUG, entry_debug_msg, _MODULE_LOGGER)

    # Ensure input is normalized to NFC for consistent matching
    if isinstance(input_string, str):
        normalized_input = unicodedata.normalize("NFC", input_string)
    else:
        normalized_input = input_string

    if (
        not _MAPPING_LOADED
        or not _COMPILED_PATTERN_FOR_ACTUAL_REPLACE
        or not _RAW_REPLACEMENT_MAPPING
        or not isinstance(normalized_input, str)
    ):
        _log_message(
            logging.DEBUG,
            f"DEBUG_REPLACE_OCCURRENCES: Early exit. _MAPPING_LOADED={_MAPPING_LOADED}, "
            f"_COMPILED_PATTERN_FOR_ACTUAL_REPLACE is {'None' if _COMPILED_PATTERN_FOR_ACTUAL_REPLACE is None else 'Set'}, "
            f"_RAW_REPLACEMENT_MAPPING is {'Empty' if not _RAW_REPLACEMENT_MAPPING else 'Populated'}",
            _MODULE_LOGGER,
        )
        return normalized_input if isinstance(normalized_input, str) else input_string

    # Use the normalized version for matching
    search_result = _COMPILED_PATTERN_FOR_ACTUAL_REPLACE.search(normalized_input)
    _log_message(
        logging.DEBUG,
        f"DEBUG_REPLACE_OCCURRENCES: Input (original): {input_string!r}, Search found: {'YES' if search_result else 'NO'}",
        _MODULE_LOGGER,
    )
    if search_result:
        _log_message(
            logging.DEBUG,
            f"DEBUG_REPLACE_OCCURRENCES: Search match object: {search_result}",
            _MODULE_LOGGER,
        )

    # Perform actual replacement using the normalized version
    result = _COMPILED_PATTERN_FOR_ACTUAL_REPLACE.sub(_actual_replace_callback, normalized_input)
    _log_message(
        logging.DEBUG,
        f"DEBUG_REPLACE_OCCURRENCES: Result after replacement: {result!r}",
        _MODULE_LOGGER,
    )
    return result
