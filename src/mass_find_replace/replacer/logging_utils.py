#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of logging utilities from replace_logic.py
# - This module handles logging with fallback to print statements
#

"""
Logging utilities for the Mass Find Replace replacer.

This module provides logging functionality with fallback to print statements
when no logger is available.
"""

from __future__ import annotations
import logging
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from logging import Logger, LoggerAdapter

from .state import get_module_logger, is_debug_enabled

__all__ = [
    "log_message",
]


def log_message(
    level: int,
    message: str,
    logger: Logger | LoggerAdapter[Logger] | None = None,
) -> None:
    """Helper to log messages using provided logger or print as fallback."""
    effective_logger = logger if logger else get_module_logger()

    if is_debug_enabled() and level == logging.DEBUG:
        # Print DEBUG messages directly to stderr when debug is enabled
        print(f"RL_DBG_STDERR: {message}", file=sys.stderr)
        sys.stderr.flush()
        # Optionally, also log to the intended logger if it's different
        if effective_logger:
            effective_logger.debug(message)
        return

    # For other levels, or if not debug enabled for DEBUG level
    if effective_logger:
        effective_logger.log(level, message)
    elif level >= logging.INFO:  # Fallback print for INFO and above if no logger
        prefix = ""
        if level == logging.ERROR:
            prefix = "ERROR: "
        elif level == logging.WARNING:
            prefix = "WARNING: "
        elif level == logging.INFO:
            prefix = "INFO: "
        print(
            f"{prefix}{message}",
            file=sys.stderr if level >= logging.WARNING else sys.stdout,
        )
        if level >= logging.WARNING:
            sys.stderr.flush()
        else:
            sys.stdout.flush()
