#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of exceptions from file_system_operations.py
# - Added docstrings to all exception classes
#

"""
Custom exceptions for the Mass Find Replace application.

This module contains all custom exception classes that were previously
defined in file_system_operations.py.
"""


class SandboxViolationError(Exception):
    """Raised when an operation attempts to access files outside the allowed directory."""

    pass


class MockableRetriableError(OSError):
    """Raised when an OS error occurs that can be retried in tests."""

    pass
