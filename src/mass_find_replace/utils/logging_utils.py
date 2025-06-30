#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of logging utilities from file_system_operations.py
# - Includes message logging and collision error logging functions
#

"""
Logging utilities for the Mass Find Replace application.

This module provides logging helper functions that can work with or without
a formal logger instance.
"""

from __future__ import annotations
import logging
import time
from pathlib import Path
from typing import Any

from ..core.types import LoggerType
from ..core.constants import COLLISIONS_ERRORS_LOG_FILE


def log_fs_op_message(level: int, message: str, logger: LoggerType = None) -> None:
    """Helper to log messages using provided logger or print as fallback.

    This function provides a unified interface for logging that works whether
    or not a logger instance is available.

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


def log_collision_error(
    root_dir: Path,
    tx: dict[str, Any],
    source_path: Path,
    collision_path: Path | None,
    collision_type: str | None,
    logger: LoggerType = None,
) -> None:
    """Log collision errors to a dedicated file.

    When file/folder rename operations would result in naming collisions,
    this function logs the details to a collision log file for review.

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

        with collision_log_path.open("a", encoding="utf-8") as log_f:
            log_f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - COLLISION ({collision_type}):\n")
            log_f.write(f"  Source: {source_rel}\n")
            log_f.write(f"  Target: {tx.get('new_path', 'N/A')}\n")
            if collision_rel:
                log_f.write(f"  Collision with: {collision_rel}\n")
            log_f.write(f"  Transaction ID: {tx.get('id', 'N/A')}\n")
            log_f.write("-" * 80 + "\n")

        log_fs_op_message(
            logging.WARNING,
            f"Collision logged to {COLLISIONS_ERRORS_LOG_FILE}: {collision_type} for {source_path}",
            logger,
        )
    except Exception as e:
        log_fs_op_message(
            logging.ERROR,
            f"Failed to log collision error: {e}",
            logger,
        )
