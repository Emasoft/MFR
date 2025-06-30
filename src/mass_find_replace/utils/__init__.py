#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial creation for utils module exports
# - Re-exports utility functions for backward compatibility
#

"""
Utility modules for Mass Find Replace.

This package contains various utility functions that were extracted from
file_system_operations.py.
"""

# Re-export JSON handling
from .json_handlers import (
    SurrogateHandlingEncoder,
    decode_surrogate_escaped_json,
)

# Re-export file locking
from .file_locking import (
    file_lock,
)

# Re-export logging utilities
from .logging_utils import (
    log_fs_op_message,
    log_collision_error,
)

# Re-export file encoding utilities
from .file_encoding import (
    get_file_encoding,
    open_file_with_encoding,
)

__all__ = [
    # JSON handling
    "SurrogateHandlingEncoder",
    "decode_surrogate_escaped_json",
    # File locking
    "file_lock",
    # Logging
    "log_fs_op_message",
    "log_collision_error",
    # File encoding
    "get_file_encoding",
    "open_file_with_encoding",
]
