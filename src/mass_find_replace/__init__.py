#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE CODE:
# - Initial package structure for mass_find_replace module
# - Export main CLI function for entry point
# 

"""Mass Find Replace - Surgical find-and-replace operations."""

__version__ = "0.1.0"
__author__ = "Emasoft"
__email__ = "713559+Emasoft@users.noreply.github.com"

from .mass_find_replace import main_cli as main, run_self_test

__all__ = ["main", "run_self_test"]