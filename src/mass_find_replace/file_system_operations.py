#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE CODE:
# - Fixed file encoding handling: ensured all file opens use detected encoding with errors='surrogateescape'.
# - Added strict=False to Path.resolve() calls to prevent exceptions and improve sandbox safety.
# - Changed all UUID generation for transactions from uuid1() to uuid4() to avoid leaking MAC/timestamp.
# - Added error handling around os.remove() calls to avoid silent failures.
# - Added safer temp file naming to avoid overwriting existing files.
# - Improved retry logic to respect timeout_minutes parameter instead of hardcoded max passes.
# - Added checks before dictionary accesses to avoid KeyError.
# - Added comments and improved logging for clarity.
# - Minor performance improvements in large file processing.
# - Added SurrogateHandlingEncoder to handle surrogate characters in JSON serialization.
# - Enhanced encoding detection to properly identify UTF-16 files without BOM.
#
# Copyright (c) 2024 Emasoft
#
# This software is licensed under the MIT License.
# Refer to the LICENSE file for more details.

from __future__ import annotations

from pathlib import Path
import pathspec
from isbinary import is_binary_file
import logging


from .core import (
    # Constants
    DEFAULT_ENCODING_FALLBACK,
    TRANSACTION_FILE_BACKUP_EXT,
    BINARY_MATCHES_LOG_FILE,
    COLLISIONS_ERRORS_LOG_FILE,
    LoggerType,
    TransactionType,
    TransactionStatus,
)
from .utils import (
    log_fs_op_message,
    log_collision_error,
    get_file_encoding,
    open_file_with_encoding,
)
from .core.scanning import (
    scan_directory_for_occurrences,
)
from .core.transaction_manager import (
    save_transactions,
    load_transactions,
    update_transaction_status_in_list,
)
from .core.file_processor import (
    process_large_file_content,
    group_and_process_file_transactions,
)
from .core.transaction_orchestrator import (
    execute_all_transactions,
)


# ====================== MAIN FILE SYSTEM OPERATIONS ======================

# Note: The following have been moved to separate modules:
# - JSON encoding/decoding → utils/json_handlers.py
# - File locking → utils/file_locking.py
# - Logging utilities → utils/logging_utils.py
# - File encoding detection → utils/file_encoding.py
# - Constants → core/constants.py
# - Exceptions → core/exceptions.py
# - Types/Enums → core/types.py

# Temporary aliases for backward compatibility
_log_fs_op_message = log_fs_op_message
_log_collision_error = log_collision_error


def load_ignore_patterns(ignore_file_path: Path, logger: LoggerType = None) -> pathspec.PathSpec | None:
    """Load ignore patterns from a gitignore-style file.

    Args:
        ignore_file_path: Path to the ignore file
        logger: Optional logger instance

    Returns:
        PathSpec object or None if file doesn't exist
    """
    if not ignore_file_path.is_file():
        return None
    try:
        with Path(ignore_file_path).open("r", encoding=DEFAULT_ENCODING_FALLBACK, errors="ignore") as f:
            patterns = f.readlines()
        valid_patterns = [p for p in (line.strip() for line in patterns) if p and not p.startswith("#")]
        return pathspec.PathSpec.from_lines("gitwildmatch", valid_patterns) if valid_patterns else None
    except Exception as e:
        _log_fs_op_message(
            logging.WARNING,
            f"Could not load ignore file {ignore_file_path}: {e}",
            logger,
        )
        return None


# Re-export for backward compatibility
__all__ = [
    # Functions
    "scan_directory_for_occurrences",
    "save_transactions",
    "load_transactions",
    "execute_all_transactions",
    "update_transaction_status_in_list",
    "group_and_process_file_transactions",
    "process_large_file_content",
    "load_ignore_patterns",
    # Functions re-exported from utils
    "get_file_encoding",
    "open_file_with_encoding",
    "log_collision_error",
    # External dependencies re-exported
    "is_binary_file",
    # Constants re-exported from core
    "TransactionStatus",
    "TransactionType",
    "TRANSACTION_FILE_BACKUP_EXT",
    "BINARY_MATCHES_LOG_FILE",
    "COLLISIONS_ERRORS_LOG_FILE",
]

# Re-export is_binary_file from isbinary package for backward compatibility
# Note: Already imported at the top of the file
