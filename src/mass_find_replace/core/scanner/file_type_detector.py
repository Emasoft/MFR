#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial extraction of file type detection logic from scanning.py
# - This module handles text/binary file detection and extensions
#

"""
File type detection utilities for the Mass Find Replace scanner.

This module provides functions to detect whether files are text or binary,
and to determine appropriate file extensions for content scanning.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

__all__ = [
    "TEXT_EXTENSIONS",
    "is_text_extension",
    "should_process_content",
]

# Text file extensions that should always be treated as text
TEXT_EXTENSIONS: Final[set[str]] = {
    # Documentation/Config
    ".txt",
    ".log",
    ".md",
    ".rst",
    ".ini",
    ".cfg",
    ".conf",
    ".toml",
    ".env",
    ".properties",
    ".bib",
    ".tex",
    ".cls",
    ".sty",
    # Data formats
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".csv",
    ".tsv",
    # Web
    ".html",
    ".htm",
    ".xhtml",
    ".css",
    ".scss",
    ".sass",
    ".less",
    # Programming languages
    ".py",
    ".pyw",
    ".pyx",
    ".pyi",
    ".pxd",
    ".ipynb",  # Python
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",  # JavaScript/TypeScript
    ".java",
    ".groovy",
    ".scala",
    ".kt",
    ".kts",  # JVM
    ".c",
    ".h",
    ".cpp",
    ".cc",
    ".cxx",
    ".hpp",
    ".hxx",
    ".hh",  # C/C++
    ".cs",
    ".fs",
    ".vb",  # .NET
    ".go",
    ".rs",
    ".swift",
    ".m",
    ".mm",  # Modern systems
    ".r",
    ".R",
    ".rmd",
    ".Rmd",  # R
    ".pl",
    ".pm",
    ".t",
    ".pod",  # Perl
    ".rb",
    ".rake",
    ".gemspec",  # Ruby
    ".php",
    ".phtml",
    ".php3",
    ".php4",
    ".php5",
    ".php7",
    ".phps",  # PHP
    ".lua",
    ".vim",
    ".vimrc",  # Scripting
    ".sql",
    ".psql",
    ".mysql",  # Database
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".ksh",
    ".csh",
    ".tcsh",  # Shell
    ".ps1",
    ".psm1",
    ".psd1",  # PowerShell
    ".bat",
    ".cmd",  # Windows batch
    ".asm",
    ".s",  # Assembly
    ".lisp",
    ".cl",
    ".el",
    ".scm",
    ".clj",
    ".cljs",
    ".cljc",  # Lisp family
    ".hs",
    ".lhs",
    ".ml",
    ".mli",
    ".fs",
    ".fsi",
    ".fsx",  # Functional
    ".dart",
    ".elm",
    ".ex",
    ".exs",
    ".erl",
    ".hrl",  # Other
    ".pas",
    ".pp",
    ".inc",  # Pascal
    ".f",
    ".f90",
    ".f95",
    ".for",  # Fortran
    ".jl",  # Julia
    ".nim",
    ".nims",  # Nim
    ".cr",  # Crystal
    ".zig",  # Zig
    ".v",
    ".vh",  # Verilog
    ".vhd",
    ".vhdl",  # VHDL
    # Build/Project files
    ".cmake",
    ".make",
    ".mk",
    ".mak",
    ".makefile",
    ".gnumakefile",
    ".gradle",
    ".sbt",
    ".maven",
    ".ant",
    ".dockerfile",
    ".containerfile",
    ".jenkinsfile",
    ".travis.yml",
    ".gitlab-ci.yml",
    ".github",
    ".editorconfig",
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    ".npmignore",
    ".dockerignore",
    ".eslintrc",
    ".prettierrc",
    ".babelrc",
    ".webpack",
    ".rollup",
    # Other text formats
    ".rtf",  # Rich text (special handling)
    ".diff",
    ".patch",
    ".po",
    ".pot",  # Translations
    ".srt",
    ".vtt",
    ".sub",  # Subtitles
    ".ics",
    ".vcf",  # Calendar/Contact
    ".reg",  # Windows registry
    ".desktop",
    ".service",  # Linux desktop/systemd
    ".plist",  # macOS property list
    ".manifest",
    ".rc",
    ".resx",  # Windows resources
}


def is_text_extension(file_path: Path) -> bool:
    """Check if file has a text extension.

    Args:
        file_path: Path to check

    Returns:
        True if file has a text extension
    """
    return file_path.suffix.lower() in TEXT_EXTENSIONS


def should_process_content(
    file_path: Path,
    file_extensions: list[str] | None,
    check_size: bool = True,
    size_limit: int = 100 * 1024 * 1024,  # 100MB default
) -> bool:
    """Determine if file content should be processed.

    Args:
        file_path: Path to file
        file_extensions: Allowed extensions or None for all
        check_size: Whether to check file size
        size_limit: Maximum file size in bytes

    Returns:
        True if file should be processed
    """
    # Check size first if requested
    if check_size:
        try:
            if file_path.stat().st_size > size_limit:
                return False
        except OSError:
            return False

    # If no extensions specified, process all files
    if file_extensions is None:
        return True

    # Check if file extension is in the allowed list
    suffix = file_path.suffix.lower()
    return any(suffix == ext.lower() if ext.startswith(".") else suffix == f".{ext.lower()}" for ext in file_extensions)
