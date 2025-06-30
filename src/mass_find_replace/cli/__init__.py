#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial creation of cli module
#

"""
Command-line interface module for Mass Find Replace.

This module contains the CLI argument parsing and validation.
"""

from .parser import main_cli

__all__ = ["main_cli"]
