#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of mapping loading logic from replace_logic.py
# - This module handles loading and processing replacement mappings from JSON files
#

"""
Mapping loader for the Mass Find Replace replacer.

This module handles loading replacement mappings from JSON files and
preparing them for use in the replacement process.
"""

from __future__ import annotations
import json
import logging
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

from .normalization import strip_diacritics, strip_control_characters
from .validation import validate_replacement_mapping_structure
from .patterns import compile_patterns
from .state import (
    set_raw_mapping,
    set_scan_pattern,
    set_replace_pattern,
    set_mapping_loaded,
    set_sorted_keys,
    set_module_logger,
    add_key_characters,
    get_raw_mapping,
)
from .logging_utils import log_message

__all__ = [
    "load_replacement_map",
]


def load_replacement_map(
    mapping_file_path: Path,
    logger: Logger | LoggerAdapter[Logger] | None = None,
) -> bool:
    """
    Loads and processes the replacement mapping from the given JSON file.
    Assumes that `reset_module_state()` has been called prior to this function
    if a clean state is required.
    """
    set_module_logger(logger)

    try:
        with open(mapping_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        log_message(
            logging.ERROR,
            f"Replacement mapping file not found: {mapping_file_path}",
            logger,
        )
        return False
    except json.JSONDecodeError as e:
        log_message(logging.ERROR, f"Invalid JSON in replacement mapping file: {e}", logger)
        return False
    except Exception as e:
        log_message(
            logging.ERROR,
            f"Could not read replacement mapping file {mapping_file_path}: {e}",
            logger,
        )
        return False

    # Validate structure
    is_valid, error_msg = validate_replacement_mapping_structure(data, logger)
    if not is_valid:
        log_message(
            logging.ERROR,
            f"Invalid replacement mapping structure in {mapping_file_path}: {error_msg}",
            logger,
        )
        return False

    raw_mapping_from_json = data.get("REPLACEMENT_MAPPING")

    temp_raw_mapping: dict[str, str] = {}
    log_message(
        logging.DEBUG,
        f"DEBUG MAP LOAD: Loading map from {mapping_file_path.name}",
        logger,
    )

    for k_orig_json, v_original in raw_mapping_from_json.items():
        if not isinstance(k_orig_json, str) or not isinstance(v_original, str):
            log_message(
                logging.WARNING,
                f"Skipping invalid key-value pair (must be strings): key={repr(k_orig_json)} (type={type(k_orig_json).__name__}), value={repr(v_original)} (type={type(v_original).__name__})",
                logger,
            )
            continue

        temp_stripped_key_no_controls = strip_control_characters(k_orig_json)
        temp_stripped_key_no_diacritics = strip_diacritics(temp_stripped_key_no_controls)
        canonical_key = unicodedata.normalize("NFC", temp_stripped_key_no_diacritics)

        if not canonical_key:
            log_message(
                logging.WARNING,
                f"Skipping empty key after normalization from original: {k_orig_json!r}",
                logger,
            )
            continue

        if not v_original:
            log_message(
                logging.WARNING,
                f"Skipping empty value for key: {k_orig_json!r}",
                logger,
            )
            continue

        log_message(
            logging.DEBUG,
            f"  DEBUG MAP LOAD: JSON Key='{k_orig_json}' (len {len(k_orig_json)}, ords={[ord(c) for c in k_orig_json]})",
            logger,
        )
        log_message(
            logging.DEBUG,
            f"    -> NoControls='{temp_stripped_key_no_controls}' (len {len(temp_stripped_key_no_controls)}, ords={[ord(c) for c in temp_stripped_key_no_controls]})",
            logger,
        )
        log_message(
            logging.DEBUG,
            f"    -> NoDiacritics='{temp_stripped_key_no_diacritics}' (len {len(temp_stripped_key_no_diacritics)}, ords={[ord(c) for c in temp_stripped_key_no_diacritics]})",
            logger,
        )
        log_message(
            logging.DEBUG,
            f"    -> CanonicalKey (NFC)='{canonical_key}' (len {len(canonical_key)}, ords={[ord(c) for c in canonical_key]})",
            logger,
        )
        log_message(logging.DEBUG, f"    -> Maps to Value: '{v_original}'", logger)

        # Track all characters in keys
        add_key_characters(canonical_key)

        temp_raw_mapping[canonical_key] = v_original

    set_raw_mapping(temp_raw_mapping)
    log_message(
        logging.DEBUG,
        f"DEBUG MAP LOAD: _RAW_REPLACEMENT_MAPPING populated with {len(temp_raw_mapping)} entries: {list(temp_raw_mapping.keys())[:10]}...",
        logger,
    )

    if not temp_raw_mapping:
        log_message(
            logging.WARNING,
            "No valid replacement rules found in the mapping file after initial loading/stripping.",
            logger,
        )
        set_mapping_loaded(True)
        return True

    # Check for recursive mappings
    all_canonical_keys_for_recursion_check = set(temp_raw_mapping.keys())
    for key_canonical, value_original_from_map in temp_raw_mapping.items():
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
            log_message(
                logging.ERROR,
                f"Recursive mapping potential! Value '{value_original_from_map}' (for original JSON key '{original_json_key_for_error_report}', its canonical form '{normalized_value_stripped_for_check}' is also a canonical key). This is disallowed. Aborting.",
                logger,
            )
            set_raw_mapping({})
            return False

    # STORE SORTED KEYS (by longest first) for binary scanning and in what order?
    sorted_keys = sorted(temp_raw_mapping.keys(), key=len, reverse=True)
    set_sorted_keys(sorted_keys)

    # Compile patterns
    compiled_pattern, error_msg = compile_patterns(sorted_keys, logger)
    if not compiled_pattern:
        log_message(logging.ERROR, error_msg, logger)
        set_raw_mapping({})
        return False

    set_scan_pattern(compiled_pattern)
    set_replace_pattern(compiled_pattern)

    set_mapping_loaded(True)
    return True
