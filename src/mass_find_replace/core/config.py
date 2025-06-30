#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial creation of config module for global constants
# - Extracted from mass_find_replace.py
#

"""
Configuration constants for Mass Find Replace.

This module contains global configuration constants used throughout the application.
"""

from typing import Final

__all__ = [
    "SCRIPT_NAME",
    "MAIN_TRANSACTION_FILE_NAME",
    "DEFAULT_REPLACEMENT_MAPPING_FILE",
]

SCRIPT_NAME: Final[str] = "MFR - Mass Find Replace - A script to safely rename things in your project"
MAIN_TRANSACTION_FILE_NAME: Final[str] = "planned_transactions.json"
DEFAULT_REPLACEMENT_MAPPING_FILE: Final[str] = "replacement_mapping.json"
