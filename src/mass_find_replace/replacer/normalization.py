#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of string normalization functions from replace_logic.py
# - This module handles diacritics removal and control character stripping
#

"""
String normalization utilities for the Mass Find Replace replacer.

This module provides functions to normalize strings by removing diacritical marks
and control characters, ensuring consistent matching and replacement.
"""

from __future__ import annotations
import unicodedata

__all__ = [
    "strip_diacritics",
    "strip_control_characters",
]


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
