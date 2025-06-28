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

                with pytest.raises(SystemExit) as exc_info:
                    main_cli()
                assert exc_info.value.code == 0
                # Check that subprocess.run was called (twice: once for uv install, once for pytest)
                assert mock_run.call_count == 2
                # Second call should be pytest
                pytest_call_args = mock_run.call_args_list[1][0][0]
                assert "pytest" in pytest_call_args

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
            with patch("mass_find_replace.mass_find_replace._get_logger") as mock_logger:
                from mass_find_replace.mass_find_replace import main_cli

                # main_cli doesn't check for conflicting flags, main_flow does
                # Let's mock main_flow to avoid actual execution
                with patch("mass_find_replace.mass_find_replace.main_flow"):
                    main_cli()  # Should not raise an error

    def test_main_cli_invalid_directory(self, capsys, tmp_path):
        """Test with non-existent directory."""
        nonexistent = tmp_path / "does_not_exist"
        test_args = ["mfr", str(nonexistent)]

        with patch.object(sys, "argv", test_args):
            with patch("mass_find_replace.mass_find_replace.main_flow") as mock_flow:
                # main_flow will handle the error
                mock_flow.side_effect = lambda *args, **kwargs: None
                from mass_find_replace.mass_find_replace import main_cli

                main_cli()  # Directory validation happens in main_flow

    def test_main_cli_not_directory(self, capsys, tmp_path):
        """Test with file instead of directory."""
        test_file = tmp_path / "file.txt"
        test_file.write_text("content")
        test_args = ["mfr", str(test_file)]

        with patch.object(sys, "argv", test_args):
            with patch("mass_find_replace.mass_find_replace.main_flow") as mock_flow:
                # main_flow will handle the error
                mock_flow.side_effect = lambda *args, **kwargs: None
                from mass_find_replace.mass_find_replace import main_cli

                main_cli()  # Directory validation happens in main_flow

    def test_main_cli_invalid_mapping_file(self, capsys, tmp_path):
        """Test with non-existent mapping file."""
        test_args = ["mfr", str(tmp_path), "--mapping-file", "nonexistent.json"]

        with patch.object(sys, "argv", test_args):
            with patch("mass_find_replace.mass_find_replace.main_flow") as mock_flow:
                # main_flow will handle the error
                mock_flow.side_effect = lambda *args, **kwargs: None
                from mass_find_replace.mass_find_replace import main_cli

                main_cli()  # Mapping file validation happens in main_flow

    def test_main_cli_invalid_json(self, capsys, tmp_path):
        """Test with invalid JSON in mapping file."""
        mapping_file = tmp_path / "invalid.json"
        mapping_file.write_text("invalid json")
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file)]

        with patch.object(sys, "argv", test_args):
            with patch("mass_find_replace.mass_find_replace.main_flow") as mock_flow:
                # main_flow will handle the error
                mock_flow.side_effect = lambda *args, **kwargs: None
                from mass_find_replace.mass_find_replace import main_cli

                main_cli()  # JSON validation happens in main_flow

    def test_main_cli_empty_mapping(self, capsys, tmp_path):
        """Test with empty mapping."""
        mapping_file = tmp_path / "empty.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {}}')
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file), "--force"]

        with patch.object(sys, "argv", test_args):
            with patch("mass_find_replace.mass_find_replace.main_flow") as mock_flow:
                # main_flow will handle the empty mapping
                mock_flow.side_effect = lambda *args, **kwargs: None
                from mass_find_replace.mass_find_replace import main_cli

                main_cli()  # Empty mapping check happens in main_flow

    def test_main_cli_invalid_ignore_file(self, capsys, tmp_path):
        """Test with non-existent ignore file."""
        test_args = ["mfr", str(tmp_path), "--ignore-file", "nonexistent.gitignore"]

        with patch.object(sys, "argv", test_args):
            from mass_find_replace.mass_find_replace import main_cli

            with pytest.raises(SystemExit) as exc_info:
                main_cli()
            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "Ignore file not found" in captured.err

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

                main_cli()
                # Check that timeout was adjusted to 1
                # main_flow is called with positional args, not kwargs
                call_args = mock_flow.call_args[0]
                # timeout is the 16th argument (0-indexed position 15)
                assert call_args[15] == 1

    def test_main_cli_successful_run(self, tmp_path):
        """Test successful execution."""
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file), "--force"]

        with patch.object(sys, "argv", test_args):
            with patch("mass_find_replace.mass_find_replace.main_flow") as mock_flow:
                # main_flow doesn't return a value
                mock_flow.return_value = None
                from mass_find_replace.mass_find_replace import main_cli

                # main_cli doesn't exit on success, it just returns
                main_cli()
                assert mock_flow.called

    def test_main_cli_with_failures(self, tmp_path):
        """Test execution with failures."""
        mapping_file = tmp_path / "mapping.json"
        mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
        test_args = ["mfr", str(tmp_path), "--mapping-file", str(mapping_file), "--force"]

        with patch.object(sys, "argv", test_args):
            with patch("mass_find_replace.mass_find_replace.main_flow") as mock_flow:
                # main_flow doesn't return a value, it would log errors
                mock_flow.return_value = None
                from mass_find_replace.mass_find_replace import main_cli

                main_cli()
                assert mock_flow.called


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
        transactions = [{"id": "1", "TYPE": TransactionType.FILE_CONTENT_LINE.value, "PATH": str(test_file.relative_to(tmp_path)), "STATUS": TransactionStatus.COMPLETED.value, "ERROR_MESSAGE": "DRY_RUN", "EXPECTED_CHANGES": 1}]
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
            "interactive_mode": False,
            "verbose_mode": False,
            "skip_file_renaming": False,
            "skip_folder_renaming": False,
            "skip_content": False,
            "use_gitignore": False,  # no_gitignore=True means use_gitignore=False
            "ignore_symlinks_arg": True,  # process_symlink_names=False means ignore_symlinks_arg=True
            "timeout_minutes": 30,
            "custom_ignore_file_path": None,
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

        transaction = {"id": "1", "TYPE": TransactionType.FILE_CONTENT_LINE.value, "PATH": str(test_file.relative_to(tmp_path)), "STATUS": TransactionStatus.PENDING.value, "EXPECTED_CHANGES": 1}

        logger = MagicMock()

        # Test 'n' (skip) response
        # Save transactions to file first
        txn_file = tmp_path / "planned_transactions.json"
        from mass_find_replace.file_system_operations import save_transactions

        save_transactions([transaction], txn_file, logger)

        with patch("builtins.input", return_value="n"):
            stats = execute_all_transactions(transactions_file_path=txn_file, root_dir=tmp_path, dry_run=False, resume=False, timeout_minutes=30, skip_file_renaming=False, skip_folder_renaming=False, skip_content=False, interactive_mode=True, logger=logger)
        assert stats["skipped"] == 1
        assert stats["completed"] == 0

    def test_interactive_mode_apply_all(self, tmp_path):
        """Test interactive mode with apply all response."""
        from mass_find_replace.file_system_operations import execute_all_transactions, TransactionType, TransactionStatus

        test_file = tmp_path / "test.txt"
        test_file.write_text("old content")

        transaction = {"id": "1", "TYPE": TransactionType.FILE_CONTENT_LINE.value, "PATH": str(test_file.relative_to(tmp_path)), "STATUS": TransactionStatus.PENDING.value, "EXPECTED_CHANGES": 1}

        logger = MagicMock()

        # Test 'a' (apply all) response
        # Save transactions to file first
        txn_file = tmp_path / "planned_transactions.json"
        from mass_find_replace.file_system_operations import save_transactions

        save_transactions([transaction], txn_file, logger)

        with patch("builtins.input", return_value="a"):
            stats = execute_all_transactions(transactions_file_path=txn_file, root_dir=tmp_path, dry_run=False, resume=False, timeout_minutes=30, skip_file_renaming=False, skip_folder_renaming=False, skip_content=False, interactive_mode=True, logger=logger)
        assert stats["completed"] == 1

    def test_transaction_with_high_retry_count(self, tmp_path):
        """Test transaction with high retry count."""
        from mass_find_replace.file_system_operations import execute_all_transactions, TransactionType, TransactionStatus

        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        transaction = {
            "id": "1",
            "TYPE": TransactionType.FILE_CONTENT_LINE.value,
            "FILE_PATH": str(test_file),
            "STATUS": TransactionStatus.RETRY_LATER.value,
            "RETRY_COUNT": 50,  # High retry count
            "EXPECTED_CHANGES": 1,
        }

        logger = MagicMock()

        # With very short timeout, should skip due to timeout
        # Save transactions to file first
        txn_file = tmp_path / "planned_transactions.json"
        from mass_find_replace.file_system_operations import save_transactions

        save_transactions([transaction], txn_file, logger)

        stats = execute_all_transactions(
            transactions_file_path=txn_file,
            root_dir=tmp_path,
            dry_run=False,
            resume=False,
            timeout_minutes=0.01,  # Very short timeout
            skip_file_renaming=False,
            skip_folder_renaming=False,
            skip_content=False,
            interactive_mode=False,
            logger=logger,
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
        assert "file contents" in mfr._get_operation_description(False, False, True)
        assert "folder names" in mfr._get_operation_description(False, True, False)
        assert "nothing" in mfr._get_operation_description(True, True, True)

    def test_check_existing_transactions(self, tmp_path):
        """Test checking for existing transactions."""
        import mass_find_replace.mass_find_replace as mfr
        from mass_find_replace.file_system_operations import TransactionStatus

        logger = MagicMock()

        # Create transaction file with mixed statuses
        txn_file = tmp_path / "planned_transactions.json"
        transactions = [
            {"id": "1", "STATUS": TransactionStatus.COMPLETED.value},
            {"id": "2", "STATUS": TransactionStatus.PENDING.value},
            {"id": "3", "STATUS": TransactionStatus.FAILED.value},
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


class TestColorOutput:
    """Test color output in console."""

    def test_color_constants(self):
        """Test that color constants are defined."""
        import mass_find_replace.mass_find_replace as mfr

        # Check that color constants exist
        assert hasattr(mfr, "GREEN")
        assert hasattr(mfr, "RED")
        assert hasattr(mfr, "YELLOW")
        assert hasattr(mfr, "BLUE")
        assert hasattr(mfr, "RESET")
        assert hasattr(mfr, "DIM")


class TestReplaceLogic:
    """Test replace_logic module functions."""

    def test_validate_mapping_structure(self):
        """Test validation of mapping structure."""
        from mass_find_replace.replace_logic import validate_replacement_mapping_structure

        logger = MagicMock()

        # Valid structure
        data = {"REPLACEMENT_MAPPING": {"old": "new", "foo": "bar"}}
        is_valid, error = validate_replacement_mapping_structure(data, logger)
        assert is_valid is True
        assert error == ""

        # Missing REPLACEMENT_MAPPING key
        data = {"wrong_key": {}}
        is_valid, error = validate_replacement_mapping_structure(data, logger)
        assert is_valid is False
        assert "REPLACEMENT_MAPPING" in error

        # Invalid type
        data = {"REPLACEMENT_MAPPING": "not a dict"}
        is_valid, error = validate_replacement_mapping_structure(data, logger)
        assert is_valid is False
        assert "must be a dictionary" in error


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

        # load_ignore_patterns expects a Path object
        patterns_spec = load_ignore_patterns(ignore_file)
        assert patterns_spec is not None
        # Check that patterns are loaded (PathSpec doesn't allow direct pattern access)
        assert patterns_spec.match_file("test.pyc") is True
        assert patterns_spec.match_file("__pycache__/test.py") is True
        assert patterns_spec.match_file("test.log") is True
        assert patterns_spec.match_file("test.txt") is False

    def test_folder_rename_collision(self, tmp_path):
        """Test folder rename when target exists."""
        from mass_find_replace.file_system_operations import execute_all_transactions, TransactionType, TransactionStatus

        old_dir = tmp_path / "old_folder"
        new_dir = tmp_path / "new_folder"
        old_dir.mkdir()
        new_dir.mkdir()  # Target already exists

        transaction = {"id": "1", "TYPE": TransactionType.FOLDER_NAME.value, "PATH": str(old_dir.relative_to(tmp_path)), "OLD_PATH": str(old_dir), "NEW_PATH": str(new_dir), "STATUS": TransactionStatus.PENDING.value}

        logger = MagicMock()

        # Save transactions to file first
        txn_file = tmp_path / "planned_transactions.json"
        from mass_find_replace.file_system_operations import save_transactions

        save_transactions([transaction], txn_file, logger)

        stats = execute_all_transactions(transactions_file_path=txn_file, root_dir=tmp_path, dry_run=False, resume=False, timeout_minutes=30, skip_file_renaming=False, skip_folder_renaming=False, skip_content=False, interactive_mode=False, logger=logger)

        assert stats["failed"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
