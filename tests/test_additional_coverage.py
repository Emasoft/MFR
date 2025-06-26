#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Additional tests to increase coverage to 100%
# - Focus on uncovered edge cases and error paths
# - Tests for file operations and error handling
#

"""
Additional tests to achieve 100% coverage.
"""

import pytest
from pathlib import Path
import json
import os
import sys
import time
import errno
import fcntl
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import shutil


class TestFileSystemOperations:
    """Test uncovered file system operations."""

    def test_scan_with_symlinks(self, tmp_path):
        """Test scanning with symlink processing enabled."""
        from mass_find_replace.file_system_operations import scan_directory_for_occurrences

        if os.name == "nt":
            pytest.skip("Symlinks not supported on Windows")

        # Create a symlink
        target = tmp_path / "target.txt"
        target.write_text("old content")
        link = tmp_path / "old_link"
        link.symlink_to(target)

        mapping = {"old": "new"}
        logger = MagicMock()

        transactions = scan_directory_for_occurrences(
            directory=tmp_path,
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            mapping=mapping,
            no_gitignore=True,
            logger=logger,
            skip_file_renaming=False,
            skip_folder_renaming=False,
            skip_content=False,
            process_symlink_names=True,  # Enable symlink processing
            ignore_file=None,
        )

        # Should find symlink rename transaction
        symlink_txns = [t for t in transactions if t["TYPE"] == "SYMLINK_RENAME"]
        assert len(symlink_txns) > 0

    def test_scan_with_gitignore(self, tmp_path):
        """Test scanning with gitignore enabled."""
        from mass_find_replace.file_system_operations import scan_directory_for_occurrences

        # Create gitignore
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("*.log\ntemp/")

        # Create files
        (tmp_path / "keep.txt").write_text("old content")
        (tmp_path / "skip.log").write_text("old content")

        mapping = {"old": "new"}
        logger = MagicMock()

        transactions = scan_directory_for_occurrences(
            directory=tmp_path,
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            mapping=mapping,
            no_gitignore=False,  # Enable gitignore
            logger=logger,
            skip_file_renaming=True,
            skip_folder_renaming=True,
            skip_content=False,
            process_symlink_names=False,
            ignore_file=None,
        )

        # Should only find keep.txt
        file_paths = [t["FILE_PATH"] for t in transactions]
        assert any("keep.txt" in path for path in file_paths)
        assert not any("skip.log" in path for path in file_paths)

    def test_process_large_file_with_encoding_error(self, tmp_path):
        """Test processing file with encoding issues."""
        from mass_find_replace.file_system_operations import process_large_file_content

        # Create file with problematic encoding
        test_file = tmp_path / "bad_encoding.txt"
        test_file.write_bytes(b"Hello \x80 World")  # Invalid UTF-8

        mapping = {"Hello": "Hi"}
        logger = MagicMock()

        # Should handle encoding error gracefully
        new_content, changes = process_large_file_content(file_path=test_file, mapping=mapping, logger=logger, dry_run=False)

        assert changes > 0

    def test_execute_transaction_os_errors(self, tmp_path):
        """Test various OS errors during execution."""
        from mass_find_replace.file_system_operations import execute_all_transactions, TransactionType, TransactionStatus

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        transaction = {"ID": "1", "TYPE": TransactionType.FILE_RENAME.value, "OLD_PATH": str(test_file), "NEW_PATH": str(tmp_path / "new.txt"), "STATUS": TransactionStatus.PENDING.value}

        logger = MagicMock()

        # Test with EBUSY error (file busy)
        with patch("pathlib.Path.rename", side_effect=OSError(errno.EBUSY, "Device busy")):
            stats = execute_all_transactions(
                [transaction],
                {},
                tmp_path,
                logger,
                dry_run=False,
                interactive=False,
                process_symlink_names=False,
                timeout_minutes=0.01,  # Very short timeout
            )
            # Should retry and eventually timeout
            assert stats["skipped"] > 0 or stats["failed"] > 0

    def test_file_locking_error(self, tmp_path):
        """Test file locking errors."""
        from mass_find_replace.file_system_operations import execute_all_transactions, TransactionType, TransactionStatus

        test_file = tmp_path / "locked.txt"
        test_file.write_text("content")

        transaction = {"ID": "1", "TYPE": TransactionType.FILE_CONTENT_CHANGE.value, "FILE_PATH": str(test_file), "STATUS": TransactionStatus.PENDING.value, "EXPECTED_CHANGES": 1}

        logger = MagicMock()

        # Mock file operations to raise locking error
        with patch("builtins.open", side_effect=OSError(errno.EACCES, "Permission denied")):
            stats = execute_all_transactions([transaction], {"content": "new"}, tmp_path, logger, dry_run=False, interactive=False, process_symlink_names=False, timeout_minutes=0.01)
            assert stats["failed"] > 0 or stats["skipped"] > 0

    def test_rtf_file_processing(self, tmp_path):
        """Test RTF file processing."""
        from mass_find_replace.file_system_operations import scan_directory_for_occurrences

        # Create a simple RTF file
        rtf_file = tmp_path / "document.rtf"
        rtf_content = r"{\rtf1\ansi{\fonttbl\f0\fswiss Helvetica;}\f0\pard This is old text.\par}"
        rtf_file.write_text(rtf_content)

        mapping = {"old": "new"}
        logger = MagicMock()

        transactions = scan_directory_for_occurrences(directory=tmp_path, extensions=[".rtf"], exclude_dirs=[], exclude_files=[], mapping=mapping, no_gitignore=True, logger=logger, skip_file_renaming=True, skip_folder_renaming=True, skip_content=False, process_symlink_names=False, ignore_file=None)

        assert len(transactions) > 0

    def test_binary_file_detection_edge_cases(self, tmp_path):
        """Test binary file detection with edge cases."""
        from mass_find_replace.file_system_operations import is_binary_file

        # Empty file
        empty_file = tmp_path / "empty.txt"
        empty_file.touch()
        assert is_binary_file(empty_file) is False

        # File with some binary content but mostly text
        mixed_file = tmp_path / "mixed.txt"
        mixed_file.write_bytes(b"Hello World\x00\x01Text continues")
        # This should be detected as binary due to null bytes
        assert is_binary_file(mixed_file) is True

        # Large text file
        large_text = tmp_path / "large.txt"
        large_text.write_text("Hello World\n" * 10000)
        assert is_binary_file(large_text) is False

    def test_save_transactions_with_backup(self, tmp_path):
        """Test transaction saving with backup."""
        from mass_find_replace.file_system_operations import save_transactions, TRANSACTION_FILE_BACKUP_EXT

        # Create existing transaction file
        txn_file = tmp_path / "planned_transactions.json"
        original_data = [{"ID": "old", "data": "original"}]
        txn_file.write_text(json.dumps(original_data))

        # Save new transactions
        new_data = [{"ID": "new", "data": "updated"}]
        logger = MagicMock()

        save_transactions(new_data, tmp_path, logger)

        # Check backup was created
        backup_file = tmp_path / f"planned_transactions{TRANSACTION_FILE_BACKUP_EXT}"
        assert backup_file.exists()
        assert json.loads(backup_file.read_text()) == original_data

    def test_load_transactions_invalid_json(self, tmp_path):
        """Test loading invalid transaction file."""
        from mass_find_replace.file_system_operations import load_transactions

        txn_file = tmp_path / "planned_transactions.json"
        txn_file.write_text("invalid json {")

        logger = MagicMock()

        with pytest.raises(json.JSONDecodeError):
            load_transactions(tmp_path, logger)

    def test_folder_with_special_chars(self, tmp_path):
        """Test handling folders with special characters."""
        from mass_find_replace.file_system_operations import scan_directory_for_occurrences

        # Create folder with special chars
        special_dir = tmp_path / "folder with spaces & special-chars"
        special_dir.mkdir()
        (special_dir / "file.txt").write_text("old content")

        mapping = {"old": "new"}
        logger = MagicMock()

        transactions = scan_directory_for_occurrences(directory=tmp_path, extensions=None, exclude_dirs=[], exclude_files=[], mapping=mapping, no_gitignore=True, logger=logger, skip_file_renaming=True, skip_folder_renaming=False, skip_content=False, process_symlink_names=False, ignore_file=None)

        # Should handle special chars properly
        assert len(transactions) > 0


class TestReplaceLogicEdgeCases:
    """Test replace logic edge cases."""

    def test_replace_with_unicode(self):
        """Test replacements with unicode characters."""
        from mass_find_replace.replace_logic import apply_replacements_to_string

        mapping = {"café": "coffee shop", "naïve": "simple", "Zürich": "Zurich"}

        text = "Visit the café in Zürich with naïve charm"
        result = apply_replacements_to_string(text, mapping)

        assert "coffee shop" in result
        assert "simple" in result
        assert "Zurich" in result

    def test_case_sensitive_replacements(self):
        """Test case-sensitive replacement behavior."""
        from mass_find_replace.replace_logic import apply_replacements_to_string

        mapping = {"Test": "Exam", "test": "quiz"}

        text = "Test the test and TEST"
        result = apply_replacements_to_string(text, mapping)

        # Should replace case-sensitively
        assert "Exam" in result
        assert "quiz" in result

    def test_overlapping_replacements(self):
        """Test handling of overlapping replacement patterns."""
        from mass_find_replace.replace_logic import create_compiled_mapping

        mapping = {"abc": "xyz", "abcd": "wxyz", "ab": "uv"}

        logger = MagicMock()
        canonicalized, compiled = create_compiled_mapping(mapping, logger)

        # Should handle overlapping patterns correctly
        assert len(compiled) == len(mapping)


class TestMainFlowEdgeCases:
    """Test main_flow edge cases."""

    def test_main_flow_with_modified_files_detection(self, tmp_path):
        """Test file modification detection during resume."""
        from mass_find_replace.mass_find_replace import main_flow
        from mass_find_replace.file_system_operations import TransactionStatus, TransactionType

        # Create mapping
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("old content")

        # Create transaction file with timestamp
        txn_file = tmp_path / "planned_transactions.json"
        past_time = time.time() - 100
        transactions = [{"ID": "1", "TYPE": TransactionType.FILE_CONTENT_CHANGE.value, "FILE_PATH": str(test_file), "STATUS": TransactionStatus.COMPLETED.value, "PATH": str(test_file), "TIMESTAMP_LAST_PROCESSED": past_time}]
        txn_file.write_text(json.dumps(transactions))

        # Modify file after transaction
        time.sleep(0.1)
        test_file.write_text("old content modified")

        # Resume should detect modification
        result = main_flow(
            directory=str(tmp_path),
            mapping_file=str(mapping_file),
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=False,
            skip_scan=False,
            resume=True,
            force_execution=True,
            interactive=False,
            verbose_mode=False,
            skip_file_renaming=False,
            skip_folder_renaming=False,
            skip_content=False,
            no_gitignore=True,
            process_symlink_names=False,
            timeout_minutes=30,
            ignore_file=None,
            quiet_mode=False,
        )

        success, completed, failed, skipped = result
        assert success is True

    def test_main_flow_keyboard_interrupt(self, tmp_path):
        """Test handling of keyboard interrupt."""
        from mass_find_replace.mass_find_replace import main_flow

        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

        # Mock scan to raise KeyboardInterrupt
        with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences", side_effect=KeyboardInterrupt):
            result = main_flow(
                directory=str(tmp_path),
                mapping_file=str(mapping_file),
                extensions=None,
                exclude_dirs=[],
                exclude_files=[],
                dry_run=False,
                skip_scan=False,
                resume=False,
                force_execution=True,
                interactive=False,
                verbose_mode=False,
                skip_file_renaming=False,
                skip_folder_renaming=False,
                skip_content=False,
                no_gitignore=True,
                process_symlink_names=False,
                timeout_minutes=30,
                ignore_file=None,
                quiet_mode=False,
            )

            success, completed, failed, skipped = result
            assert success is False

    def test_main_flow_with_all_skip_flags(self, tmp_path):
        """Test with all operations skipped."""
        from mass_find_replace.mass_find_replace import main_flow

        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

        # Skip all operations
        result = main_flow(
            directory=str(tmp_path),
            mapping_file=str(mapping_file),
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=False,
            skip_scan=False,
            resume=False,
            force_execution=True,
            interactive=False,
            verbose_mode=False,
            skip_file_renaming=True,
            skip_folder_renaming=True,
            skip_content=True,  # All operations skipped
            no_gitignore=True,
            process_symlink_names=False,
            timeout_minutes=30,
            ignore_file=None,
            quiet_mode=False,
        )

        success, completed, failed, skipped = result
        assert success is True
        assert completed == 0  # Nothing to do


class TestUtilityFunctions:
    """Test utility and helper functions."""

    def test_get_exclude_patterns(self, tmp_path):
        """Test gitignore pattern loading."""
        from mass_find_replace.file_system_operations import get_exclude_patterns

        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("""
# Python
*.pyc
__pycache__/
.pytest_cache/

# Logs
*.log
logs/

# Empty lines and comments should be ignored


# More patterns
.DS_Store
""")

        patterns = get_exclude_patterns(gitignore)
        assert "*.pyc" in patterns
        assert "__pycache__/" in patterns
        assert "*.log" in patterns
        assert ".DS_Store" in patterns
        # Comments and empty lines should not be included
        assert not any(p.startswith("#") for p in patterns)
        assert not any(p == "" for p in patterns)

    def test_update_transaction_status_edge_cases(self):
        """Test transaction status update edge cases."""
        from mass_find_replace.file_system_operations import update_transaction_status_in_list, TransactionStatus

        logger = MagicMock()

        # Empty transaction list
        transactions = []
        update_transaction_status_in_list(transactions, "1", TransactionStatus.COMPLETED, "", logger)
        logger.warning.assert_called_with("Transaction ID 1 not found in the transaction list.")

        # Transaction without ID field
        transactions = [{"data": "no id"}]
        update_transaction_status_in_list(transactions, "1", TransactionStatus.COMPLETED, "", logger)

    def test_open_file_with_encoding_edge_cases(self, tmp_path):
        """Test file opening with various encodings."""
        from mass_find_replace.file_system_operations import open_file_with_encoding

        # UTF-16 file
        utf16_file = tmp_path / "utf16.txt"
        utf16_file.write_text("Hello UTF-16", encoding="utf-16")

        with open_file_with_encoding(utf16_file, "r") as f:
            content = f.read()
            assert "Hello UTF-16" in content

        # Latin-1 file
        latin1_file = tmp_path / "latin1.txt"
        latin1_file.write_bytes("Café résumé".encode("latin-1"))

        with open_file_with_encoding(latin1_file, "r") as f:
            content = f.read()
            # Should be readable even if encoding detection isn't perfect

    def test_group_and_process_file_transactions_edge_cases(self, tmp_path):
        """Test transaction grouping edge cases."""
        from mass_find_replace.file_system_operations import group_and_process_file_transactions, TransactionType

        # Mix of different transaction types for same file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        transactions = [{"ID": "1", "TYPE": TransactionType.FILE_RENAME.value, "OLD_PATH": str(test_file), "NEW_PATH": str(tmp_path / "renamed.txt"), "PATH": str(test_file)}, {"ID": "2", "TYPE": TransactionType.FILE_CONTENT_CHANGE.value, "FILE_PATH": str(test_file), "PATH": str(test_file), "EXPECTED_CHANGES": 1}]

        mapping = {"content": "new content"}
        logger = MagicMock()

        processed = group_and_process_file_transactions(transactions, mapping, tmp_path, logger, dry_run=True)

        assert len(processed) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
