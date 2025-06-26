#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Final push to achieve 100% test coverage
# - Tests for all remaining uncovered lines
# - Focus on error paths and edge cases
#

"""
Final tests to achieve 100% coverage.
"""

import pytest
from pathlib import Path
import json
import sys
import os
import logging
import subprocess
from unittest.mock import patch, MagicMock, call, ANY
import time
import errno
import shutil
import tempfile


class TestPrefectIntegration:
    """Test Prefect integration and flow decorator."""

    def test_main_flow_with_prefect(self, tmp_path):
        """Test main_flow when run as a Prefect flow."""
        # Mock the flow decorator
        mock_flow_decorator = MagicMock()
        mock_flow_instance = MagicMock()
        mock_flow_decorator.return_value = lambda func: func

        with patch("mass_find_replace.mass_find_replace.flow", mock_flow_decorator):
            from mass_find_replace.mass_find_replace import main_flow

            mapping_file = tmp_path / "mapping.json"
            mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

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

            assert result[0] is True

    def test_subprocess_flush_handlers(self, capsys):
        """Test subprocess stdout flushing with logger handlers."""
        import mass_find_replace.mass_find_replace as mfr

        # Create a logger with a handler that has flush method
        mock_handler = MagicMock()
        mock_handler.flush = MagicMock()

        mock_logger = MagicMock()
        mock_logger.handlers = [mock_handler]

        # Test command that produces output
        with patch("mass_find_replace.mass_find_replace._get_logger", return_value=mock_logger):
            result = mfr._run_subprocess_command(["echo", "test output"], "Test", mock_logger)

        # Handler flush should be called
        mock_handler.flush.assert_called()

    def test_subprocess_without_flush(self, capsys):
        """Test subprocess when handler has no flush method."""
        import mass_find_replace.mass_find_replace as mfr

        # Create handler without flush method
        mock_handler = MagicMock()
        del mock_handler.flush  # Remove flush attribute

        mock_logger = MagicMock()
        mock_logger.handlers = [mock_handler]

        # Should handle gracefully
        with patch("mass_find_replace.mass_find_replace._get_logger", return_value=mock_logger):
            result = mfr._run_subprocess_command(["echo", "test"], "Test", mock_logger)
            assert result is True


class TestMainCLIEdgeCases:
    """Test main_cli edge cases."""

    def test_main_cli_exception_handling(self, capsys):
        """Test exception handling in main_cli."""
        test_args = ["mfr", ".", "--force"]

        with patch.object(sys, "argv", test_args):
            with patch("mass_find_replace.mass_find_replace.main_flow", side_effect=Exception("Unexpected error")):
                from mass_find_replace.mass_find_replace import main_cli

                result = main_cli()
                assert result == 1
                captured = capsys.readouterr()
                assert "An error occurred" in captured.out

    def test_main_cli_json_key_error(self, capsys, tmp_path):
        """Test missing REPLACEMENT_MAPPING key in JSON."""
        mapping_file = tmp_path / "invalid.json"
        mapping_file.write_text('{"wrong_key": {}}')
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file)]

        with patch.object(sys, "argv", test_args):
            from mass_find_replace.mass_find_replace import main_cli

            result = main_cli()
            assert result == 1
            captured = capsys.readouterr()
            assert "REPLACEMENT_MAPPING" in captured.out

    def test_main_cli_cyclic_mapping(self, capsys, tmp_path):
        """Test cyclic mapping detection."""
        mapping_file = tmp_path / "cyclic.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {"A": "B", "B": "A"}}')
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file), "--force"]

        with patch.object(sys, "argv", test_args):
            from mass_find_replace.mass_find_replace import main_cli

            result = main_cli()
            assert result == 1
            captured = capsys.readouterr()
            assert "cyclic" in captured.out.lower()

    def test_main_cli_user_confirmation_no(self, tmp_path, monkeypatch):
        """Test user declining confirmation."""
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file)]

        # User says no
        monkeypatch.setattr("builtins.input", lambda _: "n")

        with patch.object(sys, "argv", test_args):
            from mass_find_replace.mass_find_replace import main_cli

            result = main_cli()
            assert result == 0  # Exits gracefully

    def test_main_cli_timeout_zero(self, tmp_path):
        """Test with timeout set to 0 (infinite)."""
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file), "--timeout", "0", "--force"]

        with patch.object(sys, "argv", test_args):
            with patch("mass_find_replace.mass_find_replace.main_flow") as mock_flow:
                mock_flow.return_value = (True, 0, 0, 0)
                from mass_find_replace.mass_find_replace import main_cli

                result = main_cli()

                # Check timeout was set to 0
                call_args = mock_flow.call_args[1]
                assert call_args["timeout_minutes"] == 0


class TestCheckExistingTransactions:
    """Test _check_existing_transactions function."""

    def test_all_transactions_completed(self, tmp_path):
        """Test when all transactions are completed."""
        import mass_find_replace.mass_find_replace as mfr
        from mass_find_replace.file_system_operations import TransactionStatus

        logger = MagicMock()

        # Create transaction file with all completed
        txn_file = tmp_path / "planned_transactions.json"
        transactions = [
            {"ID": "1", "STATUS": TransactionStatus.COMPLETED.value},
            {"ID": "2", "STATUS": TransactionStatus.COMPLETED.value},
        ]
        txn_file.write_text(json.dumps(transactions))

        has_existing, progress = mfr._check_existing_transactions(tmp_path, logger)
        assert has_existing is False  # All done
        assert progress == 100

    def test_no_transactions(self, tmp_path):
        """Test with empty transaction list."""
        import mass_find_replace.mass_find_replace as mfr

        logger = MagicMock()

        # Empty transaction file
        txn_file = tmp_path / "planned_transactions.json"
        txn_file.write_text("[]")

        has_existing, progress = mfr._check_existing_transactions(tmp_path, logger)
        assert has_existing is False
        assert progress == 0


class TestTransactionProcessing:
    """Test transaction processing edge cases."""

    def test_symlink_rename_dry_run(self, tmp_path):
        """Test symlink rename in dry run mode."""
        from mass_find_replace.file_system_operations import execute_all_transactions, TransactionType, TransactionStatus

        if os.name == "nt":
            pytest.skip("Symlinks not supported on Windows")

        target = tmp_path / "target.txt"
        target.write_text("content")
        old_link = tmp_path / "old_link"
        old_link.symlink_to(target)

        transaction = {"ID": "1", "TYPE": TransactionType.SYMLINK_RENAME.value, "OLD_PATH": str(old_link), "NEW_PATH": str(tmp_path / "new_link"), "STATUS": TransactionStatus.PENDING.value}

        logger = MagicMock()

        stats = execute_all_transactions(
            [transaction],
            {},
            tmp_path,
            logger,
            dry_run=True,  # Dry run
            interactive=False,
            process_symlink_names=True,
            timeout_minutes=30,
        )

        assert stats["completed"] == 1
        assert old_link.exists()  # Should not be renamed in dry run

    def test_file_rename_permission_error(self, tmp_path):
        """Test file rename with permission error."""
        from mass_find_replace.file_system_operations import execute_all_transactions, TransactionType, TransactionStatus

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        transaction = {"ID": "1", "TYPE": TransactionType.FILE_RENAME.value, "OLD_PATH": str(test_file), "NEW_PATH": str(tmp_path / "new.txt"), "STATUS": TransactionStatus.PENDING.value}

        logger = MagicMock()

        # Mock to raise permission error
        with patch("pathlib.Path.rename", side_effect=PermissionError("Access denied")):
            stats = execute_all_transactions([transaction], {}, tmp_path, logger, dry_run=False, interactive=False, process_symlink_names=False, timeout_minutes=30)
            assert stats["failed"] == 1

    def test_content_change_with_no_changes(self, tmp_path):
        """Test content change when no actual changes occur."""
        from mass_find_replace.file_system_operations import execute_all_transactions, TransactionType, TransactionStatus

        test_file = tmp_path / "test.txt"
        test_file.write_text("content without matches")

        transaction = {
            "ID": "1",
            "TYPE": TransactionType.FILE_CONTENT_CHANGE.value,
            "FILE_PATH": str(test_file),
            "STATUS": TransactionStatus.PENDING.value,
            "EXPECTED_CHANGES": 1,  # Expects changes but none will occur
        }

        logger = MagicMock()

        stats = execute_all_transactions(
            [transaction],
            {"old": "new"},  # Pattern not in file
            tmp_path,
            logger,
            dry_run=False,
            interactive=False,
            process_symlink_names=False,
            timeout_minutes=30,
        )

        # Should still be marked as completed
        assert stats["completed"] == 1


class TestLoggerFunctions:
    """Test logger-related functions."""

    def test_log_message_functions(self, capsys):
        """Test all log message functions."""
        # Test file_system_operations log function
        import mass_find_replace.file_system_operations as fs_ops

        # Test all log levels
        logger = MagicMock()
        fs_ops._log_fs_op_message("DEBUG", "Debug message", logger)
        logger.debug.assert_called_with("Debug message")

        fs_ops._log_fs_op_message("INFO", "Info message", logger)
        logger.info.assert_called_with("Info message")

        fs_ops._log_fs_op_message("WARNING", "Warning message", logger)
        logger.warning.assert_called_with("Warning message")

        fs_ops._log_fs_op_message("ERROR", "Error message", logger)
        logger.error.assert_called_with("Error message")

        # Test with None logger
        fs_ops._log_fs_op_message("INFO", "Console message", None)
        captured = capsys.readouterr()
        assert "Console message" in captured.out

    def test_replace_logic_logging(self, capsys):
        """Test replace_logic logging."""
        import mass_find_replace.replace_logic as rl

        # Test with exception in logger
        logger = MagicMock()
        logger.debug.side_effect = Exception("Logger failed")

        # Should handle exception gracefully
        rl._log_message("DEBUG", "Test message", logger)
        captured = capsys.readouterr()
        assert "Test message" in captured.out


class TestStringProcessing:
    """Test string processing functions."""

    def test_canonicalize_edge_cases(self):
        """Test string canonicalization edge cases."""
        import mass_find_replace.file_system_operations as fs_ops

        # Empty string
        assert fs_ops._canonicalize_for_matching("") == ""

        # Only control characters
        assert fs_ops._canonicalize_for_matching("\x00\x01\x02") == ""

        # Mixed content
        text = "Café\x00naïve\tZürich\n"
        result = fs_ops._canonicalize_for_matching(text)
        assert "\x00" not in result
        assert "\t" not in result
        assert "\n" not in result

    def test_strip_functions(self):
        """Test strip functions individually."""
        import mass_find_replace.file_system_operations as fs_ops

        # Test strip_control_characters
        assert fs_ops._strip_control_characters("Hello\x00World") == "HelloWorld"
        assert fs_ops._strip_control_characters("\x01\x02\x03") == ""

        # Test strip_diacritics
        assert fs_ops._strip_diacritics("naïve") == "naive"
        assert fs_ops._strip_diacritics("Zürich") == "Zurich"


class TestEncodingDetection:
    """Test encoding detection edge cases."""

    def test_encoding_detection_edge_cases(self, tmp_path):
        """Test various encoding scenarios."""
        from mass_find_replace.file_system_operations import get_file_encoding

        # Empty file
        empty = tmp_path / "empty.txt"
        empty.touch()
        assert get_file_encoding(empty) == "utf-8"

        # Binary file that looks like text
        mixed = tmp_path / "mixed.bin"
        mixed.write_bytes(b"Text\x00Binary\xff\xfe")
        encoding = get_file_encoding(mixed)
        assert encoding is not None

        # Very large file (should only read sample)
        large = tmp_path / "large.txt"
        large.write_text("A" * 1000000)  # 1MB of 'A'
        encoding = get_file_encoding(large)
        assert encoding == "utf-8"


class TestRTFProcessing:
    """Test RTF file processing."""

    def test_rtf_to_text_edge_cases(self):
        """Test RTF conversion edge cases."""
        from mass_find_replace.file_system_operations import rtf_to_text

        # Empty RTF
        assert rtf_to_text("") == ""

        # Invalid RTF
        assert rtf_to_text("Not RTF content") == "Not RTF content"

        # Minimal RTF
        rtf = r"{\rtf1 Hello}"
        result = rtf_to_text(rtf)
        assert "Hello" in result

        # RTF with special chars
        rtf = r"{\rtf1 Text with \'e9 accent}"
        result = rtf_to_text(rtf)
        assert "Text with" in result


class TestFileOperationHelpers:
    """Test file operation helper functions."""

    def test_is_running_in_ci(self):
        """Test CI environment detection."""
        import mass_find_replace.file_system_operations as fs_ops

        # Save original env
        original_ci = os.environ.get("CI")
        original_gh = os.environ.get("GITHUB_ACTIONS")

        try:
            # Test with CI env var
            os.environ["CI"] = "true"
            assert fs_ops._is_running_in_ci() is True

            # Test with GITHUB_ACTIONS
            del os.environ["CI"]
            os.environ["GITHUB_ACTIONS"] = "true"
            assert fs_ops._is_running_in_ci() is True

            # Test with neither
            del os.environ["GITHUB_ACTIONS"]
            assert fs_ops._is_running_in_ci() is False

        finally:
            # Restore original env
            if original_ci:
                os.environ["CI"] = original_ci
            elif "CI" in os.environ:
                del os.environ["CI"]

            if original_gh:
                os.environ["GITHUB_ACTIONS"] = original_gh
            elif "GITHUB_ACTIONS" in os.environ:
                del os.environ["GITHUB_ACTIONS"]

    def test_is_running_in_test(self):
        """Test test environment detection."""
        import mass_find_replace.file_system_operations as fs_ops

        # We're running in pytest, so this should be True
        assert fs_ops._is_running_in_test() is True

    def test_convert_to_relative_display_path(self, tmp_path):
        """Test path conversion to relative display."""
        import mass_find_replace.file_system_operations as fs_ops

        # Test various path scenarios
        file_path = tmp_path / "subdir" / "file.txt"
        result = fs_ops._convert_to_relative_display_path(file_path, tmp_path)
        assert result == "subdir/file.txt"

        # Same directory
        file_path = tmp_path / "file.txt"
        result = fs_ops._convert_to_relative_display_path(file_path, tmp_path)
        assert result == "file.txt"

        # Already relative
        result = fs_ops._convert_to_relative_display_path(Path("relative/path.txt"), tmp_path)
        assert result == "relative/path.txt"


class TestScanEdgeCases:
    """Test edge cases in directory scanning."""

    def test_scan_with_permission_error(self, tmp_path):
        """Test scanning when encountering permission errors."""
        from mass_find_replace.file_system_operations import scan_directory_for_occurrences

        # Create a directory we can't read
        restricted_dir = tmp_path / "restricted"
        restricted_dir.mkdir()

        mapping = {"old": "new"}
        logger = MagicMock()

        # Mock os.walk to raise permission error
        def mock_walk(path):
            if "restricted" in str(path):
                raise PermissionError("Access denied")
            return []

        with patch("os.walk", mock_walk):
            transactions = scan_directory_for_occurrences(directory=tmp_path, extensions=None, exclude_dirs=[], exclude_files=[], mapping=mapping, no_gitignore=True, logger=logger, skip_file_renaming=False, skip_folder_renaming=False, skip_content=False, process_symlink_names=False, ignore_file=None)

            # Should handle error gracefully
            logger.error.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
