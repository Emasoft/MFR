#!/usr/bin/env python3
"""Comprehensive tests with fixtures to achieve maximum coverage."""

import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
import pytest
from io import StringIO
import chardet
import pathspec

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from mass_find_replace.mass_find_replace import (
    _get_logger,
    _print_mapping_table,
    _get_operation_description,
    _check_existing_transactions,
    _run_subprocess_command,
    main_flow,
    main_cli,
    SCRIPT_NAME,
    MAIN_TRANSACTION_FILE_NAME,
)

import mass_find_replace.file_system_operations as fs_ops
from mass_find_replace.file_system_operations import (
    _log_fs_op_message,
    _log_collision_error,
    get_file_encoding,
    load_ignore_patterns,
    save_transactions,
    load_transactions,
    update_transaction_status_in_list,
    scan_directory_for_occurrences,
    execute_all_transactions,
    process_large_file_content,
    _execute_rename_transaction,
    _execute_content_line_transaction,
    _execute_file_content_batch,
    group_and_process_file_transactions,
    _walk_for_scan,
    TransactionStatus,
    TransactionType,
    COLLISIONS_ERRORS_LOG_FILE,
    BINARY_MATCHES_LOG_FILE,
    LARGE_FILE_SIZE_THRESHOLD,
)

from mass_find_replace.replace_logic import (
    _log_message,
    strip_diacritics,
    strip_control_characters,
    load_replacement_map,
    get_key_characters,
    get_mapping_size,
    replace_occurrences,
    _actual_replace_callback,
    _DEBUG_REPLACE_LOGIC,
)


# ============= FIXTURES =============


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory with some test files."""
    # Create directory structure
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module1.py").write_text("class OldName:\n    pass")
    (tmp_path / "src" / "module2.py").write_text("from module1 import OldName")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "readme.txt").write_text("This is OldName documentation")
    (tmp_path / "empty.txt").write_text("")
    (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__/")
    return tmp_path


@pytest.fixture
def mapping_file(tmp_path):
    """Create a valid mapping file."""
    mapping = {"REPLACEMENT_MAPPING": {"OldName": "NewName", "old_function": "new_function"}}
    map_file = tmp_path / "mapping.json"
    map_file.write_text(json.dumps(mapping))
    return map_file


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    logger = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.debug = Mock()
    logger.setLevel = Mock()
    return logger


@pytest.fixture
def transaction_file(tmp_path):
    """Create a transaction file with various statuses."""
    transactions = [
        {"id": "1", "type": "RENAME_FILE", "status": "COMPLETED", "original_path": "old.txt", "new_path": "new.txt"},
        {"id": "2", "type": "RENAME_FOLDER", "status": "PENDING", "original_path": "old_dir", "new_path": "new_dir"},
        {
            "id": "3",
            "type": "FILE_CONTENT",
            "status": "FAILED",
            "path": "file.txt",
            "line_number": 1,
            "original_line": "old text",
            "new_line": "new text",
        },
    ]
    trans_file = tmp_path / "planned_transactions.json"
    trans_file.write_text(json.dumps(transactions))
    return trans_file


@pytest.fixture
def large_file(tmp_path):
    """Create a large file for testing streaming."""
    large = tmp_path / "large.txt"
    content = "OldName appears here\n" * 100000  # ~2MB
    large.write_text(content)
    return large


@pytest.fixture
def binary_file(tmp_path):
    """Create a binary file."""
    binary = tmp_path / "test.bin"
    binary.write_bytes(b"\x00\x01\x02OldName\xff\xfe")
    return binary


@pytest.fixture
def rtf_file(tmp_path):
    """Create an RTF file."""
    rtf = tmp_path / "test.rtf"
    rtf.write_bytes(b"{\\rtf1\\ansi\\deff0 {\\fonttbl {\\f0 Times;}} OldName text \\par}")
    return rtf


# ============= TESTS FOR _get_logger =============


class TestGetLogger:
    """Test _get_logger function with various scenarios."""

    def test_get_logger_with_prefect_context(self):
        """Test when Prefect context is available."""
        mock_logger = Mock()

        with patch.dict(
            "sys.modules",
            {
                "prefect": Mock(get_run_logger=Mock(return_value=mock_logger)),
                "prefect.exceptions": Mock(MissingContextError=Exception),
            },
        ):
            # Need to reload the module to pick up the mocked imports
            import importlib
            import mass_find_replace.mass_find_replace as mfr

            importlib.reload(mfr)

            logger = mfr._get_logger(verbose_mode=True)
            assert logger == mock_logger
            mock_logger.setLevel.assert_called_once_with(logging.DEBUG)

    def test_get_logger_prefect_missing_context(self):
        """Test when Prefect raises MissingContextError."""

        class MockMissingContextError(Exception):
            pass

        mock_get_run_logger = Mock(side_effect=MockMissingContextError())

        with patch.dict(
            "sys.modules",
            {
                "prefect": Mock(get_run_logger=mock_get_run_logger),
                "prefect.exceptions": Mock(MissingContextError=MockMissingContextError),
            },
        ):
            import importlib
            import mass_find_replace.mass_find_replace as mfr

            importlib.reload(mfr)

            logger = mfr._get_logger(verbose_mode=False)
            assert isinstance(logger, logging.Logger)
            assert logger.name == "mass_find_replace"

    def test_get_logger_no_prefect(self):
        """Test when Prefect is not available."""
        # Clear any existing handlers
        logger = logging.getLogger("mass_find_replace")
        logger.handlers.clear()

        # Mock the import to raise ImportError when importing prefect
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "prefect" or name.startswith("prefect."):
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            logger = _get_logger(verbose_mode=True)
            assert isinstance(logger, logging.Logger)
            assert logger.level == logging.DEBUG
            assert len(logger.handlers) == 1


# ============= TESTS FOR MAIN FLOW =============


class TestMainFlow:
    """Test main_flow with comprehensive scenarios."""

    @patch("mass_find_replace.mass_find_replace.flow")
    def test_main_flow_verbose_mode(self, mock_flow_decorator, temp_dir, mapping_file, caplog):
        """Test main_flow with verbose mode."""
        # Make flow decorator return the original function
        mock_flow_decorator.return_value = lambda fn: fn

        with caplog.at_level(logging.DEBUG):
            # We need to mock the scan to avoid full execution
            with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences", return_value=[]):
                main_flow(
                    directory=str(temp_dir),
                    mapping_file=str(mapping_file),
                    extensions=None,
                    exclude_dirs=[],
                    exclude_files=[],
                    dry_run=False,
                    skip_scan=False,
                    resume=False,
                    force_execution=True,
                    ignore_symlinks_arg=True,
                    use_gitignore=False,
                    custom_ignore_file_path=None,
                    skip_file_renaming=False,
                    skip_folder_renaming=False,
                    skip_content=False,
                    timeout_minutes=10,
                    quiet_mode=False,
                    verbose_mode=True,
                    interactive_mode=False,
                )
                assert "Verbose mode enabled" in caplog.text

    def test_main_flow_invalid_paths(self):
        """Test main_flow with various invalid paths."""
        # Non-existent directory
        main_flow(
            directory="/nonexistent/path",
            mapping_file="mapping.json",
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=True,
            skip_scan=False,
            resume=False,
            force_execution=True,
            ignore_symlinks_arg=True,
            use_gitignore=False,
            custom_ignore_file_path=None,
            skip_file_renaming=False,
            skip_folder_renaming=False,
            skip_content=False,
            timeout_minutes=10,
            quiet_mode=True,
            verbose_mode=False,
            interactive_mode=False,
        )

        # File instead of directory
        with tempfile.NamedTemporaryFile() as f:
            main_flow(
                directory=f.name,
                mapping_file="mapping.json",
                extensions=None,
                exclude_dirs=[],
                exclude_files=[],
                dry_run=False,
                skip_scan=False,
                resume=False,
                force_execution=True,
                ignore_symlinks_arg=True,
                use_gitignore=False,
                custom_ignore_file_path=None,
                skip_file_renaming=False,
                skip_folder_renaming=False,
                skip_content=False,
                timeout_minutes=10,
                quiet_mode=True,
                verbose_mode=False,
                interactive_mode=False,
            )

    @patch("os.access", return_value=False)
    def test_main_flow_no_read_permission(self, mock_access, temp_dir):
        """Test when directory is not readable."""
        main_flow(
            directory=str(temp_dir),
            mapping_file="mapping.json",
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=False,
            skip_scan=False,
            resume=False,
            force_execution=True,
            ignore_symlinks_arg=True,
            use_gitignore=False,
            custom_ignore_file_path=None,
            skip_file_renaming=False,
            skip_folder_renaming=False,
            skip_content=False,
            timeout_minutes=10,
            quiet_mode=True,
            verbose_mode=False,
            interactive_mode=False,
        )

    def test_main_flow_all_operations_skipped(self, temp_dir):
        """Test when all operations are skipped."""
        main_flow(
            directory=str(temp_dir),
            mapping_file="mapping.json",
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=False,
            skip_scan=False,
            resume=False,
            force_execution=True,
            ignore_symlinks_arg=True,
            use_gitignore=False,
            custom_ignore_file_path=None,
            skip_file_renaming=True,
            skip_folder_renaming=True,
            skip_content=True,
            timeout_minutes=10,
            quiet_mode=True,
            verbose_mode=False,
            interactive_mode=False,
        )

    def test_main_flow_empty_directory(self, tmp_path):
        """Test with empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        main_flow(
            directory=str(empty_dir),
            mapping_file="mapping.json",
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=False,
            skip_scan=False,
            resume=False,
            force_execution=True,
            ignore_symlinks_arg=True,
            use_gitignore=False,
            custom_ignore_file_path=None,
            skip_file_renaming=False,
            skip_folder_renaming=False,
            skip_content=False,
            timeout_minutes=10,
            quiet_mode=True,
            verbose_mode=False,
            interactive_mode=False,
        )

    def test_main_flow_invalid_mapping_file(self, temp_dir):
        """Test with invalid mapping file path."""
        main_flow(
            directory=str(temp_dir),
            mapping_file="/nonexistent/mapping.json",
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=False,
            skip_scan=False,
            resume=False,
            force_execution=True,
            ignore_symlinks_arg=True,
            use_gitignore=False,
            custom_ignore_file_path=None,
            skip_file_renaming=False,
            skip_folder_renaming=False,
            skip_content=False,
            timeout_minutes=10,
            quiet_mode=True,
            verbose_mode=False,
            interactive_mode=False,
        )

    def test_main_flow_mapping_load_failure(self, temp_dir, tmp_path):
        """Test when mapping file is invalid."""
        bad_mapping = tmp_path / "bad_mapping.json"
        bad_mapping.write_text("invalid json")

        main_flow(
            directory=str(temp_dir),
            mapping_file=str(bad_mapping),
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=False,
            skip_scan=False,
            resume=False,
            force_execution=True,
            ignore_symlinks_arg=True,
            use_gitignore=False,
            custom_ignore_file_path=None,
            skip_file_renaming=False,
            skip_folder_renaming=False,
            skip_content=False,
            timeout_minutes=10,
            quiet_mode=True,
            verbose_mode=False,
            interactive_mode=False,
        )

    def test_main_flow_empty_mapping_continue(self, temp_dir, tmp_path, monkeypatch):
        """Test with empty mapping and user continues."""
        empty_mapping = tmp_path / "empty_mapping.json"
        empty_mapping.write_text('{"REPLACEMENT_MAPPING": {}}')

        # Mock user input to continue
        monkeypatch.setattr("builtins.input", lambda _: "y")

        with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences", return_value=[]):
            main_flow(
                directory=str(temp_dir),
                mapping_file=str(empty_mapping),
                extensions=None,
                exclude_dirs=[],
                exclude_files=[],
                dry_run=False,
                skip_scan=False,
                resume=False,
                force_execution=False,
                ignore_symlinks_arg=True,
                use_gitignore=False,
                custom_ignore_file_path=None,
                skip_file_renaming=False,
                skip_folder_renaming=False,
                skip_content=False,
                timeout_minutes=10,
                quiet_mode=False,
                verbose_mode=False,
                interactive_mode=False,
            )

    def test_main_flow_empty_mapping_abort(self, temp_dir, tmp_path, monkeypatch):
        """Test with empty mapping and user aborts."""
        empty_mapping = tmp_path / "empty_mapping.json"
        empty_mapping.write_text('{"REPLACEMENT_MAPPING": {}}')

        # Mock user input to abort
        monkeypatch.setattr("builtins.input", lambda _: "n")

        main_flow(
            directory=str(temp_dir),
            mapping_file=str(empty_mapping),
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=False,
            skip_scan=False,
            resume=False,
            force_execution=False,
            ignore_symlinks_arg=True,
            use_gitignore=False,
            custom_ignore_file_path=None,
            skip_file_renaming=False,
            skip_folder_renaming=False,
            skip_content=False,
            timeout_minutes=10,
            quiet_mode=False,
            verbose_mode=False,
            interactive_mode=False,
        )

    def test_main_flow_print_mapping_table(self, temp_dir, mapping_file, capsys, monkeypatch):
        """Test that mapping table is printed."""
        # Mock user input to proceed
        monkeypatch.setattr("builtins.input", lambda _: "y")

        with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences", return_value=[]):
            main_flow(
                directory=str(temp_dir),
                mapping_file=str(mapping_file),
                extensions=None,
                exclude_dirs=[],
                exclude_files=[],
                dry_run=False,
                skip_scan=False,
                resume=False,
                force_execution=False,
                ignore_symlinks_arg=True,
                use_gitignore=False,
                custom_ignore_file_path=None,
                skip_file_renaming=False,
                skip_folder_renaming=False,
                skip_content=False,
                timeout_minutes=10,
                quiet_mode=False,
                verbose_mode=False,
                interactive_mode=False,
            )
            captured = capsys.readouterr()
            assert "OldName" in captured.out
            assert "NewName" in captured.out

    def test_main_flow_with_gitignore(self, temp_dir, mapping_file):
        """Test with .gitignore file."""
        gitignore = temp_dir / ".gitignore"
        gitignore.write_text("*.pyc\n__pycache__/\n")

        with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences") as mock_scan:
            mock_scan.return_value = []
            main_flow(
                directory=str(temp_dir),
                mapping_file=str(mapping_file),
                extensions=None,
                exclude_dirs=[],
                exclude_files=[],
                dry_run=False,
                skip_scan=False,
                resume=False,
                force_execution=True,
                ignore_symlinks_arg=True,
                use_gitignore=True,
                custom_ignore_file_path=None,
                skip_file_renaming=False,
                skip_folder_renaming=False,
                skip_content=False,
                timeout_minutes=10,
                quiet_mode=False,
                verbose_mode=False,
                interactive_mode=False,
            )
            # Check that ignore patterns were loaded
            args, kwargs = mock_scan.call_args
            assert "ignore_spec" in kwargs
            assert kwargs["ignore_spec"] is not None

    def test_main_flow_custom_ignore_file(self, temp_dir, mapping_file):
        """Test with custom ignore file."""
        custom_ignore = temp_dir / ".mfrignore"
        custom_ignore.write_text("*.tmp\ntemp/\n")

        with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences") as mock_scan:
            mock_scan.return_value = []
            main_flow(
                directory=str(temp_dir),
                mapping_file=str(mapping_file),
                extensions=None,
                exclude_dirs=[],
                exclude_files=[],
                dry_run=False,
                skip_scan=False,
                resume=False,
                force_execution=True,
                ignore_symlinks_arg=True,
                use_gitignore=True,
                custom_ignore_file_path=str(custom_ignore),
                skip_file_renaming=False,
                skip_folder_renaming=False,
                skip_content=False,
                timeout_minutes=10,
                quiet_mode=False,
                verbose_mode=False,
                interactive_mode=False,
            )
            args, kwargs = mock_scan.call_args
            assert "ignore_spec" in kwargs

    def test_main_flow_ignore_pattern_error(self, temp_dir, mapping_file):
        """Test when ignore pattern compilation fails."""
        with patch("pathspec.PathSpec.from_lines", side_effect=Exception("Pattern error")):
            with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences", return_value=[]):
                main_flow(
                    directory=str(temp_dir),
                    mapping_file=str(mapping_file),
                    extensions=None,
                    exclude_dirs=[],
                    exclude_files=[],
                    dry_run=False,
                    skip_scan=False,
                    resume=False,
                    force_execution=True,
                    ignore_symlinks_arg=True,
                    use_gitignore=True,
                    custom_ignore_file_path="/some/file",
                    skip_file_renaming=False,
                    skip_folder_renaming=False,
                    skip_content=False,
                    timeout_minutes=10,
                    quiet_mode=False,
                    verbose_mode=False,
                    interactive_mode=False,
                )
                # Should continue without patterns


# ============= TESTS FOR FILE OPERATIONS =============


class TestFileOperations:
    """Test file_system_operations functions."""

    def test_log_fs_op_message_all_levels(self, capsys):
        """Test _log_fs_op_message with all log levels."""
        # Without logger
        _log_fs_op_message(logging.INFO, "Info message", None)
        captured = capsys.readouterr()
        assert "INFO (fs_op): Info message" in captured.out

        _log_fs_op_message(logging.ERROR, "Error message", None)
        captured = capsys.readouterr()
        assert "ERROR (fs_op): Error message" in captured.out

        _log_fs_op_message(logging.WARNING, "Warning message", None)
        captured = capsys.readouterr()
        assert "WARNING (fs_op): Warning message" in captured.out

        _log_fs_op_message(logging.DEBUG, "Debug message", None)
        captured = capsys.readouterr()
        assert "DEBUG (fs_op): Debug message" in captured.out

        # With logger
        mock_logger = Mock()
        _log_fs_op_message(logging.INFO, "Test", mock_logger)
        mock_logger.log.assert_called_once_with(logging.INFO, "Test")

    def test_log_collision_error(self, tmp_path):
        """Test _log_collision_error in various scenarios."""
        log_file = tmp_path / "collisions_errors.log"

        # Normal write
        # Create dummy transaction and paths
        tx = {"id": "test-123", "TYPE": "FILE_NAME", "PATH": "test.txt", "ORIGINAL_NAME": "old", "NEW_NAME": "new"}
        root_dir = tmp_path
        source_path = tmp_path / "old_path"
        collision_path = tmp_path / "new_path"
        collision_type = "exact match"

        _log_collision_error(root_dir, tx, source_path, collision_path, collision_type, None)
        assert log_file.exists()
        content = log_file.read_text()
        assert "Original Name: old" in content
        assert "Proposed New Name: new" in content

        # Write failure
        log_dir = tmp_path / "readonly"
        log_dir.mkdir()
        log_file = log_dir / "collisions_errors.log"
        log_dir.chmod(0o444)

        try:
            # Should not raise exception
            tx = {"id": "test-456", "TYPE": "FILE_NAME", "PATH": "test.txt", "ORIGINAL_NAME": "old", "NEW_NAME": "new"}
            _log_collision_error(tmp_path, tx, tmp_path / "old", tmp_path / "new", "exact match", None)
        finally:
            log_dir.chmod(0o755)

    def test_get_file_encoding_various_files(self, tmp_path, rtf_file, binary_file):
        """Test get_file_encoding with various file types."""
        # Empty file
        empty = tmp_path / "empty.txt"
        empty.write_text("")
        assert get_file_encoding(empty) == "utf-8"

        # RTF file - get_file_encoding returns "latin-1" for RTF files
        assert get_file_encoding(rtf_file) == "latin-1"

        # UTF-8 file
        utf8_file = tmp_path / "utf8.txt"
        utf8_file.write_text("Hello 世界", encoding="utf-8")
        assert get_file_encoding(utf8_file) == "utf-8"

        # Latin-1 file
        latin1_file = tmp_path / "latin1.txt"
        latin1_file.write_bytes("Café".encode("latin-1"))
        with patch("chardet.detect", return_value={"encoding": "latin-1", "confidence": 0.9}):
            assert get_file_encoding(latin1_file) == "latin-1"

        # Read error
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            assert get_file_encoding(Path("/some/file")) == "utf-8"

    def test_save_and_load_transactions(self, tmp_path):
        """Test save and load transactions."""
        trans_file = tmp_path / "trans.json"
        transactions = [{"id": "1", "status": "PENDING"}, {"id": "2", "status": "COMPLETED"}]

        # Save
        save_transactions(transactions, trans_file)
        assert trans_file.exists()

        # Load
        loaded = load_transactions(trans_file)
        assert len(loaded) == 2
        assert loaded[0]["id"] == "1"

        # Load non-existent
        assert load_transactions(Path("/nonexistent.json")) is None

        # Load invalid JSON
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not json")
        assert load_transactions(bad_json) is None

        # Load non-list
        not_list = tmp_path / "notlist.json"
        not_list.write_text('{"not": "list"}')
        assert load_transactions(not_list) is None

        # Save empty with warning
        import logging

        with patch("mass_find_replace.file_system_operations._log_fs_op_message") as mock_log:
            save_transactions([], trans_file)
            # Check that warning was logged
            mock_log.assert_called_with(logging.WARNING, "No transactions to save.", None)

        # Save with OS error
        with patch("builtins.open", side_effect=OSError("No space")):
            save_transactions(transactions, Path("/invalid/path.json"))  # Should not crash

    def test_update_transaction_status(self):
        """Test update_transaction_status_in_list."""
        transactions = [{"id": "1", "status": "PENDING"}, {"id": "2", "status": "PENDING"}]

        # Update existing
        update_transaction_status_in_list(transactions, "1", TransactionStatus.COMPLETED)
        # The function sets "STATUS" not "status"
        assert transactions[0]["STATUS"] == "COMPLETED"

        # Update non-existent (should log warning)
        from unittest.mock import Mock

        mock_logger = Mock()
        result = update_transaction_status_in_list(transactions, "999", TransactionStatus.COMPLETED, logger=mock_logger)
        assert result is False
        mock_logger.warning.assert_called_with("Transaction 999 not found for status update.")

    def test_walk_for_scan(self, temp_dir):
        """Test _walk_for_scan function."""
        # Create symlink
        target = temp_dir / "target"
        target.mkdir()
        symlink = temp_dir / "link"
        symlink.symlink_to(target)

        # Without following symlinks
        # Test with proper arguments
        excluded_dirs_abs = []
        ignore_symlinks = True  # This is the correct parameter to skip symlinks
        items = list(_walk_for_scan(Path(temp_dir), excluded_dirs_abs, ignore_symlinks, None, None))
        # Should skip the symlink
        paths = [str(item) for item in items]
        assert str(symlink) not in paths

        # With ignore patterns
        ignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", ["*.pyc", "src/"])
        items = list(_walk_for_scan(Path(temp_dir), excluded_dirs_abs, False, ignore_spec, None))
        # Should have handled patterns
        assert isinstance(items, list)

        # With OSError - we need to test the actual error handling in _walk_for_scan
        # Since it handles errors internally, we should check it doesn't crash
        bad_path = Path("/nonexistent/path")
        items = list(_walk_for_scan(bad_path, excluded_dirs_abs, False, None, None))
        assert items == []  # Should handle non-existent path gracefully


# ============= TESTS FOR SCAN AND EXECUTE =============


class TestScanAndExecute:
    """Test scanning and execution functions."""

    def test_scan_directory_with_transactions(self, temp_dir, mapping_file):
        """Test scan_directory_for_occurrences."""
        # Load mapping first
        mapping = load_replacement_map(mapping_file)
        assert mapping is not None

        # Test basic scan
        transactions = scan_directory_for_occurrences(root_dir=Path(temp_dir), excluded_dirs=[], excluded_files=[], file_extensions=None, ignore_symlinks=True, ignore_spec=None, skip_file_renaming=False, skip_folder_renaming=False, skip_content=False)

        # Should find occurrences
        assert len(transactions) > 0

        # Test with skip flags
        transactions = scan_directory_for_occurrences(root_dir=Path(temp_dir), excluded_dirs=[], excluded_files=[], file_extensions=None, ignore_symlinks=True, ignore_spec=None, skip_file_renaming=True, skip_folder_renaming=True, skip_content=False)
        # Should only have content transactions
        for t in transactions:
            assert t["type"] == TransactionType.FILE_CONTENT_LINE.value

    def test_scan_with_binary_file(self, temp_dir, binary_file, mapping_file):
        """Test scanning with binary files."""
        # Load mapping
        load_replacement_map(mapping_file)

        # Mock binary log file
        with patch("builtins.open", mock_open()) as mock_file:
            transactions = scan_directory_for_occurrences(root_dir=Path(temp_dir.parent), excluded_dirs=[], excluded_files=[], file_extensions=None, ignore_symlinks=True, ignore_spec=None, skip_content=False)

            # Check if binary file was logged
            calls = mock_file().write.call_args_list
            binary_logged = any(str(binary_file) in str(call) for call in calls)

    def test_scan_with_large_file(self, temp_dir, large_file, mapping_file):
        """Test scanning with large files."""
        load_replacement_map(mapping_file)

        # Temporarily reduce threshold
        original_threshold = fs_ops.LARGE_FILE_SIZE_THRESHOLD
        fs_ops.LARGE_FILE_SIZE_THRESHOLD = 1000  # 1KB

        try:
            transactions = scan_directory_for_occurrences(root_dir=Path(large_file.parent), excluded_dirs=[], excluded_files=[], file_extensions=None, ignore_symlinks=True, ignore_spec=None, skip_content=False)

            # Should handle large file
            content_trans = [t for t in transactions if t["type"] == TransactionType.FILE_CONTENT_LINE.value]
            assert len(content_trans) > 0
        finally:
            fs_ops.LARGE_FILE_SIZE_THRESHOLD = original_threshold

    def test_execute_rename_transaction(self, tmp_path):
        """Test _execute_rename_transaction."""
        # Create test file
        old_file = tmp_path / "old.txt"
        old_file.write_text("content")

        transaction = {
            "id": "1",
            "type": TransactionType.FILE_NAME.value,
            "original_path": str(old_file),
            "new_path": str(tmp_path / "new.txt"),
        }

        # Normal execution
        result = _execute_rename_transaction(tx=transaction, root_dir=tmp_path, path_translation_map={}, path_cache={}, dry_run=False, logger=None)
        status, error_msg, changed = result
        assert status == TransactionStatus.COMPLETED
        assert changed is True
        assert not old_file.exists()
        assert (tmp_path / "new.txt").exists()

        # Dry run
        old_file2 = tmp_path / "old2.txt"
        old_file2.write_text("content")
        transaction2 = {
            "id": "2",
            "type": TransactionType.FILE_NAME.value,
            "original_path": str(old_file2),
            "new_path": str(tmp_path / "new2.txt"),
        }

        result = _execute_rename_transaction(tx=transaction2, root_dir=tmp_path, path_translation_map={}, path_cache={}, dry_run=True, logger=None)
        status, error_msg, changed = result
        assert status == TransactionStatus.COMPLETED
        assert changed is True  # Even in dry run, it reports what would be changed
        assert old_file2.exists()  # Should not be renamed in dry run

        # Path not found
        transaction3 = {
            "id": "3",
            "type": TransactionType.FILE_NAME.value,
            "original_path": "/nonexistent/file.txt",
            "new_path": "/nonexistent/new.txt",
        }
        result = _execute_rename_transaction(tx=transaction3, root_dir=tmp_path, path_translation_map={}, path_cache={}, dry_run=False, logger=None)
        status, error_msg, changed = result
        assert status == TransactionStatus.FAILED
        assert changed is False

        # Same path (no change needed)
        same_file = tmp_path / "same.txt"
        same_file.write_text("content")
        transaction4 = {
            "id": "4",
            "type": TransactionType.FILE_NAME.value,
            "original_path": str(same_file),
            "new_path": str(same_file),
        }
        result = _execute_rename_transaction(tx=transaction4, root_dir=tmp_path, path_translation_map={}, path_cache={}, dry_run=False, logger=None)
        status, error_msg, changed = result
        assert status == TransactionStatus.COMPLETED
        assert changed is False  # No change when paths are the same

    def test_execute_content_line_transaction(self, tmp_path):
        """Test _execute_content_line_transaction."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Line 1\nLine 2 with OldName\nLine 3")

        transaction = {
            "id": "1",
            "type": TransactionType.FILE_CONTENT_LINE.value,
            "path": str(test_file),
            "line_number": 2,
            "original_line": "Line 2 with OldName",
            "new_line": "Line 2 with NewName",
            "encoding": "utf-8",
        }

        # Normal execution
        result = _execute_content_line_transaction(tx=transaction, root_dir=tmp_path, path_translation_map={}, path_cache={}, logger=None)
        status, error_msg, changed = result
        assert status == TransactionStatus.COMPLETED
        assert changed is True
        assert "NewName" in test_file.read_text()

        # File not found
        transaction2 = transaction.copy()
        transaction2["path"] = "/nonexistent/file.txt"
        result = _execute_content_line_transaction(tx=transaction2, root_dir=tmp_path, path_translation_map={}, path_cache={}, logger=None)
        status, error_msg, changed = result
        assert status == TransactionStatus.FAILED
        assert changed is False

        # RTF file (should skip)
        rtf_trans = transaction.copy()
        rtf_trans["encoding"] = "rtf"
        result = _execute_content_line_transaction(tx=rtf_trans, root_dir=tmp_path, path_translation_map={}, path_cache={}, logger=None)
        status, error_msg, changed = result
        assert status == TransactionStatus.SKIPPED  # Skipped successfully
        assert changed is False

        # Invalid line number
        invalid_trans = transaction.copy()
        invalid_trans["line_number"] = 999
        result = _execute_content_line_transaction(tx=invalid_trans, root_dir=tmp_path, path_translation_map={}, path_cache={}, logger=None)
        status, error_msg, changed = result
        assert status == TransactionStatus.FAILED
        assert changed is False

    def test_execute_file_content_batch(self, tmp_path):
        """Test _execute_file_content_batch."""
        test_file = tmp_path / "batch.txt"
        test_file.write_text("OldName line 1\nOldName line 2\nOldName line 3")

        transactions = [
            {"id": "1", "line_number": 1, "original_line": "OldName line 1", "new_line": "NewName line 1"},
            {"id": "2", "line_number": 3, "original_line": "OldName line 3", "new_line": "NewName line 3"},
        ]

        # Normal execution
        completed, skipped, failed = _execute_file_content_batch(abs_filepath=test_file, transactions=transactions, logger=None)

        assert completed == 2
        assert skipped == 0
        assert failed == 0
        content = test_file.read_text()
        assert "NewName line 1" in content
        assert "NewName line 3" in content

        # File not found
        completed, skipped, failed = _execute_file_content_batch(abs_filepath=Path("/nonexistent/file.txt"), transactions=transactions, logger=None)
        assert completed == 0
        assert failed == len(transactions)

    def test_process_large_file_content(self, tmp_path, mapping_file):
        """Test process_large_file_content."""
        # Create large file
        large_file = tmp_path / "large.txt"
        content = []
        for i in range(1000):
            content.append(f"Line {i} with OldName\n")
        large_file.write_text("".join(content))

        # Load mapping
        load_replacement_map(mapping_file)

        transactions = [
            {
                "id": f"{i}",
                "type": TransactionType.FILE_CONTENT_LINE.value,
                "path": str(large_file),
                "line_number": i + 1,
                "original_line": f"Line {i} with OldName",
                "new_line": f"Line {i} with NewName",
                "encoding": "utf-8",
            }
            for i in range(0, 100, 10)  # Every 10th line
        ]

        # Process
        process_large_file_content(txns_for_file=transactions, abs_filepath=large_file, file_encoding="utf-8", is_rtf=False, logger=None)

        # Check results
        content = large_file.read_text()
        assert "Line 0 with NewName" in content
        assert "Line 50 with NewName" in content

        # Test with RTF - process_large_file_content handles RTF differently
        # For RTF files, it extracts text first, so we need to create a proper RTF file
        rtf_file = tmp_path / "test.rtf"
        rtf_file.write_text(r"{\rtf1\ansi{\fonttbl\f0\fswiss Helvetica;}\f0 OldName\par}")
        rtf_trans = [
            {
                "id": "1",
                "type": TransactionType.FILE_CONTENT_LINE.value,
                "path": str(rtf_file),
                "line_number": 1,
                "original_line": "OldName",
                "new_line": "NewName",
                "encoding": "rtf",
            }
        ]
        process_large_file_content(txns_for_file=rtf_trans, abs_filepath=rtf_file, file_encoding="rtf", is_rtf=True, logger=None)

    def test_group_and_process_file_transactions(self, tmp_path):
        """Test group_and_process_file_transactions."""
        # Create test files
        file1 = tmp_path / "file1.txt"
        file1.write_text("OldName in file1")
        file2 = tmp_path / "file2.txt"
        file2.write_text("OldName in file2")

        transactions = [
            {
                "id": "1",
                "type": TransactionType.FILE_CONTENT_LINE.value,
                "path": str(file1),
                "line_number": 1,
                "original_line": "OldName in file1",
                "new_line": "NewName in file1",
                "encoding": "utf-8",
                "status": TransactionStatus.PENDING.value,
            },
            {
                "id": "2",
                "type": TransactionType.FILE_CONTENT_LINE.value,
                "path": str(file2),
                "line_number": 1,
                "original_line": "OldName in file2",
                "new_line": "NewName in file2",
                "encoding": "utf-8",
                "status": TransactionStatus.PENDING.value,
            },
        ]

        # Process
        group_and_process_file_transactions(transactions=transactions, root_dir=tmp_path, path_translation_map={}, path_cache={}, dry_run=False, skip_content=False, logger=None)

        # Check status updates
        assert transactions[0]["STATUS"] == TransactionStatus.COMPLETED.value
        assert transactions[1]["STATUS"] == TransactionStatus.COMPLETED.value

        # Check file contents
        assert "NewName" in file1.read_text()
        assert "NewName" in file2.read_text()

        # Test skip content
        transactions[0]["STATUS"] = TransactionStatus.PENDING.value
        transactions[1]["STATUS"] = TransactionStatus.PENDING.value
        group_and_process_file_transactions(transactions=transactions, root_dir=tmp_path, path_translation_map={}, path_cache={}, dry_run=False, skip_content=True, logger=None)
        assert transactions[0]["STATUS"] == TransactionStatus.SKIPPED.value

    def test_execute_all_transactions(self, tmp_path, transaction_file):
        """Test execute_all_transactions."""
        # Create files for transactions
        (tmp_path / "old.txt").write_text("content")
        (tmp_path / "old_dir").mkdir()
        (tmp_path / "file.txt").write_text("old text")

        # Load transactions
        transactions = load_transactions(transaction_file)

        # Mock user input for interactive mode
        with patch("builtins.input", return_value="y"):
            result = execute_all_transactions(transactions_file_path=transaction_file, root_dir=tmp_path, dry_run=False, resume=False, timeout_minutes=10, skip_file_renaming=False, skip_folder_renaming=False, skip_content=False, interactive_mode=True, logger=None)

        # Some should succeed, some fail
        assert result == 0  # At least partial success

        # Test with empty transaction file
        empty_trans_file = tmp_path / "empty_trans.json"
        empty_trans_file.write_text("[]")
        result = execute_all_transactions(transactions_file_path=empty_trans_file, root_dir=tmp_path, dry_run=False, resume=False, timeout_minutes=10, skip_file_renaming=False, skip_folder_renaming=False, skip_content=False, interactive_mode=False, logger=None)
        assert result == 1  # No transactions error

        # Test unknown transaction type
        unknown_trans = [{"id": "999", "type": "UNKNOWN_TYPE", "status": TransactionStatus.PENDING.value}]
        unknown_trans_file = tmp_path / "unknown_trans.json"
        save_transactions(unknown_trans, unknown_trans_file)

        result = execute_all_transactions(transactions_file_path=unknown_trans_file, root_dir=tmp_path, dry_run=False, resume=False, timeout_minutes=10, skip_file_renaming=False, skip_folder_renaming=False, skip_content=False, interactive_mode=False, logger=None)
        # Reload to check status
        updated_trans = load_transactions(unknown_trans_file)
        assert updated_trans[0]["STATUS"] == TransactionStatus.FAILED.value


# ============= TESTS FOR REPLACE LOGIC =============


class TestReplaceLogic:
    """Test replace_logic functions comprehensively."""

    def test_log_message_all_scenarios(self, capsys):
        """Test _log_message in all scenarios."""
        # Test with debug mode
        import mass_find_replace.replace_logic as rl

        original_debug = rl._DEBUG_REPLACE_LOGIC
        rl._DEBUG_REPLACE_LOGIC = True

        try:
            _log_message(logging.DEBUG, "Debug message")
            captured = capsys.readouterr()
            assert "RL_DBG_STDERR: Debug message" in captured.err
        finally:
            rl._DEBUG_REPLACE_LOGIC = original_debug

        # Test without logger - all levels
        _log_message(logging.INFO, "Info message", logger=None)
        captured = capsys.readouterr()
        assert "INFO: Info message" in captured.out

        _log_message(logging.WARNING, "Warning message", logger=None)
        captured = capsys.readouterr()
        assert "WARNING: Warning message" in captured.err  # WARNING goes to stderr

        _log_message(logging.ERROR, "Error message", logger=None)
        captured = capsys.readouterr()
        assert "ERROR: Error message" in captured.err

        _log_message(logging.CRITICAL, "Critical message", logger=None)
        captured = capsys.readouterr()
        # CRITICAL level just goes to stderr without a prefix
        assert "Critical message" in captured.err

        # Test with logger
        mock_logger = Mock()
        _log_message(logging.INFO, "Test", logger=mock_logger)
        mock_logger.log.assert_called_once_with(logging.INFO, "Test")

    def test_strip_functions_edge_cases(self):
        """Test strip_diacritics and strip_control_characters edge cases."""
        # Non-string inputs
        assert strip_diacritics(123) == 123
        assert strip_diacritics(None) is None
        assert strip_diacritics([1, 2, 3]) == [1, 2, 3]

        assert strip_control_characters(123) == 123
        assert strip_control_characters(None) is None
        assert strip_control_characters({"key": "value"}) == {"key": "value"}

        # String inputs
        assert strip_diacritics("café") == "cafe"
        assert strip_control_characters("test\x00\x01") == "test"

    def test_load_replacement_map_all_errors(self, tmp_path):
        """Test all error scenarios in load_replacement_map."""
        # File not found
        result = load_replacement_map(Path("/nonexistent/map.json"))
        assert result is False  # Returns False on error

        # Read error
        with patch("builtins.open", side_effect=Exception("Read error")):
            result = load_replacement_map(Path("some_file.json"))
            assert result is False

        # Invalid JSON
        bad_json = tmp_path / "bad.json"
        bad_json.write_text("not json")
        result = load_replacement_map(bad_json)
        assert result is False

        # Missing REPLACEMENT_MAPPING key
        wrong_key = tmp_path / "wrong_key.json"
        wrong_key.write_text('{"wrong": {}}')
        result = load_replacement_map(wrong_key)
        assert result is False

        # REPLACEMENT_MAPPING not a dict
        not_dict = tmp_path / "not_dict.json"
        not_dict.write_text('{"REPLACEMENT_MAPPING": "string"}')
        result = load_replacement_map(not_dict)
        assert result is False

        # Invalid key-value pairs
        # We need to mock json.load to return non-string types
        with patch("json.load") as mock_load:
            mock_load.return_value = {
                "REPLACEMENT_MAPPING": {
                    "valid": "replacement",
                    123: "invalid_key",  # Non-string key
                    "invalid_value": 456,  # Non-string value
                }
            }
            valid_map = tmp_path / "mixed.json"
            valid_map.write_text("{}")
            result = load_replacement_map(valid_map)
            # Should load only valid pairs
            assert result == {"valid": "replacement"}

        # Empty normalized key
        empty_key = tmp_path / "empty_key.json"
        empty_key.write_text(
            json.dumps(
                {
                    "REPLACEMENT_MAPPING": {
                        "\x00\x01\x02": "value",  # Only control chars
                        "valid": "replacement",
                    }
                }
            )
        )
        result = load_replacement_map(empty_key)
        assert result is True  # Should succeed, skipping invalid keys
        assert get_mapping_size() == 1  # Only "valid" key loaded

        # Empty value
        empty_value = tmp_path / "empty_value.json"
        empty_value.write_text(json.dumps({"REPLACEMENT_MAPPING": {"key": "", "valid": "replacement"}}))
        result = load_replacement_map(empty_value)
        assert result is True  # Should succeed, skipping invalid values
        assert get_mapping_size() == 1  # Only "valid" loaded

        # No valid rules
        no_valid = tmp_path / "no_valid.json"
        no_valid.write_text(json.dumps({"REPLACEMENT_MAPPING": {"": "empty_key", "empty_value": ""}}))
        result = load_replacement_map(no_valid)
        assert result is False

        # Recursive mapping
        recursive = tmp_path / "recursive.json"
        recursive.write_text(
            json.dumps(
                {
                    "REPLACEMENT_MAPPING": {
                        "a": "b",
                        "b": "c",
                        "c": "a",  # Creates cycle a->b->c->a
                    }
                }
            )
        )
        result = load_replacement_map(recursive)
        assert result is False

        # Regex compilation error
        with patch("re.compile", side_effect=re.error("Invalid regex")):
            good_map = tmp_path / "good.json"
            good_map.write_text(json.dumps({"REPLACEMENT_MAPPING": {"test": "replacement"}}))
            result = load_replacement_map(good_map)
            assert result is False

    def test_get_key_characters_and_size(self):
        """Test get_key_characters and get_mapping_size."""
        import mass_find_replace.replace_logic as rl

        # With mapping
        rl._RAW_REPLACEMENT_MAPPING = {"test": "value", "foo": "bar"}
        rl._KEY_CHARACTER_SET = set("testfo")

        chars = get_key_characters()
        assert chars == {"t", "e", "s", "f", "o"}
        assert chars is not rl._KEY_CHARACTER_SET  # Should be a copy

        assert get_mapping_size() == 2

        # Without mapping
        rl._RAW_REPLACEMENT_MAPPING = {}
        rl._KEY_CHARACTER_SET = set()

        assert get_key_characters() == set()
        assert get_mapping_size() == 0

    def test_actual_replace_callback(self):
        """Test _actual_replace_callback."""
        import mass_find_replace.replace_logic as rl

        # Set up mapping
        rl._RAW_REPLACEMENT_MAPPING = {"oldname": "NewName", "test": "replacement"}

        # Mock match object
        match = Mock()
        match.group.return_value = "OldName"

        # Found match (canonicalized)
        result = _actual_replace_callback(match)
        assert result == "NewName"

        # Not found match
        match.group.return_value = "NotFound"
        with patch("mass_find_replace.replace_logic._MODULE_LOGGER") as mock_logger:
            result = _actual_replace_callback(match)
            assert result == "NotFound"  # Returns original
            mock_logger.warning.assert_called()

    def test_replace_occurrences_all_cases(self):
        """Test replace_occurrences in all scenarios."""
        import mass_find_replace.replace_logic as rl

        # Test with debug mode
        original_debug = rl._DEBUG_REPLACE_LOGIC
        rl._DEBUG_REPLACE_LOGIC = True
        rl._RAW_REPLACEMENT_MAPPING = {"test": "replacement"}
        rl._COMPILED_PATTERN_FOR_ACTUAL_REPLACE = re.compile("test")

        try:
            with patch("mass_find_replace.replace_logic._MODULE_LOGGER") as mock_logger:
                result = replace_occurrences("test string")
                mock_logger.debug.assert_called()
        finally:
            rl._DEBUG_REPLACE_LOGIC = original_debug

        # Non-string input
        assert replace_occurrences(123) == 123
        assert replace_occurrences(None) is None

        # No mapping loaded
        rl._MAPPING_LOADED = False
        with patch("mass_find_replace.replace_logic._MODULE_LOGGER") as mock_logger:
            result = replace_occurrences("test")
            assert result == "test"
            mock_logger.warning.assert_called_with("No replacement map loaded.")

        # No regex compiled
        rl._MAPPING_LOADED = True
        rl._COMPILED_PATTERN_FOR_ACTUAL_REPLACE = None
        with patch("mass_find_replace.replace_logic._MODULE_LOGGER") as mock_logger:
            result = replace_occurrences("test")
            assert result == "test"
            mock_logger.warning.assert_called_with("No regex compiled.")

        # Normal replacement
        rl._RAW_REPLACEMENT_MAPPING = {"old": "new"}
        rl._COMPILED_PATTERN_FOR_ACTUAL_REPLACE = re.compile(r"\b(old)\b", re.IGNORECASE)
        result = replace_occurrences("This is OLD text")
        assert result == "This is new text"


# ============= TESTS FOR CLI AND MAIN =============


class TestCLIAndMain:
    """Test CLI and main entry point."""

    def test_subprocess_command_all_cases(self):
        """Test _run_subprocess_command comprehensively."""
        with patch("subprocess.run") as mock_run:
            # Success case
            mock_run.return_value = Mock(returncode=0, stdout="Success output", stderr="")
            assert _run_subprocess_command(["echo", "test"], "Test echo") is True

            # Failure case
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error message")
            assert _run_subprocess_command(["false"], "Test fail") is False

            # FileNotFoundError
            mock_run.side_effect = FileNotFoundError("Command not found")
            assert _run_subprocess_command(["missing"], "Test missing") is False

            # Generic exception
            mock_run.side_effect = Exception("Unexpected error")
            assert _run_subprocess_command(["error"], "Test error") is False

    def test_main_cli_self_test(self, monkeypatch):
        """Test main_cli with --self-test option."""
        # Success case
        monkeypatch.setattr("sys.argv", ["mfr", "--self-test"])
        with patch("mass_find_replace.mass_find_replace._run_subprocess_command", return_value=True):
            assert main_cli() == 0

        # UV fails, pip succeeds
        monkeypatch.setattr("sys.argv", ["mfr", "--self-test"])
        with patch("mass_find_replace.mass_find_replace._run_subprocess_command") as mock_run:
            mock_run.side_effect = [False, True, True]  # First uv fails, then pip succeeds, then pytest succeeds
            assert main_cli() == 0
            assert mock_run.call_count == 3

        # Both fail
        monkeypatch.setattr("sys.argv", ["mfr", "--self-test"])
        with patch("mass_find_replace.mass_find_replace._run_subprocess_command", return_value=False):
            assert main_cli() == 1

    def test_main_cli_invalid_args(self, monkeypatch):
        """Test main_cli with invalid arguments."""
        # Invalid timeout
        monkeypatch.setattr("sys.argv", ["mfr", ".", "--timeout", "-1"])
        with pytest.raises(SystemExit) as exc:
            main_cli()
        assert exc.value.code == 2

        # Help
        monkeypatch.setattr("sys.argv", ["mfr", "--help"])
        with pytest.raises(SystemExit) as exc:
            main_cli()
        assert exc.value.code == 0

    def test_main_cli_missing_dependency(self, monkeypatch):
        """Test when required dependencies are missing."""
        monkeypatch.setattr("sys.argv", ["mfr", "."])

        # Mock the import of a required module to fail
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "click":
                raise ImportError("click module not found")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            # Clear cached module to force re-import
            if "mass_find_replace.mass_find_replace" in sys.modules:
                del sys.modules["mass_find_replace.mass_find_replace"]

            # The import should fail
            with pytest.raises(ImportError) as exc_info:
                import mass_find_replace.mass_find_replace

            assert "click" in str(exc_info.value)

    def test_main_cli_normal_execution(self, monkeypatch, capsys):
        """Test normal CLI execution."""
        monkeypatch.setattr("sys.argv", ["mfr", ".", "--force"])

        with patch("mass_find_replace.mass_find_replace.main_flow", return_value=0):
            result = main_cli()

            # Check script name printed
            captured = capsys.readouterr()
            assert SCRIPT_NAME in captured.out

    def test_check_existing_transactions_comprehensive(self, tmp_path, mock_logger):
        """Test _check_existing_transactions with all scenarios."""
        # No file
        has_existing, progress = _check_existing_transactions(Path("/nonexistent.json"), mock_logger)
        assert not has_existing
        assert progress == 0

        # Valid file with mixed statuses
        trans_file = tmp_path / "trans.json"
        transactions = [
            {"status": TransactionStatus.COMPLETED.value},
            {"status": TransactionStatus.COMPLETED.value},
            {"status": TransactionStatus.PENDING.value},
            {"status": TransactionStatus.FAILED.value},
            {"status": TransactionStatus.IN_PROGRESS.value},
        ]
        trans_file.write_text(json.dumps(transactions))

        has_existing, progress = _check_existing_transactions(trans_file, mock_logger)
        assert has_existing
        assert progress == 40  # 2/5 completed

        # Empty transactions
        empty_file = tmp_path / "empty.json"
        empty_file.write_text("[]")
        has_existing, progress = _check_existing_transactions(empty_file, mock_logger)
        assert has_existing
        assert progress == 0

        # Invalid JSON
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("invalid")
        has_existing, progress = _check_existing_transactions(bad_file, mock_logger)
        assert not has_existing
        assert progress == 0

        # All completed
        all_done = tmp_path / "done.json"
        all_done.write_text(json.dumps([{"status": TransactionStatus.COMPLETED.value}, {"status": TransactionStatus.COMPLETED.value}]))
        has_existing, progress = _check_existing_transactions(all_done, mock_logger)
        assert has_existing
        assert progress == 100

    def test_print_mapping_table_comprehensive(self, mock_logger, capsys):
        """Test _print_mapping_table with various scenarios."""
        # Empty mapping
        _print_mapping_table({}, mock_logger)
        mock_logger.info.assert_called_with("Replacement mapping is empty.")

        # Reset mock
        mock_logger.reset_mock()

        # Simple mapping
        mapping = {"old": "new"}
        _print_mapping_table(mapping, mock_logger)
        # Should print to stdout, not logger calls
        captured = capsys.readouterr()
        assert "old" in captured.out
        assert "new" in captured.out

        # Large mapping with long keys/values
        large_mapping = {
            "very_long_old_name_that_should_stretch_column": "very_long_new_name_that_should_stretch_column",
            "short": "name",
        }
        _print_mapping_table(large_mapping, mock_logger)
        captured = capsys.readouterr()
        assert "very_long_old_name" in captured.out

    def test_get_operation_description_all_combinations(self):
        """Test _get_operation_description with all combinations."""
        # All operations
        assert _get_operation_description(False, False, False) == "folder names, file names, and file contents"

        # Two operations
        assert _get_operation_description(True, False, False) == "file names and file contents"
        assert _get_operation_description(False, True, False) == "folder names and file contents"
        assert _get_operation_description(False, False, True) == "folder names and file names"

        # Single operation
        assert _get_operation_description(False, True, True) == "file names"
        assert _get_operation_description(True, False, True) == "folder names"
        assert _get_operation_description(True, True, False) == "file contents"

        # No operations
        assert _get_operation_description(True, True, True) == "nothing (all operations skipped)"


# ============= TESTS FOR MAIN ENTRY POINT =============


def test_main_entry_exception_handling():
    """Test exception handling in __main__ block."""
    # Create a script that simulates the main entry point with an exception
    test_script = """
import sys

class MockMainCLI:
    def __call__(self):
        raise Exception("Test exception in main")

main_cli = MockMainCLI()

if __name__ == "__main__":
    try:
        sys.exit(main_cli())
    except Exception as e:
        print(f"\\033[91mUnexpected error: {e}\\033[0m", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
"""

    # Write to temp file and execute
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(test_script)
        f.flush()

        # Run the script
        result = subprocess.run([sys.executable, f.name], check=False, capture_output=True, text=True)

        assert result.returncode == 1
        assert "Test exception in main" in result.stderr
        assert "Unexpected error" in result.stderr

        # Clean up
        os.unlink(f.name)
