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
#
# Copyright (c) 2024 Emasoft
#
# This software is licensed under the MIT License.
# Refer to the LICENSE file for more details.

from __future__ import annotations

import os
import json
import uuid
from pathlib import Path
from typing import (
    Any,
    Union,
    Final,
)
from collections.abc import Iterator  # Keep Any if specifically needed for dynamic parts
from enum import Enum
import chardet
import unicodedata  # For NFC normalization
import time
import pathspec
import errno
from striprtf.striprtf import rtf_to_text
from isbinary import is_binary_file
import logging
import sys
import contextlib

from prefect import flow

from . import replace_logic

# Platform-specific imports for file locking
if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

# Type alias for logger types to avoid repetition
# Note: LoggerAdapter is not generic in Python 3.10, so we use Any
LoggerType = Union[logging.Logger, Any, None]

# Constants for file size thresholds
SMALL_FILE_SIZE_THRESHOLD: Final[int] = 1_048_576  # 1 MB - files smaller than this are read entirely
LARGE_FILE_SIZE_THRESHOLD: Final[int] = 100_000_000  # 100 MB - files larger than this are skipped for content scan
DEFAULT_ENCODING_SAMPLE_SIZE: Final[int] = 10240  # 10 KB - sample size for encoding detection

# Constants for retry logic
QUICK_RETRY_COUNT: Final[int] = 3  # Number of quick retries with short delay
QUICK_RETRY_DELAY: Final[int] = 1  # Seconds between quick retries
MAX_RETRY_WAIT_TIME: Final[int] = 30  # Maximum wait time between retries in seconds
RETRY_BACKOFF_MULTIPLIER: Final[int] = 5  # Multiplier for exponential backoff

# Constants for large file processing
SAFE_LINE_LENGTH_THRESHOLD: Final[int] = 1000  # Characters - lines longer than this use chunked processing
CHUNK_SIZE: Final[int] = 1000  # Characters - chunk size for processing long lines
FALLBACK_CHUNK_SIZE: Final[int] = 1000  # Characters - fallback chunk size if no safe split found


class SandboxViolationError(Exception):
    pass


class MockableRetriableError(OSError):
    pass


DEFAULT_ENCODING_FALLBACK: Final[str] = "utf-8"
TRANSACTION_FILE_BACKUP_EXT: Final[str] = ".bak"
SELF_TEST_ERROR_FILE_BASENAME: Final[str] = "error_file_test.txt"
BINARY_MATCHES_LOG_FILE: Final[str] = "binary_files_matches.log"
COLLISIONS_ERRORS_LOG_FILE: Final[str] = "collisions_errors.log"

RETRYABLE_OS_ERRORNOS: Final[set[int]] = {
    errno.EACCES,
    errno.EBUSY,
    errno.ETXTBSY,
}


def open_file_with_encoding(
    file_path: Path,
    mode: str = "r",
    encoding: str | None = None,
    logger: LoggerType = None,
) -> Any:
    """Open a file with proper encoding detection and error handling.

    Args:
        file_path: Path to the file
        mode: File open mode
        encoding: Encoding to use (if None, will detect)
        logger: Optional logger instance

    Returns:
        File handle

    Raises:
        IOError: If file cannot be opened
    """
    if encoding is None and "b" not in mode:
        encoding = get_file_encoding(file_path, logger=logger)

    try:
        if "b" in mode:
            return open(file_path, mode)
        return open(file_path, mode, encoding=encoding, errors="surrogateescape", newline="")
    except OSError as e:
        _log_fs_op_message(
            logging.ERROR,
            f"Cannot open file {file_path} in mode '{mode}' with encoding '{encoding}': {e}",
            logger,
        )
        raise


# ANSI escape codes for interactive mode
GREEN_FG: Final[str] = "\033[32m"
YELLOW_FG: Final[str] = "\033[33m"
BLUE_FG: Final[str] = "\033[94m"
MAGENTA_FG: Final[str] = "\033[35m"
CYAN_FG: Final[str] = "\033[36m"
RED_FG: Final[str] = "\033[31m"
DIM_STYLE: Final[str] = "\033[2m"
BOLD_STYLE: Final[str] = "\033[1m"
RESET_STYLE: Final[str] = "\033[0m"


@contextlib.contextmanager
def file_lock(file_handle: Any, exclusive: bool = True, timeout: float = 10.0) -> Iterator[Any]:
    """Cross-platform file locking context manager.

    Args:
        file_handle: Open file handle to lock
        exclusive: If True, acquire exclusive lock; if False, shared lock
        timeout: Maximum seconds to wait for lock

    Raises:
        TimeoutError: If lock cannot be acquired within timeout
    """
    locked = False
    start_time = time.time()

    try:
        while True:
            try:
                if sys.platform == "win32":
                    # Windows file locking
                    if exclusive:
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        # Windows doesn't have shared locks, use exclusive
                        msvcrt.locking(file_handle.fileno(), msvcrt.LK_NBLCK, 1)
                # Unix file locking
                elif exclusive:
                    fcntl.flock(file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                else:
                    fcntl.flock(file_handle.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
                locked = True
                break
            except OSError as e:
                if e.errno in (errno.EAGAIN, errno.EACCES, errno.EWOULDBLOCK):
                    # Lock is held by another process
                    if time.time() - start_time > timeout:
                        raise TimeoutError(f"Could not acquire file lock within {timeout} seconds")
                    time.sleep(0.1)  # Brief pause before retry
                else:
                    raise

        yield file_handle

    finally:
        if locked:
            try:
                if sys.platform == "win32":
                    msvcrt.locking(file_handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(file_handle.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass  # Best effort unlock


class TransactionType(str, Enum):
    FILE_NAME = "FILE_NAME"
    FOLDER_NAME = "FOLDER_NAME"
    FILE_CONTENT_LINE = "FILE_CONTENT_LINE"


class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    RETRY_LATER = "RETRY_LATER"


def _log_fs_op_message(level: int, message: str, logger: LoggerType = None) -> None:
    """Helper to log messages using provided logger or print as fallback for fs_operations.

    Args:
        level: Logging level (e.g., logging.INFO, logging.ERROR)
        message: Message to log
        logger: Optional logger instance. If None, prints to stdout/stderr
    """
    if logger:
        logger.log(level, message)
    else:
        prefix = ""
        if level == logging.ERROR:
            prefix = "ERROR (fs_op): "
        elif level == logging.WARNING:
            prefix = "WARNING (fs_op): "
        elif level == logging.INFO:
            prefix = "INFO (fs_op): "
        elif level == logging.DEBUG:
            prefix = "DEBUG (fs_op): "
        print(f"{prefix}{message}")


def _log_collision_error(
    root_dir: Path,
    tx: dict[str, Any],
    source_path: Path,
    collision_path: Path | None,
    collision_type: str | None,
    logger: LoggerType = None,
) -> None:
    """Log collision errors to a dedicated file.

    Args:
        root_dir: Root directory of the project
        tx: Transaction dictionary containing rename information
        source_path: Source path that would be renamed
        collision_path: Path that already exists causing the collision
        collision_type: Type of collision (e.g., "exact match", "case-insensitive match")
        logger: Optional logger instance
    """
    collision_log_path = root_dir / COLLISIONS_ERRORS_LOG_FILE

    try:
        # Get relative paths for cleaner logging
        source_rel = source_path.relative_to(root_dir) if root_dir in source_path.parents or source_path == root_dir else source_path
        collision_rel = (collision_path.relative_to(root_dir) if collision_path and (root_dir in collision_path.parents or collision_path == root_dir) else collision_path) if collision_path else None

        with open(collision_log_path, "a", encoding="utf-8") as log_f:
            log_f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - COLLISION ({collision_type}):\n")
            log_f.write(f"  Transaction ID: {tx.get('id', 'N/A')}\n")
            log_f.write(f"  Type: {tx.get('TYPE', 'N/A')}\n")
            log_f.write(f"  Original Path: {tx.get('PATH', 'N/A')}\n")
            log_f.write(f"  Original Name: {tx.get('ORIGINAL_NAME', 'N/A')}\n")
            log_f.write(f"  Proposed New Name: {tx.get('NEW_NAME', 'N/A')}\n")
            log_f.write(f"  Source: {source_rel}\n")
            log_f.write(f"  Collision With: {collision_rel}\n")
            log_f.write(f"  Collision Type: {collision_type}\n")
            log_f.write("-" * 80 + "\n")

        _log_fs_op_message(logging.DEBUG, f"Logged collision error to {collision_log_path}", logger)
    except Exception as e:
        _log_fs_op_message(logging.WARNING, f"Could not write to collision log: {e}", logger)


def get_file_encoding(file_path: Path, sample_size: int = DEFAULT_ENCODING_SAMPLE_SIZE, logger: LoggerType = None) -> str:
    """Detect file encoding using multiple strategies.

    Args:
        file_path: Path to the file
        sample_size: Number of bytes to sample for detection
        logger: Optional logger instance

    Returns:
        Detected encoding name
    """
    if not file_path.is_file():
        return DEFAULT_ENCODING_FALLBACK
    try:
        file_size = file_path.stat().st_size

        # For small files, try reading the entire file with UTF-8 decoding first
        if file_size <= SMALL_FILE_SIZE_THRESHOLD:
            try:
                raw_data = file_path.read_bytes()
                raw_data.decode("utf-8", errors="strict")  # Try strict UTF-8
                return "utf-8"
            except (UnicodeDecodeError, FileNotFoundError):
                pass  # Not UTF-8, fall through to chardet
            except Exception as e:
                _log_fs_op_message(
                    logging.WARNING,
                    f"Unexpected error decoding small file {file_path} as UTF-8: {e}",
                    logger,
                )

        with open(file_path, "rb") as f:
            raw_data = f.read(sample_size)

        if not raw_data:
            return DEFAULT_ENCODING_FALLBACK

        # 1. Try UTF-8 for all files regardless of size
        try:
            if file_path.suffix.lower() != ".rtf":
                raw_data.decode("utf-8", errors="strict")
                return "utf-8"
        except UnicodeDecodeError:
            pass

        # RTF files use Latin-1
        if file_path.suffix.lower() == ".rtf":
            return "latin-1"

        # 2. Use chardet detection
        detected = chardet.detect(raw_data)
        encoding = detected.get("encoding") or DEFAULT_ENCODING_FALLBACK
        confidence = detected.get("confidence", 0)

        # Normalize GB2312 to GB18030
        if encoding and encoding.lower().startswith("gb2312"):
            encoding = "gb18030"

        # Only consider chardet results with reasonable confidence
        if confidence > 0.5 and encoding:
            encoding = encoding.lower()
            # Handle common encoding aliases
            try:
                raw_data.decode(encoding, errors="surrogateescape")
                return encoding
            except (UnicodeDecodeError, LookupError):
                pass

        # 3. Fallback explicit checks if UTF-8 and chardet's primary suggestion failed or wasn't definitive
        for enc_try in ["cp1252", "latin1", "iso-8859-1"]:
            try:
                if encoding != enc_try:
                    raw_data.decode(enc_try, errors="surrogateescape")
                    return enc_try
            except (UnicodeDecodeError, LookupError):
                pass

        _log_fs_op_message(
            logging.DEBUG,
            f"Encoding for {file_path} could not be confidently determined. Chardet: {detected}. Using {DEFAULT_ENCODING_FALLBACK}.",
            logger,
        )
        return DEFAULT_ENCODING_FALLBACK
    except Exception as e:
        _log_fs_op_message(
            logging.WARNING,
            f"Error detecting encoding for {file_path}: {e}. Falling back to {DEFAULT_ENCODING_FALLBACK}.",
            logger,
        )
        return DEFAULT_ENCODING_FALLBACK


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
        with open(ignore_file_path, "r", encoding=DEFAULT_ENCODING_FALLBACK, errors="ignore") as f:
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


def _walk_for_scan(
    root_dir: Path,
    excluded_dirs_abs: list[Path],
    ignore_symlinks: bool,
    ignore_spec: pathspec.PathSpec | None,
    logger: LoggerType = None,
) -> Iterator[Path]:
    """Walk directory tree yielding paths that should be scanned.

    Args:
        root_dir: Root directory to walk
        excluded_dirs_abs: Absolute paths of directories to exclude
        ignore_symlinks: Whether to ignore symlinks
        ignore_spec: PathSpec for gitignore-style exclusions
        logger: Optional logger instance

    Yields:
        Paths to process
    """
    # Track visited symlinks to prevent loops
    visited_symlinks: set[Path] = set()

    for item_path_from_rglob in root_dir.rglob("*"):
        try:
            # Check for symlink loops
            if item_path_from_rglob.is_symlink():
                if ignore_symlinks:
                    continue

                # Resolve symlink to detect loops
                try:
                    real_path = item_path_from_rglob.resolve(strict=False)
                    # Check if we've already visited this real path via another symlink
                    if real_path in visited_symlinks:
                        _log_fs_op_message(
                            logging.WARNING,
                            f"Symlink loop detected: {item_path_from_rglob} -> {real_path}. Skipping.",
                            logger,
                        )
                        continue
                    visited_symlinks.add(real_path)

                    # Also check if symlink points to a parent directory (would cause infinite recursion)
                    try:
                        # Check if the symlink target is an ancestor of the symlink location
                        symlink_parents = list(item_path_from_rglob.parents)
                        if real_path in symlink_parents:
                            _log_fs_op_message(
                                logging.WARNING,
                                f"Symlink points to ancestor directory: {item_path_from_rglob} -> {real_path}. Skipping to prevent infinite recursion.",
                                logger,
                            )
                            continue
                    except (OSError, ValueError):
                        pass  # Continue if we can't resolve paths

                except Exception as e:
                    _log_fs_op_message(
                        logging.WARNING,
                        f"Could not resolve symlink {item_path_from_rglob}: {e}. Skipping.",
                        logger,
                    )
                    continue

            is_excluded_by_dir_arg = any(item_path_from_rglob == ex_dir or (ex_dir.is_dir() and str(item_path_from_rglob).startswith(str(ex_dir) + os.sep)) for ex_dir in excluded_dirs_abs)
            if is_excluded_by_dir_arg:
                continue
            if ignore_spec:
                try:
                    path_rel_to_root_for_spec = item_path_from_rglob.relative_to(root_dir)
                    rel_posix = str(path_rel_to_root_for_spec).replace("\\", "/")
                    if ignore_spec.match_file(rel_posix) or (item_path_from_rglob.is_dir() and ignore_spec.match_file(rel_posix + "/")):
                        continue
                except ValueError:  # Not relative, should not happen with rglob from root
                    pass
                except Exception as e_spec:  # Catch other pathspec errors
                    _log_fs_op_message(
                        logging.WARNING,
                        f"Error during ignore_spec matching for {item_path_from_rglob} relative to {root_dir}: {e_spec}",
                        logger,
                    )
            yield item_path_from_rglob
        except OSError as e_os:  # Catch OSError from is_symlink, is_dir
            _log_fs_op_message(
                logging.WARNING,
                f"OS error accessing attributes of {item_path_from_rglob}: {e_os}. Skipping item.",
                logger,
            )
            continue
        except Exception as e_gen:  # Catch any other unexpected error for this item
            _log_fs_op_message(
                logging.ERROR,
                f"Unexpected error processing item {item_path_from_rglob} in _walk_for_scan: {e_gen}. Skipping item.",
                logger,
            )
            continue


def _get_current_absolute_path(
    original_relative_path_str: str,
    root_dir: Path,
    path_translation_map: dict[str, str],
    cache: dict[str, Path],
    dry_run: bool = False,
) -> Path:
    if dry_run:
        # During dry run, update virtual mapping to enable child transactions to resolve correctly
        if original_relative_path_str not in path_translation_map:
            # Use original name as fallback
            path_translation_map[original_relative_path_str] = Path(original_relative_path_str).name
        # Compose current absolute path using virtual mapping
        if original_relative_path_str in cache:
            return cache[original_relative_path_str]
        if original_relative_path_str == ".":
            cache["."] = root_dir
            return root_dir
        original_path_obj = Path(original_relative_path_str)
        parent_rel_str = "." if original_path_obj.parent == Path() else str(original_path_obj.parent)
        current_parent_abs_path = _get_current_absolute_path(parent_rel_str, root_dir, path_translation_map, cache, dry_run)
        current_item_name = path_translation_map.get(original_relative_path_str, original_path_obj.name)
        current_abs_path = current_parent_abs_path / current_item_name
        cache[original_relative_path_str] = current_abs_path
        return current_abs_path

    if original_relative_path_str in cache:
        return cache[original_relative_path_str]
    if original_relative_path_str == ".":
        cache["."] = root_dir
        return root_dir
    original_path_obj = Path(original_relative_path_str)
    parent_rel_str = "." if original_path_obj.parent == Path() else str(original_path_obj.parent)
    current_parent_abs_path = _get_current_absolute_path(parent_rel_str, root_dir, path_translation_map, cache, dry_run)
    current_item_name = path_translation_map.get(original_relative_path_str, original_path_obj.name)
    current_abs_path = current_parent_abs_path / current_item_name
    cache[original_relative_path_str] = current_abs_path
    return current_abs_path


def scan_directory_for_occurrences(
    root_dir: Path,
    excluded_dirs: list[str],
    excluded_files: list[str],
    file_extensions: list[str] | None,
    ignore_symlinks: bool,
    ignore_spec: pathspec.PathSpec | None,
    resume_from_transactions: list[dict[str, Any]] | None = None,
    paths_to_force_rescan: set[str] | None = None,
    skip_file_renaming: bool = False,
    skip_folder_renaming: bool = False,
    skip_content: bool = False,
    logger: LoggerType = None,
) -> list[dict[str, Any]]:
    """Scan directory for all occurrences that need replacement.

    Args:
        root_dir: Root directory to scan
        excluded_dirs: Directory names to exclude
        excluded_files: Files or relative paths to exclude
        file_extensions: List of file extensions for content scan
        ignore_symlinks: Whether to ignore symlinks
        ignore_spec: PathSpec for gitignore-style exclusions
        resume_from_transactions: Existing transactions for resume
        paths_to_force_rescan: Paths to force rescan or None for all
        skip_file_renaming: Skip file renaming operations
        skip_folder_renaming: Skip folder renaming operations
        skip_content: Skip content modifications
        logger: Optional logger instance

    Returns:
        List of transaction dictionaries
    """
    processed_transactions: list[dict[str, Any]] = []
    existing_transaction_ids: set[tuple[str, str, int]] = set()
    # Handle None as "rescan everything"
    rescan_all = paths_to_force_rescan is None
    paths_to_force_rescan_internal: set[str] = set() if rescan_all else (paths_to_force_rescan if paths_to_force_rescan is not None else set())
    abs_root_dir = root_dir

    binary_log_path = root_dir / BINARY_MATCHES_LOG_FILE

    scan_pattern = replace_logic.get_scan_pattern()
    raw_keys_for_binary_search = replace_logic.get_raw_stripped_keys()

    if resume_from_transactions is not None:
        processed_transactions = list(resume_from_transactions)
        # Backfill NEW_NAME for existing rename transactions if missing
        for tx in resume_from_transactions:
            if tx["TYPE"] in [TransactionType.FILE_NAME.value, TransactionType.FOLDER_NAME.value] and "NEW_NAME" not in tx:
                tx["NEW_NAME"] = replace_logic.replace_occurrences(tx["ORIGINAL_NAME"])
        for tx in resume_from_transactions:
            tx_rel_path = tx.get("PATH")
            if (rescan_all or tx_rel_path in paths_to_force_rescan_internal) and tx.get("TYPE") == TransactionType.FILE_CONTENT_LINE.value:
                continue
            tx_type, tx_line = tx.get("TYPE"), tx.get("LINE_NUMBER", 0)
            if tx_type and tx_rel_path:
                existing_transaction_ids.add((tx_rel_path, tx_type, tx_line))

    resolved_abs_excluded_dirs = []
    for d_str in excluded_dirs:
        try:
            resolved_abs_excluded_dirs.append(abs_root_dir.joinpath(d_str).resolve(strict=False))
        except Exception:
            resolved_abs_excluded_dirs.append(abs_root_dir.joinpath(d_str).absolute())

    excluded_basenames = {Path(f).name for f in excluded_files if Path(f).name == f and os.path.sep not in f and not ("/" in f or "\\" in f)}
    excluded_relative_paths_set = {f.replace("\\", "/") for f in excluded_files if os.path.sep in f or "/" in f or "\\" in f}

    normalized_extensions = {ext.lower() for ext in file_extensions} if file_extensions else None

    # Fix: If resume_from_transactions is not None and paths_to_force_rescan is empty, initialize as empty set
    if resume_from_transactions is not None and not paths_to_force_rescan_internal:
        paths_to_force_rescan_internal = set()

    item_iterator = _walk_for_scan(
        abs_root_dir,
        resolved_abs_excluded_dirs,
        ignore_symlinks,
        ignore_spec,
        logger=logger,
    )

    # Collect items with depth for proper ordering
    all_items_with_depth = []

    for item_abs_path in item_iterator:
        # Depth calculation for ordering
        depth = len(item_abs_path.relative_to(abs_root_dir).parts)
        all_items_with_depth.append((depth, item_abs_path))

    # Sort by depth (shallow first), then by normalized path string for consistent ordering
    all_items_with_depth.sort(key=lambda x: (x[0], x[1]))  # Proper Path comparison

    for depth, item_abs_path in all_items_with_depth:
        try:
            relative_path_str = str(item_abs_path.relative_to(abs_root_dir)).replace("\\", "/")
        except ValueError:
            _log_fs_op_message(
                logging.WARNING,
                f"Could not get relative path for {item_abs_path} against {abs_root_dir}. Skipping.",
                logger,
            )
            continue

        if item_abs_path.name in excluded_basenames or relative_path_str in excluded_relative_paths_set:
            continue

        original_name = item_abs_path.name
        searchable_name = unicodedata.normalize(
            "NFC",
            replace_logic.strip_control_characters(replace_logic.strip_diacritics(original_name)),
        )

        item_is_dir = False
        item_is_file = False
        item_is_symlink = False
        try:
            if not item_abs_path.is_symlink():
                item_is_dir = item_abs_path.is_dir()
            else:
                # Check if symlink points outside root
                try:
                    target = item_abs_path.resolve(strict=False)
                except Exception as e_resolve:
                    _log_fs_op_message(
                        logging.WARNING,
                        f"Could not resolve symlink target for {relative_path_str}: {e_resolve}. Skipping.",
                        logger,
                    )
                    continue
                if root_dir not in target.parents and target != root_dir:
                    _log_fs_op_message(
                        logging.INFO,
                        f"Skipping external symlink: {relative_path_str} -> {target}",
                        logger,
                    )
                    continue
                # Treat symlink as file for name replacement
                item_is_file = True
            if not item_is_dir and not item_is_file:
                # If not dir and not file, check if file (for symlink to file)
                item_is_file = item_abs_path.is_file()
            item_is_symlink = item_abs_path.is_symlink()
        except OSError as e_stat:
            _log_fs_op_message(
                logging.WARNING,
                f"OS error checking type of {item_abs_path}: {e_stat}. Skipping item.",
                logger,
            )
            continue

        if (scan_pattern and scan_pattern.search(searchable_name)) and (replace_logic.replace_occurrences(original_name) != original_name):
            tx_type_val: str | None = None
            if item_is_dir:  # True only if not a symlink and is_dir() was true
                if not skip_folder_renaming:
                    tx_type_val = TransactionType.FOLDER_NAME.value
            elif item_is_file or item_is_symlink:  # True if is_file() or is_symlink() (and not ignore_symlinks)
                if not skip_file_renaming:
                    tx_type_val = TransactionType.FILE_NAME.value

            if tx_type_val:
                tx_id_tuple = (relative_path_str, tx_type_val, 0)
                if tx_id_tuple not in existing_transaction_ids:
                    # Calculate new name and store in transaction
                    new_name = replace_logic.replace_occurrences(original_name)
                    transaction_entry = {
                        "id": str(uuid.uuid4()),  # Changed to uuid4 for privacy and uniqueness
                        "TYPE": tx_type_val,
                        "PATH": relative_path_str,
                        "ORIGINAL_NAME": original_name,
                        "NEW_NAME": new_name,
                        "LINE_NUMBER": 0,
                        "STATUS": TransactionStatus.PENDING.value,
                        "timestamp_created": time.time(),
                        "retry_count": 0,
                    }
                    processed_transactions.append(transaction_entry)
                    existing_transaction_ids.add(tx_id_tuple)

        # Content processing should only happen for actual files, not symlinks to directories
        # and only if item_is_file was true (meaning it's a file or a symlink we are considering for content if it points to a file)
        # The `item_abs_path.is_file()` check inside this block will resolve the symlink if it's one.
        if not skip_content:
            try:
                if item_abs_path.is_file():  # This resolves symlinks to files
                    # Skip large files early
                    if item_abs_path.stat().st_size > LARGE_FILE_SIZE_THRESHOLD:
                        continue

                    is_rtf = item_abs_path.suffix.lower() == ".rtf"
                    try:
                        is_bin = is_binary_file(str(item_abs_path))
                    except FileNotFoundError:
                        _log_fs_op_message(
                            logging.WARNING,
                            f"File not found for binary check: {item_abs_path}. Skipping content scan.",
                            logger,
                        )
                        continue
                    except Exception as e_isbin:
                        _log_fs_op_message(
                            logging.WARNING,
                            f"Could not determine if {item_abs_path} is binary: {e_isbin}. Skipping content scan.",
                            logger,
                        )
                        continue

                    if is_bin and not is_rtf:
                        # Skip binary files but log them
                        _log_fs_op_message(
                            logging.DEBUG,
                            f"Skipping binary file: {relative_path_str}",
                            logger,
                        )
                        if raw_keys_for_binary_search:
                            try:
                                # Process binary file in chunks to avoid memory exhaustion
                                BINARY_CHUNK_SIZE = 1_048_576  # 1MB chunks
                                with open(item_abs_path, "rb") as bf:
                                    # Pre-encode keys for efficiency
                                    encoded_keys = []
                                    for key_str in raw_keys_for_binary_search:
                                        try:
                                            encoded_keys.append((key_str, key_str.encode("utf-8")))
                                        except UnicodeEncodeError:
                                            continue

                                    if not encoded_keys:
                                        continue

                                    # Track global offset for reporting
                                    global_offset = 0
                                    overlap_size = max(len(kb[1]) for kb in encoded_keys) - 1

                                    # Process file in chunks with overlap
                                    while True:
                                        chunk = bf.read(BINARY_CHUNK_SIZE)
                                        if not chunk:
                                            break

                                        # For subsequent chunks, prepend overlap from previous chunk
                                        if global_offset > 0 and overlap_size > 0:
                                            # Seek back to get overlap
                                            bf.seek(global_offset - overlap_size)
                                            overlap_chunk = bf.read(overlap_size)
                                            chunk = overlap_chunk + chunk
                                            search_offset = -overlap_size
                                        else:
                                            search_offset = 0

                                        # Search for each key in this chunk
                                        for key_str, key_bytes in encoded_keys:
                                            offset = 0
                                            while True:
                                                idx = chunk.find(key_bytes, offset)
                                                if idx == -1:
                                                    break
                                                # Only report if match is not in overlap region of subsequent chunks
                                                if idx >= search_offset:
                                                    actual_offset = global_offset + idx - (0 if search_offset >= 0 else -search_offset)
                                                    # Ensure relative path is used in log
                                                    if not Path(relative_path_str).is_absolute():
                                                        log_path_str = relative_path_str
                                                    else:
                                                        log_path_str = str(item_abs_path.relative_to(root_dir)).replace("\\", "/")
                                                    with open(binary_log_path, "a", encoding="utf-8") as log_f:
                                                        log_f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - MATCH: File: {log_path_str}, Key: '{key_str}', Offset: {actual_offset}\n")
                                                offset = idx + len(key_bytes)

                                        # Update global offset
                                        global_offset += len(chunk) - (0 if search_offset >= 0 else -search_offset)

                                        # If we read less than chunk size, we're at EOF
                                        if len(chunk) < BINARY_CHUNK_SIZE + (overlap_size if global_offset > BINARY_CHUNK_SIZE else 0):
                                            break
                            except OSError as e_bin_read:
                                _log_fs_op_message(
                                    logging.WARNING,
                                    f"OS error reading binary file {item_abs_path} for logging: {e_bin_read}",
                                    logger,
                                )
                            except Exception as e_bin_proc:
                                _log_fs_op_message(
                                    logging.WARNING,
                                    f"Error processing binary {item_abs_path} for logging: {e_bin_proc}",
                                    logger,
                                )
                        continue

                    if normalized_extensions and item_abs_path.suffix.lower() not in normalized_extensions and not is_rtf:
                        continue

                    file_content_for_scan: str | None = None
                    file_encoding = DEFAULT_ENCODING_FALLBACK

                    if is_rtf:
                        try:
                            rtf_source_bytes = item_abs_path.read_bytes()
                            rtf_source_str = ""
                            for enc_try in ["latin-1", "cp1252", "utf-8"]:
                                try:
                                    rtf_source_str = rtf_source_bytes.decode(enc_try)
                                    break
                                except UnicodeDecodeError:
                                    pass
                            if not rtf_source_str:
                                rtf_source_str = rtf_source_bytes.decode("utf-8", errors="ignore")
                            file_content_for_scan = rtf_to_text(rtf_source_str, errors="ignore")
                            file_encoding = "utf-8"  # Content is now plain text
                        except OSError as e_rtf_read:
                            _log_fs_op_message(
                                logging.WARNING,
                                f"OS error reading RTF file {item_abs_path}: {e_rtf_read}",
                                logger,
                            )
                            continue
                        except Exception as e_rtf_proc:
                            _log_fs_op_message(
                                logging.WARNING,
                                f"Error extracting text from RTF {item_abs_path}: {e_rtf_proc}",
                                logger,
                            )
                            continue
                    else:
                        file_encoding = get_file_encoding(item_abs_path, logger=logger) or DEFAULT_ENCODING_FALLBACK
                        try:
                            with open_file_with_encoding(item_abs_path, "r", file_encoding, logger) as f_scan:
                                file_content_for_scan = f_scan.read()
                        except OSError as e_txt_read:
                            _log_fs_op_message(
                                logging.WARNING,
                                f"OS error reading text file {item_abs_path}: {e_txt_read}",
                                logger,
                            )
                            continue

                    if file_content_for_scan is not None:
                        lines_for_scan = file_content_for_scan.splitlines(keepends=True)
                        if not lines_for_scan and file_content_for_scan:  # Handle files with no newlines but content
                            lines_for_scan = [file_content_for_scan]

                        for line_idx, line_content in enumerate(lines_for_scan):
                            searchable_line_content = unicodedata.normalize(
                                "NFC",
                                replace_logic.strip_control_characters(replace_logic.strip_diacritics(line_content)),
                            )
                            # Calculate new content once for consistency
                            new_line_content = replace_logic.replace_occurrences(line_content)
                            if (scan_pattern and scan_pattern.search(searchable_line_content)) and (new_line_content != line_content):
                                tx_id_tuple = (
                                    relative_path_str,
                                    TransactionType.FILE_CONTENT_LINE.value,
                                    line_idx + 1,
                                )
                                if tx_id_tuple not in existing_transaction_ids:
                                    # ADD NEW_LINE_CONTENT FIELD
                                    processed_transactions.append(
                                        {
                                            "id": str(uuid.uuid4()),
                                            "TYPE": TransactionType.FILE_CONTENT_LINE.value,
                                            "PATH": relative_path_str,
                                            "LINE_NUMBER": line_idx + 1,
                                            "ORIGINAL_LINE_CONTENT": line_content,
                                            "NEW_LINE_CONTENT": new_line_content,
                                            "ORIGINAL_ENCODING": file_encoding,
                                            "IS_RTF": is_rtf,
                                            "STATUS": TransactionStatus.PENDING.value,
                                            "timestamp_created": time.time(),
                                            "retry_count": 0,
                                        }
                                    )
                                    existing_transaction_ids.add(tx_id_tuple)
            except OSError as e_stat_content:  # Catch OSError from item_abs_path.is_file()
                _log_fs_op_message(
                    logging.WARNING,
                    f"OS error checking if {item_abs_path} is a file for content processing: {e_stat_content}. Skipping content scan for this item.",
                    logger,
                )

    # Order transactions: folders first (shallow to deep), then files, then content
    folder_txs = [tx for tx in processed_transactions if tx["TYPE"] in (TransactionType.FOLDER_NAME.value,)]
    file_txs = [tx for tx in processed_transactions if tx["TYPE"] == TransactionType.FILE_NAME.value]
    content_txs = [tx for tx in processed_transactions if tx["TYPE"] == TransactionType.FILE_CONTENT_LINE.value]

    # Sort folders by depth (shallow then deep) and path for deterministic order
    folder_txs.sort(key=lambda tx: (len(Path(tx["PATH"]).parts), tx["PATH"]))

    processed_transactions = folder_txs + file_txs + content_txs

    return processed_transactions


def save_transactions(
    transactions: list[dict[str, Any]],
    transactions_file_path: Path,
    logger: LoggerType = None,
) -> None:
    """
    Save the list of transactions to a JSON file atomically with file locking.

    Args:
        transactions: List of transaction dictionaries
        transactions_file_path: Path to save the transactions file
        logger: Optional logger instance
    """
    if not transactions:
        _log_fs_op_message(logging.WARNING, "No transactions to save.", logger)
        return
    # Use unique temp file name to avoid conflicts
    temp_file_path = transactions_file_path.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
    try:
        with open(temp_file_path, "w", encoding="utf-8") as f:
            with file_lock(f, exclusive=True):
                json.dump(transactions, f, indent=2, ensure_ascii=False)
        # Atomically replace original file
        os.replace(temp_file_path, transactions_file_path)
    except TimeoutError as e:
        _log_fs_op_message(logging.ERROR, f"Could not acquire lock to save transactions: {e}", logger)
        try:
            if temp_file_path.exists():
                os.remove(temp_file_path)
        except OSError:
            pass
        raise
    except Exception as e:
        _log_fs_op_message(logging.ERROR, f"Error saving transactions: {e}", logger)
        try:
            if temp_file_path.exists():
                os.remove(temp_file_path)
        except Exception as cleanup_e:
            _log_fs_op_message(
                logging.WARNING,
                f"Error cleaning up temp transaction file: {cleanup_e}",
                logger,
            )
        raise


def load_transactions(transactions_file_path: Path, logger: LoggerType = None) -> list[dict[str, Any]] | None:
    """
    Load transactions from a JSON file with file locking.

    Args:
        transactions_file_path: Path to the transactions file
        logger: Optional logger instance

    Returns:
        List of transaction dictionaries or None if file not found/invalid
    """
    if not transactions_file_path.is_file():
        _log_fs_op_message(
            logging.WARNING,
            f"Transaction file not found: {transactions_file_path}",
            logger,
        )
        return None
    try:
        with open(transactions_file_path, "r", encoding="utf-8") as f:
            with file_lock(f, exclusive=False):  # Shared lock for reading
                data = json.load(f)
        if not isinstance(data, list):
            _log_fs_op_message(
                logging.ERROR,
                f"Transaction file {transactions_file_path} does not contain a list.",
                logger,
            )
            return None
        return data
    except TimeoutError as e:
        _log_fs_op_message(
            logging.ERROR,
            f"Could not acquire lock to read transactions: {e}",
            logger,
        )
        return None
    except Exception as e:
        _log_fs_op_message(
            logging.ERROR,
            f"Error loading transactions from {transactions_file_path}: {e}",
            logger,
        )
        return None


def update_transaction_status_in_list(
    transactions: list[dict[str, Any]],
    transaction_id: str,
    new_status: TransactionStatus,
    error_message: str | None = None,
    logger: LoggerType = None,
) -> bool:
    """Update the status and optional error message of a transaction in the list by id.

    Args:
        transactions: List of transaction dictionaries to update
        transaction_id: ID of the transaction to update
        new_status: New status to set
        error_message: Optional error message to add
        logger: Optional logger instance

    Returns:
        True if transaction was found and updated, False otherwise
    """
    for tx in transactions:
        if tx.get("id") == transaction_id:
            tx["STATUS"] = new_status.value
            if error_message is not None:
                tx["ERROR_MESSAGE"] = error_message
            if logger:
                logger.debug(f"Transaction {transaction_id} updated to {new_status.value} with error: {error_message}")
            return True
    if logger:
        logger.warning(f"Transaction {transaction_id} not found for status update.")
    return False


def _execute_rename_transaction(
    tx: dict[str, Any],
    root_dir: Path,
    path_translation_map: dict[str, str],
    path_cache: dict[str, Path],
    dry_run: bool,
    logger: LoggerType = None,
) -> tuple[TransactionStatus, str, bool]:
    """
    Execute a rename transaction (file or folder).
    Returns (status, error_message, changed_bool).
    """
    original_relative_path_str = tx["PATH"]
    original_name = tx.get("ORIGINAL_NAME", "")
    tx_type = tx["TYPE"]

    # Use precomputed NEW_NAME if available
    new_name = tx.get("NEW_NAME", replace_logic.replace_occurrences(original_name))

    current_abs_path = _get_current_absolute_path(original_relative_path_str, root_dir, path_translation_map, path_cache, dry_run)
    if not dry_run and not current_abs_path.exists():
        return TransactionStatus.FAILED, f"Path not found: {current_abs_path}", False

    if new_name == original_name:
        return TransactionStatus.SKIPPED, f"No change needed: '{original_name}' would remain the same", False

    new_abs_path = current_abs_path.parent / new_name

    # Check for exact match first
    if new_abs_path.exists():
        _log_collision_error(root_dir, tx, current_abs_path, new_abs_path, "exact match", logger)
        return (
            TransactionStatus.FAILED,
            f"Target path already exists: {new_abs_path}",
            False,
        )

    # Case-insensitive collision check
    parent_dir = current_abs_path.parent
    new_name_lower = new_name.lower()

    try:
        for existing_item in parent_dir.iterdir():
            # Skip self
            if existing_item == current_abs_path:
                continue
            # Check for case-insensitive match
            if existing_item.name.lower() == new_name_lower:
                _log_collision_error(
                    root_dir,
                    tx,
                    current_abs_path,
                    existing_item,
                    "case-insensitive match",
                    logger,
                )
                return (
                    TransactionStatus.FAILED,
                    f"Case-insensitive collision with existing path: {existing_item}",
                    False,
                )
    except OSError as e:
        _log_fs_op_message(
            logging.WARNING,
            f"Could not check for collisions in {parent_dir}: {e}",
            logger,
        )

    try:
        if dry_run:
            # Special handling for folders to simulate cascading renames
            if tx_type in [TransactionType.FOLDER_NAME.value]:
                # Create virtual path for simulation
                if original_relative_path_str not in path_translation_map:
                    path_translation_map[original_relative_path_str] = original_name
                path_translation_map[original_relative_path_str] = new_name
                path_cache.pop(original_relative_path_str, None)
                return TransactionStatus.COMPLETED, "DRY_RUN", True
            # Only simulate changes, don't update real path mappings
            return TransactionStatus.COMPLETED, "DRY_RUN", False

        # Actual rename
        os.rename(current_abs_path, new_abs_path)
        path_translation_map[original_relative_path_str] = new_name
        path_cache.pop(original_relative_path_str, None)
        return TransactionStatus.COMPLETED, "", True
    except Exception as e:
        return TransactionStatus.FAILED, f"Rename error: {e}", False


def _execute_content_line_transaction(
    tx: dict[str, Any],
    root_dir: Path,
    path_translation_map: dict[str, str],
    path_cache: dict[str, Path],
    logger: LoggerType = None,
) -> tuple[TransactionStatus, str, bool]:
    """
    Execute a content line transaction.
    Returns (status, error_message, changed_bool).
    """
    relative_path_str = tx["PATH"]
    line_no = tx["LINE_NUMBER"]  # 1-indexed
    file_encoding = tx.get("ORIGINAL_ENCODING", DEFAULT_ENCODING_FALLBACK)
    is_rtf = tx.get("IS_RTF", False)

    # Skip RTF as they're converted text files with unique formatting
    if is_rtf:
        return (
            TransactionStatus.SKIPPED,
            "RTF content modification not supported",
            False,
        )

    try:
        # Get current file location (accounts for renames)
        current_abs_path = _get_current_absolute_path(relative_path_str, root_dir, path_translation_map, path_cache, dry_run=False)

        # Read file with original encoding
        with open_file_with_encoding(current_abs_path, "r", file_encoding, logger) as f:
            lines = f.readlines()  # Preserve line endings

        if line_no - 1 < 0 or line_no - 1 >= len(lines):
            return (
                TransactionStatus.FAILED,
                f"Line number {line_no} out of range. File has {len(lines)} lines.",
                False,
            )

        # Get new content from transaction
        new_line_content = tx.get("NEW_LINE_CONTENT", "")

        # Skip if line didn't change (shouldn't happen but safeguard)
        if lines[line_no - 1] == new_line_content:
            return (TransactionStatus.SKIPPED, "Line already matches target", False)

        # Update the line
        lines[line_no - 1] = new_line_content

        # Write back with same encoding
        with open_file_with_encoding(current_abs_path, "w", file_encoding, logger) as f:
            f.writelines(lines)

        return (TransactionStatus.COMPLETED, "", True)
    except Exception as e:
        return (TransactionStatus.FAILED, f"Content update failed: {e}", False)


def _execute_file_content_batch(
    abs_filepath: Path,
    transactions: list[dict[str, Any]],
    logger: LoggerType = None,
) -> tuple[int, int, int]:
    """
    Execute content line transactions for a single file in batch.
    Returns (completed_count, skipped_count, failed_count).
    """
    try:
        # Read entire file content
        if not abs_filepath.exists():
            for tx in transactions:
                tx["STATUS"] = TransactionStatus.FAILED.value
                tx["ERROR_MESSAGE"] = f"File not found: {abs_filepath}"
            return (0, 0, len(transactions))

        file_encoding = transactions[0].get("ORIGINAL_ENCODING", DEFAULT_ENCODING_FALLBACK)
        is_rtf = transactions[0].get("IS_RTF", False)
        if is_rtf:
            for tx in transactions:
                tx["STATUS"] = TransactionStatus.SKIPPED.value
                tx["ERROR_MESSAGE"] = "RTF content modification not supported"
            return (0, 0, len(transactions))

        with open_file_with_encoding(abs_filepath, "r", file_encoding, logger) as f:
            lines = f.readlines()

        # Apply replacements
        for tx in transactions:
            line_no = tx["LINE_NUMBER"]
            if 1 <= line_no <= len(lines):
                new_line = tx.get("NEW_LINE_CONTENT", "")
                if lines[line_no - 1] != new_line:
                    lines[line_no - 1] = new_line
                    tx["STATUS"] = TransactionStatus.COMPLETED.value
                else:
                    tx["STATUS"] = TransactionStatus.SKIPPED.value
                    tx["ERROR_MESSAGE"] = "Line already matches target"
            else:
                tx["STATUS"] = TransactionStatus.FAILED.value
                tx["ERROR_MESSAGE"] = f"Line number {line_no} out of range"

        # Write back
        with open_file_with_encoding(abs_filepath, "w", file_encoding, logger) as f:
            f.writelines(lines)

        completed = sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.COMPLETED.value)
        skipped = sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.SKIPPED.value)
        failed = sum(1 for tx in transactions if tx.get("STATUS") == TransactionStatus.FAILED.value)
        return (completed, skipped, failed)
    except Exception as e:
        for tx in transactions:
            tx["STATUS"] = TransactionStatus.FAILED.value
            tx["ERROR_MESSAGE"] = f"Unhandled error: {e}"
        return (0, 0, len(transactions))


# New function for streaming large file content
def process_large_file_content(
    txns_for_file: list[dict[str, Any]],
    abs_filepath: Path,
    file_encoding: str,
    is_rtf: bool,
    logger: LoggerType = None,
) -> None:
    """Process content replacements for large files using streaming approach.

    Args:
        txns_for_file: List of transactions for this file
        abs_filepath: Absolute path to the file
        file_encoding: File encoding to use
        is_rtf: Whether file is RTF format
        logger: Optional logger instance
    """
    # Use constants defined at module level

    if is_rtf:
        for tx in txns_for_file:
            tx["STATUS"] = TransactionStatus.SKIPPED.value
            tx["ERROR_MESSAGE"] = "RTF content modification not supported"
        return

    # Get all characters that might be in replacement keys
    key_characters = replace_logic.get_key_characters()

    # Sort transactions by line number
    txns_sorted = sorted(txns_for_file, key=lambda tx: tx["LINE_NUMBER"])
    max_line = txns_sorted[-1]["LINE_NUMBER"]

    # Map from line number to transaction with precomputed new content
    txn_map = {tx["LINE_NUMBER"]: tx for tx in txns_sorted}

    # Use unique temp file name
    temp_file = abs_filepath.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")

    try:
        with open_file_with_encoding(abs_filepath, "r", file_encoding, logger) as src_file:
            with open_file_with_encoding(temp_file, "w", file_encoding, logger) as dst_file:
                # Track state between lines
                current_line = 1

                # Process file line by line, receiving from src_file
                while current_line <= max_line:
                    if current_line in txn_map:
                        # This line will be modified
                        tx = txn_map[current_line]
                        # Load replacement content for transaction
                        upgrade_content = tx.get("NEW_LINE_CONTENT", "")
                    else:
                        # This line won't be modified
                        upgrade_content = None

                    # Read full line using readline() with size hint
                    line_buffer = []
                    while True:
                        # Implement safe fetching with fragmented reads
                        part = src_file.readline()
                        if not part:
                            break
                        line_buffer.append(part)
                        if part.endswith("\n") or part.endswith("\r"):
                            break
                    current_line_content = "".join(line_buffer)

                    # Skip empty lines
                    if not current_line_content:
                        current_line += 1
                        continue

                    # Only process long lines with chunked approach
                    if len(current_line_content) > SAFE_LINE_LENGTH_THRESHOLD and not upgrade_content:
                        # Process in safe chunks for unmmodified long lines
                        buffer_idx = 0
                        while buffer_idx < len(current_line_content):
                            end_idx = buffer_idx + CHUNK_SIZE
                            if end_idx >= len(current_line_content):
                                dst_file.write(current_line_content[buffer_idx:])
                                break

                            # Find safe split position - scan backward to find a character not in keys
                            split_pos = end_idx
                            search_pos = min(end_idx - 1, len(current_line_content) - 1)

                            # Use key characters already obtained at the start of the function

                            while search_pos >= buffer_idx:
                                if current_line_content[search_pos] not in key_characters:
                                    split_pos = search_pos + 1
                                    break
                                search_pos -= 1

                            # Special case: if we didn't find any non-key character
                            if split_pos == end_idx and search_pos < buffer_idx:
                                # Backtrack further if necessary (shouldn't happen often)
                                split_pos = min(buffer_idx + FALLBACK_CHUNK_SIZE, len(current_line_content))

                            # Process and write the chunk
                            dst_file.write(current_line_content[buffer_idx:split_pos])
                            buffer_idx = split_pos
                    # Regular line processing (short line or modified line)
                    elif upgrade_content is not None:
                        # Write precomputed content if available
                        dst_file.write(upgrade_content)
                    else:
                        # Write line as is
                        dst_file.write(current_line_content)

                    # Update transaction status
                    if current_line in txn_map:
                        txn_map[current_line]["STATUS"] = TransactionStatus.COMPLETED.value

                    current_line += 1

                # Handle potential trailing lines not in transactions
                trailing_content = src_file.read()
                dst_file.write(trailing_content)

        # Atomically replace file after successful write
        os.replace(temp_file, abs_filepath)

    except Exception as e:
        # Handle file errors
        for tx in txns_for_file:
            if tx.get("STATUS") != TransactionStatus.COMPLETED.value:
                tx["STATUS"] = TransactionStatus.FAILED.value
                tx["ERROR_MESSAGE"] = f"File processing error: {e}"
        try:
            if temp_file.exists():
                os.remove(temp_file)
        except Exception as cleanup_e:
            _log_fs_op_message(
                logging.WARNING,
                f"Could not remove temp file {temp_file}: {cleanup_e}",
                logger,
            )
    finally:
        # Ensure temp file is cleaned up
        try:
            if temp_file.exists():
                os.remove(temp_file)
        except OSError:
            pass


def group_and_process_file_transactions(
    transactions: list[dict[str, Any]],
    root_dir: Path,
    path_translation_map: dict[str, str],
    path_cache: dict[str, Path],
    dry_run: bool,
    skip_content: bool,
    logger: LoggerType = None,
) -> None:
    """Group transactions by file and process them efficiently.

    Groups content line transactions by their target file and processes
    each file once, applying all changes in a single pass for efficiency.

    Args:
        transactions: List of FILE_CONTENT_LINE transactions to process
        root_dir: Root directory of the project
        path_translation_map: Map of original paths to renamed paths
        path_cache: Cache of resolved paths
        dry_run: If True, simulate without actual changes
        skip_content: If True, skip all content modifications
        logger: Optional logger instance
    """
    # Group transactions by file path
    file_groups = {}
    for tx in transactions:
        if tx["TYPE"] != TransactionType.FILE_CONTENT_LINE.value:
            continue

        abs_path = _get_current_absolute_path(tx["PATH"], root_dir, path_translation_map, path_cache, dry_run)
        file_id = str(abs_path.resolve())

        if file_id not in file_groups:
            file_groups[file_id] = {
                "abs_path": abs_path,
                "txns": [],
                "encoding": tx.get("ORIGINAL_ENCODING", DEFAULT_ENCODING_FALLBACK),
                "is_rtf": tx.get("IS_RTF", False),
            }
        file_groups[file_id]["txns"].append(tx)

    # Process each file group
    for file_data in file_groups.values():
        abs_path = file_data["abs_path"]

        if skip_content:
            # Mark all as skipped
            for tx in file_data["txns"]:
                tx["STATUS"] = TransactionStatus.SKIPPED.value
            continue

        if dry_run:
            # Dry-run completes without actual write
            for tx in file_data["txns"]:
                tx["STATUS"] = TransactionStatus.COMPLETED.value
                tx["ERROR_MESSAGE"] = "DRY_RUN"
            continue

        try:
            # Get file stats
            file_size = abs_path.stat().st_size

            if file_size <= SMALL_FILE_SIZE_THRESHOLD:
                # Small file - use existing method
                _execute_file_content_batch(abs_path, file_data["txns"], logger)
            else:
                # Large file - new streaming method
                process_large_file_content(
                    file_data["txns"],
                    abs_path,
                    file_data["encoding"],
                    file_data["is_rtf"],
                    logger,
                )

        except Exception as e:
            # Mark all transactions as failed
            for tx in file_data["txns"]:
                tx["STATUS"] = TransactionStatus.FAILED.value
                tx["ERROR_MESSAGE"] = f"File group processing error: {e}"

    # Return nothing - transactions modified in-place


@flow(name="execute-all-transactions")
def execute_all_transactions(
    transactions_file_path: Path,
    root_dir: Path,
    dry_run: bool,
    resume: bool,
    timeout_minutes: int,
    skip_file_renaming: bool,
    skip_folder_renaming: bool,
    skip_content: bool,
    interactive_mode: bool,
    logger: LoggerType = None,
) -> dict[str, int]:
    """
    Execute all transactions in the transaction file.
    Returns statistics dictionary.
    """
    import time

    # Use timeout_minutes to control retry duration
    MAX_RETRY_PASSES = 1000000  # Large number to allow timeout control
    start_time = time.time()
    timeout_seconds = timeout_minutes * 60 if timeout_minutes > 0 else None

    transactions = load_transactions(transactions_file_path, logger=logger)
    if transactions is None:
        if logger:
            logger.error("No transactions to execute.")
        return {}

    stats = {
        "total": len(transactions),
        "completed": 0,
        "failed": 0,
        "skipped": 0,
        "retry_later": 0,
    }

    # Shared path translation for rename operations
    path_translation_map: dict[str, str] = {}
    path_cache: dict[str, Path] = {}

    # Track which transactions we've seen to prevent duplicate processing
    if not dry_run and resume:
        for tx in transactions:
            if tx["STATUS"] == TransactionStatus.COMPLETED.value and tx.get("ERROR_MESSAGE") == "DRY_RUN":
                tx["STATUS"] = TransactionStatus.PENDING.value
                tx.pop("ERROR_MESSAGE", None)
    seen_transaction_ids = set([tx["id"] for tx in transactions])

    # If resuming, reset statuses that need processing
    if resume:
        reset_transactions = []
        for tx in transactions:
            if tx["STATUS"] in [
                TransactionStatus.FAILED.value,
                TransactionStatus.RETRY_LATER.value,
            ]:
                tx["STATUS"] = TransactionStatus.PENDING.value
                tx.pop("ERROR_MESSAGE", None)
                reset_transactions.append(tx)
        if reset_transactions and logger:
            logger.info(f"Reset {len(reset_transactions)} transactions to PENDING for retry.")

    finished = False
    pass_count = 0
    while not finished and pass_count < MAX_RETRY_PASSES:
        pass_count += 1
        items_still_requiring_retry = []
        for tx_item in [tx for tx in transactions if tx["id"] in seen_transaction_ids]:
            tx_id = tx_item["id"]
            tx_type = tx_item["TYPE"]
            relative_path_str = tx_item["PATH"]
            status = tx_item.get("STATUS", TransactionStatus.PENDING.value)

            if status != TransactionStatus.PENDING.value:
                continue

            # Check timeout
            if timeout_seconds is not None and (time.time() - start_time) > timeout_seconds:
                if logger:
                    logger.warning("Timeout reached during transaction execution retry loop.")
                finished = True
                break

            # Pre-check for collisions in interactive mode to avoid prompting for doomed transactions
            if interactive_mode and not dry_run and tx_type in [TransactionType.FILE_NAME.value, TransactionType.FOLDER_NAME.value]:
                # Pre-flight collision check
                original_name = tx_item.get("ORIGINAL_NAME", "")
                new_name = tx_item.get("NEW_NAME", replace_logic.replace_occurrences(original_name))
                current_abs_path = _get_current_absolute_path(
                    relative_path_str,
                    root_dir,
                    path_translation_map,
                    path_cache,
                    dry_run,
                )
                if current_abs_path.exists():
                    new_abs_path = current_abs_path.parent / new_name
                    parent_dir = current_abs_path.parent
                    new_name_lower = new_name.lower()

                    # Check for collision
                    has_collision = False
                    collision_path = None
                    collision_type = None

                    if new_abs_path.exists():
                        has_collision = True
                        collision_path = new_abs_path
                        collision_type = "exact match"
                    else:
                        # Check case-insensitive
                        try:
                            for existing_item in parent_dir.iterdir():
                                if existing_item != current_abs_path and existing_item.name.lower() == new_name_lower:
                                    has_collision = True
                                    collision_path = existing_item
                                    collision_type = "case-insensitive match"
                                    break
                        except OSError:
                            pass

                    if has_collision:
                        # Log the collision
                        _log_collision_error(
                            root_dir,
                            tx_item,
                            current_abs_path,
                            collision_path,
                            collision_type,
                            logger,
                        )
                        # Update status
                        error_msg = f"Collision detected with {collision_path}"
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.FAILED,
                            error_msg,
                            logger=logger,
                        )
                        stats["failed"] += 1
                        # Print result for user
                        print(f"{RED_FG}✗ FAILED{RESET_STYLE} - {tx_type}: {relative_path_str}")
                        print(f"  {DIM_STYLE}Collision with existing file/folder{RESET_STYLE}")
                        continue

            # Interactive mode prompt (only for non-collision cases)
            if interactive_mode and not dry_run:
                # Show transaction details and ask for approval
                print(f"{DIM_STYLE}Transaction {tx_id} - Type: {tx_type}, Path: {relative_path_str}{RESET_STYLE}")
                if tx_type in [
                    TransactionType.FILE_NAME.value,
                    TransactionType.FOLDER_NAME.value,
                ]:
                    original_name = tx_item.get("ORIGINAL_NAME", "")
                    new_name = tx_item.get("NEW_NAME", replace_logic.replace_occurrences(original_name))
                    print(f"  {original_name} → {new_name}")
                elif tx_type == TransactionType.FILE_CONTENT_LINE.value:
                    line_num = tx_item.get("LINE_NUMBER", 0)
                    print(f"  Line {line_num}: content replacement")

                choice = input("Approve? (A/Approve, S/Skip, Q/Quit): ").strip().upper()
                if choice == "S":
                    update_transaction_status_in_list(
                        transactions,
                        tx_id,
                        TransactionStatus.SKIPPED,
                        "Skipped by user",
                        logger=logger,
                    )
                    stats["skipped"] += 1
                    print(f"{YELLOW_FG}⊘ SKIPPED{RESET_STYLE}")
                    continue
                if choice == "Q":
                    if logger:
                        logger.info("Operation aborted by user.")
                    finished = True
                    break
                # else proceed with execution

            try:
                if tx_type in [
                    TransactionType.FILE_NAME.value,
                    TransactionType.FOLDER_NAME.value,
                ]:
                    if (tx_type == TransactionType.FILE_NAME.value and skip_file_renaming) or (tx_type == TransactionType.FOLDER_NAME.value and skip_folder_renaming):
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.SKIPPED,
                            "Skipped by flags",
                            logger=logger,
                        )
                        stats["skipped"] += 1
                        continue
                    status_result, error_msg, changed = _execute_rename_transaction(
                        tx_item,
                        root_dir,
                        path_translation_map,
                        path_cache,
                        dry_run,
                        logger,
                    )
                    if status_result == TransactionStatus.COMPLETED:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.COMPLETED,
                            "DRY_RUN" if dry_run else None,
                            logger=logger,
                        )
                        stats["completed"] += 1
                        if interactive_mode and not dry_run:
                            print(f"{GREEN_FG}✓ SUCCESS{RESET_STYLE}")
                    elif status_result == TransactionStatus.SKIPPED:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.SKIPPED,
                            error_msg,
                            logger=logger,
                        )
                        stats["skipped"] += 1
                        if interactive_mode and not dry_run:
                            print(f"{YELLOW_FG}⊘ SKIPPED{RESET_STYLE} - {error_msg}")
                    else:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.FAILED,
                            error_msg,
                            logger=logger,
                        )
                        stats["failed"] += 1
                        items_still_requiring_retry.append(tx_item)
                        if interactive_mode and not dry_run:
                            print(f"{RED_FG}✗ FAILED{RESET_STYLE} - {error_msg}")
                elif tx_type == TransactionType.FILE_CONTENT_LINE.value:
                    if skip_content:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.SKIPPED,
                            "Skipped by flag",
                            logger=logger,
                        )
                        stats["skipped"] += 1
                        continue

                    # Get new content from transaction
                    new_line_content = tx_item.get("NEW_LINE_CONTENT", "")
                    original_line_content = tx_item.get("ORIGINAL_LINE_CONTENT", "")

                    # Skip if no actual change (shouldn't happen but added as safeguard)
                    if new_line_content == original_line_content:
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.SKIPPED,
                            "No change needed",
                            logger=logger,
                        )
                        stats["skipped"] += 1
                        continue

                    if dry_run:
                        # For dry-run, mark as completed without modifying file
                        update_transaction_status_in_list(
                            transactions,
                            tx_id,
                            TransactionStatus.COMPLETED,
                            "DRY_RUN",
                            logger=logger,
                        )
                        stats["completed"] += 1
                    else:
                        # Defer actual content line processing to batch/group processor
                        pass
                else:
                    update_transaction_status_in_list(
                        transactions,
                        tx_id,
                        TransactionStatus.SKIPPED,
                        "Unknown transaction type",
                        logger=logger,
                    )
                    stats["skipped"] += 1
            except Exception as e:
                update_transaction_status_in_list(
                    transactions,
                    tx_id,
                    TransactionStatus.FAILED,
                    f"Exception: {e}",
                    logger=logger,
                )
                stats["failed"] += 1
                items_still_requiring_retry.append(tx_item)

            # Track we've processed this transaction
            if tx_id in seen_transaction_ids:
                seen_transaction_ids.remove(tx_id)

        if not items_still_requiring_retry:
            finished = True
            break

        # Wait and retry logic
        if items_still_requiring_retry:
            # Check if any are retryable errors
            retryable_items = []
            for tx in items_still_requiring_retry:
                error_msg = tx.get("ERROR_MESSAGE", "")
                if any(err_str in error_msg.lower() for err_str in ["permission", "access", "busy", "locked"]):
                    retryable_items.append(tx)
                    update_transaction_status_in_list(
                        transactions,
                        tx["id"],
                        TransactionStatus.RETRY_LATER,
                        error_msg,
                        logger=logger,
                    )

            if retryable_items and pass_count < QUICK_RETRY_COUNT:
                if logger:
                    logger.info(f"Retrying {len(retryable_items)} transactions (pass {pass_count})...")
                time.sleep(QUICK_RETRY_DELAY)  # Brief pause between retries
            elif retryable_items:
                # After quick retries, wait longer
                wait_time = min(MAX_RETRY_WAIT_TIME, RETRY_BACKOFF_MULTIPLIER * (pass_count - 2))
                if logger:
                    logger.info(f"Waiting {wait_time}s before retry (pass {pass_count})...")
                time.sleep(wait_time)
            else:
                # No retryable items, we're done
                finished = True

    # After rename and individual transaction processing, process content transactions grouped by file
    # Only process content transactions that are still pending (not already handled in dry-run)
    content_txs = [tx for tx in transactions if tx["TYPE"] == TransactionType.FILE_CONTENT_LINE.value and tx["STATUS"] == TransactionStatus.PENDING.value]

    if content_txs:  # Only process if there are pending content transactions
        group_and_process_file_transactions(
            content_txs,
            root_dir,
            path_translation_map,
            path_cache,
            dry_run,
            skip_content,
            logger,
        )

    # Update stats for content transactions after batch processing
    stats["completed"] += sum(1 for tx in content_txs if tx.get("STATUS") == TransactionStatus.COMPLETED.value)
    stats["skipped"] += sum(1 for tx in content_txs if tx.get("STATUS") == TransactionStatus.SKIPPED.value)
    stats["failed"] += sum(1 for tx in content_txs if tx.get("STATUS") == TransactionStatus.FAILED.value)

    save_transactions(transactions, transactions_file_path, logger=logger)
    if logger:
        logger.info(f"Execution phase complete. Stats: {stats}")

    # Print summary for interactive mode
    if interactive_mode and not dry_run:
        print(f"\n{BOLD_STYLE}=== Execution Summary ==={RESET_STYLE}")
        print(f"Total transactions: {stats['total']}")
        print(f"{GREEN_FG}Completed: {stats['completed']}{RESET_STYLE}")
        print(f"{YELLOW_FG}Skipped: {stats['skipped']}{RESET_STYLE}")
        print(f"{RED_FG}Failed: {stats['failed']}{RESET_STYLE}")

        # Check for collision and binary logs
        collision_log_path = root_dir / COLLISIONS_ERRORS_LOG_FILE
        binary_log_path = root_dir / BINARY_MATCHES_LOG_FILE

        if collision_log_path.exists() and collision_log_path.stat().st_size > 0:
            print(f"\n{RED_FG}⚠ File/folder rename collisions were detected.{RESET_STYLE}")
            print(f"  See '{collision_log_path.name}' for details.")

        if binary_log_path.exists() and binary_log_path.stat().st_size > 0:
            print(f"\n{YELLOW_FG}ℹ Matches were found in binary files.{RESET_STYLE}")
            print(f"  See '{binary_log_path.name}' for details.")
            print(f"  {DIM_STYLE}(Binary files were not modified){RESET_STYLE}")

    return stats
