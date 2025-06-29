#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of file locking functionality from file_system_operations.py
# - Cross-platform file locking with timeout support
#

"""
Cross-platform file locking utilities.

This module provides a context manager for file locking that works on both
Windows and Unix-like systems.
"""

from __future__ import annotations
import contextlib
import errno
import sys
import time
from typing import Any
from collections.abc import Iterator

# Platform-specific imports for file locking
if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


@contextlib.contextmanager
def file_lock(file_handle: Any, exclusive: bool = True, timeout: float = 10.0) -> Iterator[Any]:
    """Cross-platform file locking context manager.

    This function provides a unified interface for file locking across Windows
    and Unix-like systems. It supports both exclusive and shared locks with
    a configurable timeout.

    Args:
        file_handle: Open file handle to lock
        exclusive: If True, acquire exclusive lock; if False, shared lock
        timeout: Maximum seconds to wait for lock

    Yields:
        The locked file handle

    Raises:
        TimeoutError: If lock cannot be acquired within timeout
        OSError: For other locking errors

    Example:
        with open('file.txt', 'r') as f:
            with file_lock(f, exclusive=False):
                content = f.read()
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
                        msg = f"Could not acquire file lock within {timeout} seconds"
                        raise TimeoutError(msg)
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
