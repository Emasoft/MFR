#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of logger configuration from mass_find_replace.py
# - This module provides logger setup functionality
#

"""
Logger configuration utilities for Mass Find Replace.

This module provides functions for setting up logging with Prefect integration.
"""

from __future__ import annotations

import logging
from typing import Union

__all__ = ["get_logger"]


def get_logger(
    verbose_mode: bool = False,
) -> Union[logging.Logger, logging.LoggerAdapter[logging.Logger]]:
    """Get logger with appropriate configuration.

    Args:
        verbose_mode: Whether to enable verbose (DEBUG) logging

    Returns:
        Logger instance (standard or Prefect's context logger)
    """
    import logging

    try:
        # Try to get Prefect's context logger
        from prefect import get_run_logger
        from prefect.exceptions import MissingContextError

        try:
            logger: Union[logging.Logger, logging.LoggerAdapter[logging.Logger]] = get_run_logger()
            if verbose_mode:
                logger.setLevel(logging.DEBUG)
            # Type annotation helps mypy understand the logger type
            return logger
        except MissingContextError:
            pass
    except ImportError:
        pass

    # Create standard logger
    logger = logging.getLogger("mass_find_replace")
    logger.setLevel(logging.DEBUG if verbose_mode else logging.INFO)
    if not logger.handlers:
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger
