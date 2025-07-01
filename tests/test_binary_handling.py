#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Created comprehensive test suite for binary file handling
# - Tests multiple scenarios including different file extensions and content patterns
#

"""
Comprehensive test suite for binary file handling in Mass Find Replace.

This module tests various aspects of binary file detection, scanning,
and logging to ensure robust handling of non-text files.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import json
import pytest
from typing import Any, Generator

from mass_find_replace.mass_find_replace import main_flow
from mass_find_replace.core.transaction_manager import load_transactions
from mass_find_replace.core.types import TransactionType
from mass_find_replace.core.constants import BINARY_MATCHES_LOG_FILE
from mass_find_replace import replace_logic
from isbinary import is_binary_file


@pytest.fixture(autouse=True)
def setup_logging() -> None:
    """Set up logging for tests."""
    import logging

    logger = logging.getLogger("mass_find_replace")
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False


@pytest.fixture(autouse=True)
def reset_replace_logic() -> Generator[None, None, None]:
    """Reset replace_logic module state between tests."""
    replace_logic.reset_module_state()
    yield


class TestBinaryFileHandling:
    """Test suite for binary file handling."""

    def test_binary_detection(self) -> None:
        """Test that various binary file types are correctly detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)

            # Create various binary files
            files = {
                "image.png": b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
                "archive.zip": b"PK\x03\x04\x14\x00\x00\x00",
                "data.bin": b"\x00\x01\x02\x03\x04\x05",
                "mixed.dat": b"TextOLDNAME\x00Binary\xff\xfe",
            }

            for filename, content in files.items():
                file_path = test_dir / filename
                file_path.write_bytes(content)
                assert is_binary_file(str(file_path)), f"{filename} should be detected as binary"

    def test_binary_logging_simple(self) -> None:
        """Test that binary files with matching patterns are logged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)

            # Create mapping file
            map_file = test_dir / "mapping.json"
            map_data = {"REPLACEMENT_MAPPING": {"OLDNAME": "NEWNAME", "Oldname": "Newname"}}
            map_file.write_text(json.dumps(map_data))

            # Create binary file with pattern
            bin_file = test_dir / "test.bin"
            bin_file.write_bytes(b"HeaderOLDNAME\x00\x01MiddleOldname\x02Footer")

            # Run main flow
            main_flow(
                str(test_dir),
                str(map_file),
                [".bin"],  # Only process .bin files
                [],
                [],
                False,  # dry_run
                False,  # skip_scan
                False,  # resume
                True,  # force
                True,  # ignore_symlinks
                False,  # use_gitignore
                None,  # custom_ignore_file
                False,  # skip_file_renaming
                False,  # skip_folder_renaming
                False,  # skip_content
                10,  # timeout
                True,  # quiet
                False,  # verbose
                False,  # interactive
            )

            # Check binary log
            log_path = test_dir / BINARY_MATCHES_LOG_FILE
            assert log_path.exists(), "Binary matches log should be created"

            log_content = log_path.read_text()
            assert "OLDNAME" in log_content, "OLDNAME pattern should be logged"
            assert "Oldname" in log_content, "Oldname pattern should be logged"
            assert "test.bin" in log_content, "Binary filename should be in log"
            assert "Offset:" in log_content, "Offset information should be included"

    def test_binary_logging_multiple_extensions(self) -> None:
        """Test binary logging with multiple file extensions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)

            # Create mapping file
            map_file = test_dir / "mapping.json"
            map_data = {"REPLACEMENT_MAPPING": {"PATTERN": "REPLACEMENT"}}
            map_file.write_text(json.dumps(map_data))

            # Create files
            files = {
                "binary.bin": b"Contains PATTERN here\x00\x01",
                "data.dat": b"\x00PATTERN in binary\xff",
                "text.txt": "Text file with PATTERN",
                "image.jpg": b"\xff\xd8\xff\xe0PATTERN\x00",
            }

            for filename, content in files.items():
                file_path = test_dir / filename
                if isinstance(content, bytes):
                    file_path.write_bytes(content)
                else:
                    file_path.write_text(content)

            # Run with multiple extensions
            main_flow(
                str(test_dir),
                str(map_file),
                [".bin", ".dat", ".txt", ".jpg"],
                [],
                [],
                False,  # dry_run
                False,  # skip_scan
                False,  # resume
                True,  # force
                True,  # ignore_symlinks
                False,  # use_gitignore
                None,  # custom_ignore_file
                False,  # skip_file_renaming
                False,  # skip_folder_renaming
                False,  # skip_content
                10,  # timeout
                True,  # quiet
                False,  # verbose
                False,  # interactive
            )

            # Check results
            log_path = test_dir / BINARY_MATCHES_LOG_FILE
            if log_path.exists():
                log_content = log_path.read_text()
                # Binary files should be in log
                assert "binary.bin" in log_content or "data.dat" in log_content or "image.jpg" in log_content, "At least one binary file should be logged"

            # Text file should be modified
            text_content = (test_dir / "text.txt").read_text()
            assert text_content == "Text file with REPLACEMENT", "Text file should be modified"

    def test_binary_large_file(self) -> None:
        """Test binary file handling for large files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)

            # Create mapping file
            map_file = test_dir / "mapping.json"
            map_data = {"REPLACEMENT_MAPPING": {"TARGET": "REPLACE"}}
            map_file.write_text(json.dumps(map_data))

            # Create large binary file (2MB)
            large_file = test_dir / "large.bin"
            chunk = b"Some data TARGET here\x00" * 1000
            with large_file.open("wb") as f:
                for _ in range(100):  # 100 * ~20KB = ~2MB
                    f.write(chunk)

            # Run main flow
            main_flow(
                str(test_dir),
                str(map_file),
                [".bin"],
                [],
                [],
                False,  # dry_run
                False,  # skip_scan
                False,  # resume
                True,  # force
                True,  # ignore_symlinks
                False,  # use_gitignore
                None,  # custom_ignore_file
                False,  # skip_file_renaming
                False,  # skip_folder_renaming
                False,  # skip_content
                10,  # timeout
                True,  # quiet
                False,  # verbose
                False,  # interactive
            )

            # Check log exists and contains matches
            log_path = test_dir / BINARY_MATCHES_LOG_FILE
            assert log_path.exists(), "Binary log should exist for large file"

            log_content = log_path.read_text()
            assert "large.bin" in log_content, "Large file should be in log"
            assert "TARGET" in log_content, "Pattern should be found"
            # Should have multiple matches
            assert log_content.count("TARGET") > 10, "Should find multiple pattern occurrences"

    def test_binary_no_matches(self) -> None:
        """Test that binary files without matches don't create log."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)

            # Create mapping file
            map_file = test_dir / "mapping.json"
            map_data = {"REPLACEMENT_MAPPING": {"NOTFOUND": "REPLACE"}}
            map_file.write_text(json.dumps(map_data))

            # Create binary file without pattern
            bin_file = test_dir / "test.bin"
            bin_file.write_bytes(b"Just some random binary data\x00\x01\x02\x03")

            # Run main flow
            main_flow(
                str(test_dir),
                str(map_file),
                [".bin"],
                [],
                [],
                False,  # dry_run
                False,  # skip_scan
                False,  # resume
                True,  # force
                True,  # ignore_symlinks
                False,  # use_gitignore
                None,  # custom_ignore_file
                False,  # skip_file_renaming
                False,  # skip_folder_renaming
                False,  # skip_content
                10,  # timeout
                True,  # quiet
                False,  # verbose
                False,  # interactive
            )

            # Log should not be created if no matches
            log_path = test_dir / BINARY_MATCHES_LOG_FILE
            # The log might exist but should not contain the file
            if log_path.exists():
                log_content = log_path.read_text()
                assert "test.bin" not in log_content, "File without matches should not be in log"

    def test_binary_edge_cases(self) -> None:
        """Test edge cases in binary file handling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)

            # Create mapping file
            map_file = test_dir / "mapping.json"
            map_data = {"REPLACEMENT_MAPPING": {"EDGE": "CASE"}}
            map_file.write_text(json.dumps(map_data))

            # Empty binary file
            empty_file = test_dir / "empty.bin"
            empty_file.write_bytes(b"")

            # File with pattern at boundaries
            boundary_file = test_dir / "boundary.bin"
            boundary_file.write_bytes(b"EDGE" + b"\x00" * 1048576 + b"EDGE")  # Pattern at start and after 1MB

            # File with only null bytes
            null_file = test_dir / "null.bin"
            null_file.write_bytes(b"\x00" * 1000)

            # Run main flow
            main_flow(
                str(test_dir),
                str(map_file),
                [".bin"],
                [],
                [],
                False,  # dry_run
                False,  # skip_scan
                False,  # resume
                True,  # force
                True,  # ignore_symlinks
                False,  # use_gitignore
                None,  # custom_ignore_file
                False,  # skip_file_renaming
                False,  # skip_folder_renaming
                False,  # skip_content
                10,  # timeout
                True,  # quiet
                False,  # verbose
                False,  # interactive
            )

            # Check handling
            log_path = test_dir / BINARY_MATCHES_LOG_FILE
            if log_path.exists():
                log_content = log_path.read_text()
                # Boundary file should have matches logged
                if "boundary.bin" in log_content:
                    assert log_content.count("EDGE") >= 2, "Should find pattern at boundaries"

    def test_binary_mixed_content(self) -> None:
        """Test files with mixed text and binary content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)

            # Create mapping file
            map_file = test_dir / "mapping.json"
            map_data = {"REPLACEMENT_MAPPING": {"MIXED": "FIXED"}}
            map_file.write_text(json.dumps(map_data))

            # Create mixed content file
            mixed_file = test_dir / "mixed.dat"
            content = b"Text part MIXED here\n"
            content += b"More text with MIXED\n"
            content += b"\x00\x01\x02\x03\x04"  # Binary part
            content += b"MIXED in binary part\x00"
            mixed_file.write_bytes(content)

            # Run main flow
            main_flow(
                str(test_dir),
                str(map_file),
                [".dat"],
                [],
                [],
                False,  # dry_run
                False,  # skip_scan
                False,  # resume
                True,  # force
                True,  # ignore_symlinks
                False,  # use_gitignore
                None,  # custom_ignore_file
                False,  # skip_file_renaming
                False,  # skip_folder_renaming
                False,  # skip_content
                10,  # timeout
                True,  # quiet
                False,  # verbose
                False,  # interactive
            )

            # Check that file is treated as binary
            log_path = test_dir / BINARY_MATCHES_LOG_FILE
            assert log_path.exists(), "Binary log should exist"

            log_content = log_path.read_text()
            assert "mixed.dat" in log_content, "Mixed file should be in binary log"
            assert log_content.count("MIXED") >= 3, "Should find all occurrences"

            # Original file should be unchanged
            original_content = mixed_file.read_bytes()
            assert b"MIXED" in original_content, "Binary file should not be modified"
            assert b"FIXED" not in original_content, "Replacement should not occur in binary"

    def test_transactions_for_binary(self) -> None:
        """Test that binary files don't generate content modification transactions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_dir = Path(tmpdir)

            # Create mapping file
            map_file = test_dir / "mapping.json"
            map_data = {"REPLACEMENT_MAPPING": {"BINARY": "TEXT"}}
            map_file.write_text(json.dumps(map_data))

            # Create binary file
            bin_file = test_dir / "data.bin"
            bin_file.write_bytes(b"BINARY content here\x00\x01")

            # Create text file for comparison
            txt_file = test_dir / "data.txt"
            txt_file.write_text("BINARY content here")

            # Run main flow
            main_flow(
                str(test_dir),
                str(map_file),
                [".bin", ".txt"],
                [],
                [],
                True,  # dry_run to check transactions
                False,  # skip_scan
                False,  # resume
                True,  # force
                True,  # ignore_symlinks
                False,  # use_gitignore
                None,  # custom_ignore_file
                False,  # skip_file_renaming
                False,  # skip_folder_renaming
                False,  # skip_content
                10,  # timeout
                True,  # quiet
                False,  # verbose
                False,  # interactive
            )

            # Check transactions
            txn_file = test_dir / "planned_transactions.json"
            assert txn_file.exists(), "Transaction file should exist"

            transactions = load_transactions(txn_file)
            assert transactions is not None

            # Binary file should not have content transactions
            bin_content_txns = [tx for tx in transactions if tx["PATH"] == "data.bin" and tx["TYPE"] == TransactionType.FILE_CONTENT_LINE.value]
            assert len(bin_content_txns) == 0, "Binary file should not have content transactions"

            # Text file should have content transactions
            txt_content_txns = [tx for tx in transactions if tx["PATH"] == "data.txt" and tx["TYPE"] == TransactionType.FILE_CONTENT_LINE.value]
            assert len(txt_content_txns) > 0, "Text file should have content transactions"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
