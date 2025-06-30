#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of directory walking logic from scanning.py
# - This module handles recursive directory traversal with symlink handling
#

"""
Directory walker for the Mass Find Replace scanner.

This module provides functionality to walk through directory trees while
handling exclusions, symlinks, and gitignore patterns.
"""

from __future__ import annotations

import os
import logging
from pathlib import Path
from typing import Iterator
import pathspec

from ..types import LoggerType
from ...utils import log_fs_op_message

__all__ = [
    "walk_for_scan",
]


def walk_for_scan(
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
                f"Unexpected error processing item {item_path_from_rglob} in walk_for_scan: {e_gen}. Skipping item.",
                logger,
            )
            continue
