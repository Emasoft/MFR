#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of JSON handling from file_system_operations.py
# - Includes SurrogateHandlingEncoder and decode function
# - Added comprehensive docstrings
#

"""
JSON encoding and decoding utilities with surrogate character handling.

This module provides custom JSON encoder/decoder that can handle strings
containing surrogate characters by encoding them as base64.
"""

from __future__ import annotations
import json
import base64
from typing import Any
from collections.abc import Iterator


class SurrogateHandlingEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles surrogate characters by encoding to base64.

    When encountering strings that contain surrogate characters (which cannot be
    encoded to UTF-8), this encoder converts them to a special dictionary format
    with base64-encoded data.
    """

    def _encode_with_surrogate_handling(self, text: str) -> str | dict[str, Any]:
        """Single method to handle surrogate encoding.

        Args:
            text: String to encode

        Returns:
            Original string if it can be encoded to UTF-8, otherwise a dict
            with base64-encoded data
        """
        try:
            text.encode("utf-8")
            return text
        except UnicodeEncodeError:
            # Contains surrogates, encode as base64
            return {
                "__surrogate_escaped__": True,
                "data": base64.b64encode(text.encode("utf-8", errors="surrogateescape")).decode("ascii"),
            }

    def encode(self, obj: Any) -> str:
        """Encode object to JSON, handling surrogates in strings.

        Args:
            obj: Object to encode

        Returns:
            JSON string representation
        """
        if isinstance(obj, str):
            processed = self._encode_with_surrogate_handling(obj)
            return super().encode(processed)
        return super().encode(obj)

    def iterencode(self, obj: Any, _one_shot: bool = False) -> Iterator[str]:
        """Encode object to JSON iteratively, handling surrogates in strings.

        Args:
            obj: Object to encode
            _one_shot: Whether to encode in one shot

        Returns:
            Iterator of JSON string chunks
        """
        return super().iterencode(self._process_item(obj), _one_shot)

    def _process_item(self, obj: Any) -> Any:
        """Recursively process an item, encoding strings with surrogates.

        Args:
            obj: Item to process

        Returns:
            Processed item with surrogate strings encoded
        """
        if isinstance(obj, str):
            return self._encode_with_surrogate_handling(obj)
        if isinstance(obj, dict):
            return {k: self._process_item(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._process_item(item) for item in obj]
        if isinstance(obj, tuple):
            return tuple(self._process_item(item) for item in obj)
        return obj


def decode_surrogate_escaped_json(obj: Any) -> Any:
    """Decode JSON objects that were encoded with SurrogateHandlingEncoder.

    This function recursively processes the object, looking for the special
    dictionary format created by SurrogateHandlingEncoder and converting it
    back to the original string with surrogates.

    Args:
        obj: Object to decode (can be dict, list, or any JSON type)

    Returns:
        Decoded object with surrogate strings restored
    """
    if isinstance(obj, dict):
        if obj.get("__surrogate_escaped__") and "data" in obj:
            # Decode base64 back to bytes, then decode with surrogateescape
            encoded_bytes = base64.b64decode(obj["data"])
            return encoded_bytes.decode("utf-8", errors="surrogateescape")
        return {k: decode_surrogate_escaped_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [decode_surrogate_escaped_json(item) for item in obj]
    return obj
