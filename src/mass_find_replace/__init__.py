#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE CODE:
# - Initial package structure for mass_find_replace module
# - Export main CLI function for entry point
# - Added license header and encoding declaration
#

# Copyright (c) 2024 Emasoft
#
# This software is licensed under the MIT License.
# Refer to the LICENSE file for more details.

"""Mass Find Replace - Surgical find-and-replace operations."""

__version__ = "0.3.0-alpha"
__author__ = "Emasoft"
__email__ = "713559+Emasoft@users.noreply.github.com"

from .mass_find_replace import main_cli as main

__all__ = ["main"]
