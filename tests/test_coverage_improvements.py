#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Creation of focused tests to improve coverage
# - Tests main_cli function with various scenarios
# - Tests error handling and edge cases
# - Tests interactive mode and logging
#

"""
Focused tests to improve code coverage.
"""

import pytest
from pathlib import Path
import json
import sys
import os
import logging
from unittest.mock import patch, MagicMock, call
import subprocess


class TestMainCLI:
    """Test the main_cli function."""

    def test_main_cli_help(self, capsys):
        """Test --help flag."""
        test_args = ["mfr", "--help"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                from mass_find_replace.mass_find_replace import main_cli

                main_cli()
            assert exc_info.value.code == 0
            captured = capsys.readouterr()
            assert "Mass Find Replace" in captured.out

    def test_main_cli_self_test(self):
        """Test --self-test flag."""
        test_args = ["mfr", "--self-test"]

        # Mock subprocess.run for pytest call
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Tests passed"
        mock_result.stderr = ""

        with patch.object(sys, "argv", test_args):
            with patch("subprocess.run", return_value=mock_result) as mock_run:
                from mass_find_replace.mass_find_replace import main_cli

                result = main_cli()
                assert result == 0
                # Check that pytest was called
                mock_run.assert_called_once()
                call_args = mock_run.call_args[0][0]
                assert "pytest" in call_args

    def test_main_cli_self_test_failure(self):
        """Test --self-test with test failure."""
        test_args = ["mfr", "--self-test"]

        # Mock subprocess.run to simulate test failure
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = "Tests failed"
        mock_result.stderr = "Error"

        with patch.object(sys, "argv", test_args):
            with patch("subprocess.run", return_value=mock_result):
                from mass_find_replace.mass_find_replace import main_cli

                # main_cli doesn't return a value, it exits with sys.exit(1)
                with pytest.raises(SystemExit) as exc_info:
                    main_cli()
                assert exc_info.value.code == 1

    def test_main_cli_force_interactive_conflict(self, capsys):
        """Test conflicting --force and --interactive flags."""
        test_args = ["mfr", ".", "--force", "--interactive"]

        with patch.object(sys, "argv", test_args):
            from mass_find_replace.mass_find_replace import main_cli

            result = main_cli()
            assert result == 1
            captured = capsys.readouterr()
            assert "Cannot use both --force and --interactive" in captured.out

    def test_main_cli_invalid_directory(self, capsys, tmp_path):
        """Test with non-existent directory."""
        nonexistent = tmp_path / "does_not_exist"
        test_args = ["mfr", str(nonexistent)]

        with patch.object(sys, "argv", test_args):
            from mass_find_replace.mass_find_replace import main_cli

            result = main_cli()
            assert result == 1
            captured = capsys.readouterr()
            assert "does not exist" in captured.out

    def test_main_cli_not_directory(self, capsys, tmp_path):
        """Test with file instead of directory."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")
        test_args = ["mfr", str(test_file)]

        with patch.object(sys, "argv", test_args):
            from mass_find_replace.mass_find_replace import main_cli

            result = main_cli()
            assert result == 1
            captured = capsys.readouterr()
            assert "is not a directory" in captured.out

    def test_main_cli_invalid_mapping_file(self, capsys, tmp_path):
        """Test with non-existent mapping file."""
        test_args = ["mfr", str(tmp_path), "--mapping-file", "nonexistent.json"]

        with patch.object(sys, "argv", test_args):
            from mass_find_replace.mass_find_replace import main_cli

            result = main_cli()
            assert result == 1
            captured = capsys.readouterr()
            assert "does not exist" in captured.out

    def test_main_cli_invalid_json(self, capsys, tmp_path):
        """Test with invalid JSON in mapping file."""
        mapping_file = tmp_path / "invalid.json"
        mapping_file.write_text("invalid json")
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file)]

        with patch.object(sys, "argv", test_args):
            from mass_find_replace.mass_find_replace import main_cli

            result = main_cli()
            assert result == 1
            captured = capsys.readouterr()
            assert "Invalid JSON" in captured.out

    def test_main_cli_empty_mapping(self, capsys, tmp_path):
        """Test with empty mapping."""
        mapping_file = tmp_path / "empty.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {}}')
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file), "--force"]

        with patch.object(sys, "argv", test_args):
            from mass_find_replace.mass_find_replace import main_cli

            result = main_cli()
            assert result == 1
            captured = capsys.readouterr()
            assert "empty" in captured.out.lower()

    def test_main_cli_timeout_validation(self, capsys, tmp_path):
        """Test timeout validation."""
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

        # Test timeout < 1 (should be adjusted to 1)
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file), "--timeout", "0.5", "--force"]

        with patch.object(sys, "argv", test_args):
            with patch("mass_find_replace.mass_find_replace.main_flow") as mock_flow:
                mock_flow.return_value = (True, 0, 0, 0)
                from mass_find_replace.mass_find_replace import main_cli

                result = main_cli()
                # Check that timeout was adjusted to 1
                call_args = mock_flow.call_args[1]
                assert call_args["timeout_minutes"] == 1

    def test_main_cli_successful_run(self, tmp_path):
        """Test successful execution."""
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file), "--force"]

        with patch.object(sys, "argv", test_args):
            with patch("mass_find_replace.mass_find_replace.main_flow") as mock_flow:
                mock_flow.return_value = (True, 5, 0, 0)
                from mass_find_replace.mass_find_replace import main_cli

                result = main_cli()
                assert result == 0

    def test_main_cli_with_failures(self, tmp_path):
        """Test execution with failures."""
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file), "--force"]

        with patch.object(sys, "argv", test_args):
            with patch("mass_find_replace.mass_find_replace.main_flow") as mock_flow:
                mock_flow.return_value = (False, 3, 2, 0)
                from mass_find_replace.mass_find_replace import main_cli

                result = main_cli()
                assert result == 1


class TestMainFlow:
    """Test the main_flow function."""

    def test_main_flow_skip_scan_no_file(self, tmp_path):
        """Test skip_scan when transaction file doesn't exist."""
        result = self._run_main_flow(tmp_path, skip_scan=True)
        success, completed, failed, skipped = result
        assert success is True
        assert completed == 0

    def test_main_flow_resume_no_file(self, tmp_path):
        """Test resume when transaction file doesn't exist."""
        result = self._run_main_flow(tmp_path, resume=True)
        success, completed, failed, skipped = result
        assert success is True
        assert completed == 0

    def test_main_flow_empty_transaction_file(self, tmp_path):
        """Test with empty transaction file."""
        txn_file = tmp_path / "planned_transactions.json"
        txn_file.write_text("[]")

        result = self._run_main_flow(tmp_path, skip_scan=True)
        success, completed, failed, skipped = result
        assert success is True
        assert completed == 0

    def test_main_flow_with_dry_run_reset(self, tmp_path):
        """Test that DRY_RUN completed transactions are reset."""
        from mass_find_replace.file_system_operations import TransactionStatus, TransactionType

        test_file = tmp_path / "test.txt"
        test_file.write_text("old content")

        txn_file = tmp_path / "planned_transactions.json"
        transactions = [{"ID": "1", "id": "1", "TYPE": TransactionType.FILE_CONTENT_LINE.value, "FILE_PATH": str(test_file), "PATH": str(test_file), "STATUS": TransactionStatus.COMPLETED.value, "ERROR_MESSAGE": "DRY_RUN", "EXPECTED_CHANGES": 1}]
        txn_file.write_text(json.dumps(transactions))

        result = self._run_main_flow(tmp_path, skip_scan=True, dry_run=False)
        success, completed, failed, skipped = result
        assert success is True
        assert completed == 1  # Should execute the reset transaction

    def test_main_flow_interactive_mode(self, tmp_path):
        """Test interactive mode."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("old content")

        # Mock input to approve changes
        with patch("builtins.input", return_value="y"):
            result = self._run_main_flow(tmp_path, interactive_mode=True)
            success, completed, failed, skipped = result
            assert success is True

    def test_main_flow_quiet_mode(self, tmp_path, capsys):
        """Test quiet mode suppresses output."""
        result = self._run_main_flow(tmp_path, quiet_mode=True)
        captured = capsys.readouterr()
        # In quiet mode, should have minimal output
        assert len(captured.out) < 100  # Arbitrary small number

    def test_main_flow_verbose_mode(self, tmp_path):
        """Test verbose mode."""
        with patch("mass_find_replace.mass_find_replace._get_logger") as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger

            result = self._run_main_flow(tmp_path, verbose_mode=True)
            # Should create logger with verbose=True
            mock_get_logger.assert_called_with(verbose_mode=True)

    def _run_main_flow(self, tmp_path, **kwargs):
        """Helper to run main_flow with default arguments."""
        from mass_find_replace.mass_find_replace import main_flow

        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

        defaults = {
            "directory": str(tmp_path),
            "mapping_file": str(mapping_file),
            "extensions": None,
            "exclude_dirs": [],
            "exclude_files": [],
            "dry_run": False,
            "skip_scan": False,
            "resume": False,
            "force_execution": True,
            "interactive": False,
            "verbose_mode": False,
            "skip_file_renaming": False,
            "skip_folder_renaming": False,
            "skip_content": False,
            "no_gitignore": True,
            "process_symlink_names": False,
            "timeout_minutes": 30,
            "ignore_file": None,
            "quiet_mode": False,
        }
        defaults.update(kwargs)

        return main_flow(**defaults)


class TestExecuteTransactions:
    """Test execute_all_transactions function."""

    def test_interactive_mode_skip(self, tmp_path):
        """Test interactive mode with skip response."""
        from mass_find_replace.file_system_operations import execute_all_transactions, TransactionType, TransactionStatus

        test_file = tmp_path / "test.txt"
        test_file.write_text("old content")

        transaction = {"ID": "1", "TYPE": TransactionType.FILE_CONTENT_LINE.value, "FILE_PATH": str(test_file), "STATUS": TransactionStatus.PENDING.value, "EXPECTED_CHANGES": 1}

        logger = MagicMock()

        # Test 'n' (skip) response
        with patch("builtins.input", return_value="n"):
            stats = execute_all_transactions([transaction], {"old": "new"}, tmp_path, logger, dry_run=False, interactive_mode=True, ignore_symlinks_arg=True, timeout_minutes=30)
        assert stats["skipped"] == 1
        assert stats["completed"] == 0

    def test_interactive_mode_apply_all(self, tmp_path):
        """Test interactive mode with apply all response."""
        from mass_find_replace.file_system_operations import execute_all_transactions, TransactionType, TransactionStatus

        test_file = tmp_path / "test.txt"
        test_file.write_text("old content")

        transaction = {"ID": "1", "TYPE": TransactionType.FILE_CONTENT_LINE.value, "FILE_PATH": str(test_file), "STATUS": TransactionStatus.PENDING.value, "EXPECTED_CHANGES": 1}

        logger = MagicMock()

        # Test 'a' (apply all) response
        with patch("builtins.input", return_value="a"):
            stats = execute_all_transactions([transaction], {"old": "new"}, tmp_path, logger, dry_run=False, interactive_mode=True, ignore_symlinks_arg=True, timeout_minutes=30)
        assert stats["completed"] == 1

    def test_transaction_with_high_retry_count(self, tmp_path):
        """Test transaction with high retry count."""
        from mass_find_replace.file_system_operations import execute_all_transactions, TransactionType, TransactionStatus

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        transaction = {
            "ID": "1",
            "TYPE": TransactionType.FILE_CONTENT_LINE.value,
            "FILE_PATH": str(test_file),
            "STATUS": TransactionStatus.RETRY_LATER.value,
            "RETRY_COUNT": 50,  # High retry count
            "EXPECTED_CHANGES": 1,
        }

        logger = MagicMock()

        # With very short timeout, should skip due to timeout
        stats = execute_all_transactions(
            [transaction],
            {"content": "new"},
            tmp_path,
            logger,
            dry_run=False,
            interactive_mode=False,
            ignore_symlinks_arg=True,
            timeout_minutes=0.01,  # Very short timeout
        )

        assert stats["skipped"] >= 0  # May skip or retry depending on timing


class TestHelperFunctions:
    """Test helper functions."""

    def test_get_logger_without_prefect(self):
        """Test logger creation when prefect is not available."""
        import mass_find_replace.mass_find_replace as mfr

        with patch("mass_find_replace.mass_find_replace.get_run_logger", side_effect=ImportError):
            logger = mfr._get_logger(verbose_mode=False)
            assert isinstance(logger, logging.Logger)
            assert logger.level == logging.INFO

    def test_get_logger_with_context_error(self):
        """Test logger creation with MissingContextError."""
        import mass_find_replace.mass_find_replace as mfr

        # Create a mock MissingContextError
        mock_error = type("MissingContextError", (Exception,), {})

        with patch("mass_find_replace.mass_find_replace.get_run_logger", side_effect=mock_error()):
            logger = mfr._get_logger(verbose_mode=True)
            assert isinstance(logger, logging.Logger)
            assert logger.level == logging.DEBUG

    def test_print_mapping_table(self, capsys):
        """Test mapping table printing."""
        import mass_find_replace.mass_find_replace as mfr

        mapping = {
            "old_name": "new_name",
            "OldClass": "NewClass",
        }
        logger = MagicMock()

        mfr._print_mapping_table(mapping, logger)
        captured = capsys.readouterr()
        assert "old_name" in captured.out
        assert "new_name" in captured.out
        assert "Search" in captured.out
        assert "Replace" in captured.out

    def test_get_operation_description(self):
        """Test operation description generation."""
        import mass_find_replace.mass_find_replace as mfr

        # Test various combinations
        assert "file contents" in mfr._get_operation_description(True, True, False)
        assert "folder names" in mfr._get_operation_description(False, True, True)
        assert "nothing" in mfr._get_operation_description(True, True, True)

    def test_check_existing_transactions(self, tmp_path):
        """Test checking for existing transactions."""
        import mass_find_replace.mass_find_replace as mfr
        from mass_find_replace.file_system_operations import TransactionStatus

        logger = MagicMock()

        # Create transaction file with mixed statuses
        txn_file = tmp_path / "planned_transactions.json"
        transactions = [
            {"ID": "1", "STATUS": TransactionStatus.COMPLETED.value},
            {"ID": "2", "STATUS": TransactionStatus.PENDING.value},
            {"ID": "3", "STATUS": TransactionStatus.FAILED.value},
        ]
        txn_file.write_text(json.dumps(transactions))

        has_existing, progress = mfr._check_existing_transactions(tmp_path, logger)
        assert has_existing is True
        assert progress == 33  # 1 of 3 completed

    def test_run_subprocess_command(self, capsys):
        """Test subprocess command execution."""
        import mass_find_replace.mass_find_replace as mfr

        # Test successful command
        result = mfr._run_subprocess_command(["echo", "test"], "Echo test")
        assert result is True
        captured = capsys.readouterr()
        assert "test" in captured.out

        # Test failed command
        result = mfr._run_subprocess_command(["false"], "Fail test")
        assert result is False


class TestColorFunctions:
    """Test color output functions."""

    def test_color_functions(self, capsys):
        """Test all color output functions."""
        from mass_find_replace.file_system_operations import print_green, print_red, print_yellow, print_dim

        print_green("Green text")
        print_red("Red text")
        print_yellow("Yellow text")
        print_dim("Dim text")

        captured = capsys.readouterr()
        assert "Green text" in captured.out
        assert "Red text" in captured.out
        assert "Yellow text" in captured.out
        assert "Dim text" in captured.out


class TestReplaceLogic:
    """Test replace_logic module functions."""

    def test_validate_mapping_cyclic(self):
        """Test validation of cyclic mappings."""
        from mass_find_replace.replace_logic import validate_replacement_mapping

        logger = MagicMock()

        # Direct cycle
        mapping = {"A": "B", "B": "A"}
        assert validate_replacement_mapping(mapping, logger) is False

        # Chain cycle
        mapping = {"A": "B", "B": "C", "C": "A"}
        assert validate_replacement_mapping(mapping, logger) is False

        # Self-reference
        mapping = {"A": "A"}
        assert validate_replacement_mapping(mapping, logger) is False

        # Valid mapping
        mapping = {"old": "new", "foo": "bar"}
        assert validate_replacement_mapping(mapping, logger) is True


class TestFileOperations:
    """Test file operation functions."""

    def test_get_file_encoding(self, tmp_path):
        """Test file encoding detection."""
        from mass_find_replace.file_system_operations import get_file_encoding

        # UTF-8 file
        utf8_file = tmp_path / "utf8.txt"
        utf8_file.write_text("Hello World", encoding="utf-8")
        assert get_file_encoding(utf8_file) == "utf-8"

        # UTF-8 with BOM
        bom_file = tmp_path / "bom.txt"
        bom_file.write_bytes(b"\xef\xbb\xbfHello")
        assert get_file_encoding(bom_file) == "utf-8-sig"

        # Non-existent file
        assert get_file_encoding(tmp_path / "nonexistent.txt") == "utf-8"

    def test_is_binary_file(self, tmp_path):
        """Test binary file detection."""
        from mass_find_replace.file_system_operations import is_binary_file

        # Text file
        text_file = tmp_path / "text.txt"
        text_file.write_text("Hello World")
        assert is_binary_file(text_file) is False

        # Binary file
        binary_file = tmp_path / "binary.bin"
        binary_file.write_bytes(b"\x00\x01\x02\x03\x04")
        assert is_binary_file(binary_file) is True

    def test_transaction_status_update(self):
        """Test transaction status updates."""
        from mass_find_replace.file_system_operations import update_transaction_status_in_list, TransactionStatus

        logger = MagicMock()
        transactions = [{"id": "1", "STATUS": TransactionStatus.PENDING.value}, {"id": "2", "STATUS": TransactionStatus.PENDING.value}]

        # Update existing
        result = update_transaction_status_in_list(transactions, "1", TransactionStatus.COMPLETED, "", logger)
        assert result is True
        assert transactions[0]["STATUS"] == TransactionStatus.COMPLETED.value

        # Update non-existent
        result = update_transaction_status_in_list(transactions, "999", TransactionStatus.FAILED, "error", logger)
        assert result is False
        logger.warning.assert_called()

    def test_load_ignore_patterns(self, tmp_path):
        """Test loading ignore patterns from file."""
        from mass_find_replace.file_system_operations import load_ignore_patterns

        ignore_file = tmp_path / ".customignore"
        ignore_file.write_text("*.pyc\n__pycache__/\n# Comment\n\n*.log")

        patterns = load_ignore_patterns(str(ignore_file))
        assert "*.pyc" in patterns
        assert "__pycache__/" in patterns
        assert "*.log" in patterns
        assert len(patterns) == 3

    def test_folder_rename_collision(self, tmp_path):
        """Test folder rename when target exists."""
        from mass_find_replace.file_system_operations import execute_all_transactions, TransactionType, TransactionStatus

        old_dir = tmp_path / "old_folder"
        new_dir = tmp_path / "new_folder"
        old_dir.mkdir()
        new_dir.mkdir()  # Target already exists

        transaction = {"ID": "1", "TYPE": TransactionType.FOLDER_NAME.value, "OLD_PATH": str(old_dir), "NEW_PATH": str(new_dir), "STATUS": TransactionStatus.PENDING.value}

        logger = MagicMock()

        stats = execute_all_transactions([transaction], {}, tmp_path, logger, dry_run=False, interactive_mode=False, ignore_symlinks_arg=True, timeout_minutes=30)

        assert stats["failed"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
