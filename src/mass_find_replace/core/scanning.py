#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of scanning functionality from file_system_operations.py
# - Includes directory walking and file scanning logic
#

"""
Directory scanning functionality for the Mass Find Replace application.

This module provides functions for scanning directories to find files and folders
that need renaming or content replacement based on configured patterns.
"""

from __future__ import annotations
import os
import logging
from pathlib import Path
from typing import Any, Iterator
import pathspec
import unicodedata
import time
import uuid
from striprtf.striprtf import rtf_to_text
from isbinary import is_binary_file

from .. import replace_logic
from ..utils import (
    log_fs_op_message,
    get_file_encoding,
    open_file_with_encoding,
)
from .constants import (
    DEFAULT_ENCODING_FALLBACK,
    LARGE_FILE_SIZE_THRESHOLD,
    BINARY_MATCHES_LOG_FILE,
)
from .types import (
    LoggerType,
    TransactionType,
    TransactionStatus,
)


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
                        log_fs_op_message(
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
                            log_fs_op_message(
                                logging.WARNING,
                                f"Symlink points to ancestor directory: {item_path_from_rglob} -> {real_path}. Skipping to prevent infinite recursion.",
                                logger,
                            )
                            continue
                    except (OSError, ValueError):
                        pass  # Continue if we can't resolve paths

                except Exception as e:
                    log_fs_op_message(
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
                    log_fs_op_message(
                        logging.WARNING,
                        f"Error during ignore_spec matching for {item_path_from_rglob} relative to {root_dir}: {e_spec}",
                        logger,
                    )
            yield item_path_from_rglob
        except OSError as e_os:  # Catch OSError from is_symlink, is_dir
            log_fs_op_message(
                logging.WARNING,
                f"OS error accessing attributes of {item_path_from_rglob}: {e_os}. Skipping item.",
                logger,
            )
            continue
        except Exception as e_gen:  # Catch any other unexpected error for this item
            log_fs_op_message(
                logging.ERROR,
                f"Unexpected error processing item {item_path_from_rglob} in _walk_for_scan: {e_gen}. Skipping item.",
                logger,
            )
            continue


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
            log_fs_op_message(
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
                    log_fs_op_message(
                        logging.WARNING,
                        f"Could not resolve symlink target for {relative_path_str}: {e_resolve}. Skipping.",
                        logger,
                    )
                    continue
                if root_dir not in target.parents and target != root_dir:
                    log_fs_op_message(
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
            log_fs_op_message(
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

                    # First check if file has a text extension - if so, always treat as text
                    text_extensions = {
                        # Documentation/Config
                        ".txt",
                        ".log",
                        ".md",
                        ".rst",
                        ".ini",
                        ".cfg",
                        ".conf",
                        ".toml",
                        ".env",
                        ".properties",
                        ".bib",
                        ".tex",
                        ".adoc",
                        # Programming languages
                        ".py",
                        ".js",
                        ".ts",
                        ".jsx",
                        ".tsx",
                        ".java",
                        ".c",
                        ".cpp",
                        ".cc",
                        ".cxx",
                        ".h",
                        ".hpp",
                        ".hh",
                        ".hxx",
                        ".cs",
                        ".rb",
                        ".go",
                        ".rs",
                        ".php",
                        ".sh",
                        ".bat",
                        ".ps1",
                        ".swift",
                        ".kt",
                        ".scala",
                        ".pl",
                        ".lua",
                        ".r",
                        ".m",
                        ".jl",
                        ".clj",
                        ".elm",
                        ".ex",
                        ".exs",
                        ".dart",
                        ".vue",
                        ".svelte",
                        # Web/Markup
                        ".html",
                        ".htm",
                        ".xml",
                        ".css",
                        ".scss",
                        ".sass",
                        ".less",
                        # Data formats
                        ".json",
                        ".yml",
                        ".yaml",
                        ".csv",
                        ".sql",
                        # Build/Project files
                        ".gradle",
                        ".sbt",
                        ".cmake",
                        ".make",
                        ".dockerfile",
                        ".gitignore",
                    }

                    has_text_extension = item_abs_path.suffix.lower() in text_extensions

                    # Only use binary detection for files without known text extensions
                    if has_text_extension:
                        is_bin = False
                    else:
                        try:
                            is_bin = is_binary_file(str(item_abs_path))
                        except FileNotFoundError:
                            log_fs_op_message(
                                logging.WARNING,
                                f"File not found for binary check: {item_abs_path}. Skipping content scan.",
                                logger,
                            )
                            continue
                        except Exception as e_isbin:
                            log_fs_op_message(
                                logging.WARNING,
                                f"Could not determine if {item_abs_path} is binary: {e_isbin}. Skipping content scan.",
                                logger,
                            )
                            continue

                    if is_bin and not is_rtf:
                        # Skip binary files but log them
                        log_fs_op_message(
                            logging.DEBUG,
                            f"Skipping binary file: {relative_path_str}",
                            logger,
                        )
                        if raw_keys_for_binary_search:
                            try:
                                # Process binary file in chunks to avoid memory exhaustion
                                BINARY_CHUNK_SIZE = 1_048_576  # 1MB chunks
                                with item_abs_path.open("rb") as bf:
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
                                                    with Path(binary_log_path).open("a", encoding="utf-8") as log_f:
                                                        log_f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - MATCH: File: {log_path_str}, Key: '{key_str}', Offset: {actual_offset}\n")
                                                offset = idx + len(key_bytes)

                                        # Update global offset
                                        global_offset += len(chunk) - (0 if search_offset >= 0 else -search_offset)

                                        # If we read less than chunk size, we're at EOF
                                        if len(chunk) < BINARY_CHUNK_SIZE + (overlap_size if global_offset > BINARY_CHUNK_SIZE else 0):
                                            break
                            except OSError as e_bin_read:
                                log_fs_op_message(
                                    logging.WARNING,
                                    f"OS error reading binary file {item_abs_path} for logging: {e_bin_read}",
                                    logger,
                                )
                            except Exception as e_bin_proc:
                                log_fs_op_message(
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
                            log_fs_op_message(
                                logging.WARNING,
                                f"OS error reading RTF file {item_abs_path}: {e_rtf_read}",
                                logger,
                            )
                            continue
                        except Exception as e_rtf_proc:
                            log_fs_op_message(
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
                            log_fs_op_message(
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
                log_fs_op_message(
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

    return folder_txs + file_txs + content_txs
