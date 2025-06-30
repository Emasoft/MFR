#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial creation of __main__.py to enable python -m execution
#

"""
Main entry point for running mass_find_replace as a module.

This allows running the package with `python -m mass_find_replace`.
"""

from .cli.parser import main_cli

if __name__ == "__main__":
    main_cli()
