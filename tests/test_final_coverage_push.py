#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Final tests to push coverage higher by targeting specific uncovered lines."""

import json
import logging
import os
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import mass_find_replace.mass_find_replace as mfr
import mass_find_replace.file_system_operations as fs_ops
import mass_find_replace.replace_logic as replace


# Test file_system_operations uncovered lines

def test_log_fs_op_message_with_logger():
    """Test _log_fs_op_message with logger."""
    mock_logger = Mock()
    
    fs_ops._log_fs_op_message(logging.INFO, "Info message", mock_logger)
    mock_logger.info.assert_called_once_with("Info message")
    
    fs_ops._log_fs_op_message(logging.ERROR, "Error message", mock_logger)
    mock_logger.error.assert_called_once_with("Error message")
    
    fs_ops._log_fs_op_message(logging.WARNING, "Warning message", mock_logger)
    mock_logger.warning.assert_called_once_with("Warning message")
    
    fs_ops._log_fs_op_message(logging.DEBUG, "Debug message", mock_logger)
    mock_logger.debug.assert_called_once_with("Debug message")


def test_log_fs_op_message_critical_level():
    """Test _log_fs_op_message with CRITICAL level."""
    mock_logger = Mock()
    
    # Test with a level that's not explicitly handled
    fs_ops._log_fs_op_message(logging.CRITICAL, "Critical message", mock_logger)
    mock_logger.log.assert_called_once_with(logging.CRITICAL, "Critical message")


def test_get_file_encoding_empty_file(tmp_path):
    """Test get_file_encoding with empty file."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_bytes(b"")
    
    encoding = fs_ops.get_file_encoding(empty_file)
    assert encoding == "utf-8"


def test_get_file_encoding_large_sample(tmp_path):
    """Test get_file_encoding with large sample size."""
    # Create a file with UTF-8 content
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello " * 1000, encoding="utf-8")
    
    encoding = fs_ops.get_file_encoding(test_file, sample_size=10000)
    assert encoding == "utf-8"


def test_get_file_encoding_chardet_confidence(tmp_path):
    """Test get_file_encoding when chardet has low confidence."""
    test_file = tmp_path / "test.txt"
    # Write some ambiguous bytes
    test_file.write_bytes(b"\x80\x81\x82\x83")
    
    with patch('chardet.detect') as mock_detect:
        mock_detect.return_value = {'encoding': 'latin-1', 'confidence': 0.1}
        encoding = fs_ops.get_file_encoding(test_file)
        assert encoding == "utf-8"  # Falls back to UTF-8 due to low confidence


def test_get_file_encoding_chardet_none(tmp_path):
    """Test get_file_encoding when chardet returns None."""
    test_file = tmp_path / "test.txt"
    test_file.write_bytes(b"test")
    
    with patch('chardet.detect') as mock_detect:
        mock_detect.return_value = {'encoding': None, 'confidence': 0}
        encoding = fs_ops.get_file_encoding(test_file)
        assert encoding == "utf-8"


def test_load_ignore_patterns_success(tmp_path):
    """Test load_ignore_patterns with valid file."""
    ignore_file = tmp_path / ".gitignore"
    ignore_file.write_text("*.pyc\n__pycache__/\n# Comment\n\n*.log")
    
    patterns = fs_ops.load_ignore_patterns(ignore_file)
    assert patterns is not None
    assert len(patterns.patterns) == 3  # 3 non-empty, non-comment lines


def test_load_ignore_patterns_empty_file(tmp_path):
    """Test load_ignore_patterns with empty file."""
    ignore_file = tmp_path / ".gitignore"
    ignore_file.write_text("")
    
    patterns = fs_ops.load_ignore_patterns(ignore_file)
    assert patterns is not None
    assert len(patterns.patterns) == 0


def test_load_ignore_patterns_io_error(tmp_path):
    """Test load_ignore_patterns with IO error."""
    with patch('pathlib.Path.open', side_effect=OSError("Read error")):
        patterns = fs_ops.load_ignore_patterns(Path("/fake/path"))
        assert patterns is None


def test_save_transactions_with_backup(tmp_path):
    """Test save_transactions creating backup."""
    trans_file = tmp_path / "transactions.json"
    # Create existing file
    trans_file.write_text('{"old": "data"}')
    
    transactions = [{"id": "1", "status": "PENDING"}]
    fs_ops.save_transactions(transactions, trans_file)
    
    # Check backup was created
    backup_file = tmp_path / "transactions.json.bak"
    assert backup_file.exists()
    assert json.loads(backup_file.read_text()) == {"old": "data"}


def test_save_transactions_backup_error(tmp_path):
    """Test save_transactions when backup fails."""
    trans_file = tmp_path / "transactions.json"
    trans_file.write_text('{"old": "data"}')
    
    transactions = [{"id": "1", "status": "PENDING"}]
    
    # Mock rename to fail
    with patch('pathlib.Path.rename', side_effect=OSError("Rename failed")):
        # Should still save the new data
        fs_ops.save_transactions(transactions, trans_file)
        assert json.loads(trans_file.read_text()) == transactions


def test_update_transaction_status_in_list_found():
    """Test update_transaction_status_in_list when transaction is found."""
    transactions = [
        {"id": "1", "STATUS": "PENDING"},
        {"id": "2", "STATUS": "PENDING"}
    ]
    
    fs_ops.update_transaction_status_in_list(
        transactions, "2", fs_ops.TransactionStatus.COMPLETED
    )
    
    assert transactions[1]["STATUS"] == "COMPLETED"


def test_update_transaction_status_with_error_message():
    """Test update_transaction_status_in_list with error message."""
    transactions = [{"id": "1", "STATUS": "PENDING"}]
    
    fs_ops.update_transaction_status_in_list(
        transactions, "1", fs_ops.TransactionStatus.FAILED,
        error_message="Test error"
    )
    
    assert transactions[0]["STATUS"] == "FAILED"
    assert transactions[0]["ERROR_MESSAGE"] == "Test error"


# Test replace_logic uncovered lines

def test_log_message_with_module_logger():
    """Test _log_message using module logger."""
    # Set the module logger
    replace._MODULE_LOGGER = Mock()
    
    replace._log_message(logging.INFO, "Test message")
    replace._MODULE_LOGGER.log.assert_called_once_with(logging.INFO, "Test message")
    
    # Clean up
    replace._MODULE_LOGGER = None


def test_log_message_debug_with_logger():
    """Test _log_message in debug mode with both stderr and logger."""
    original = replace._DEBUG_REPLACE_LOGIC
    replace._DEBUG_REPLACE_LOGIC = True
    
    mock_logger = Mock()
    
    try:
        import io
        old_stderr = sys.stderr
        sys.stderr = io.StringIO()
        
        replace._log_message(logging.DEBUG, "Debug test", logger=mock_logger)
        
        stderr_output = sys.stderr.getvalue()
        assert "RL_DBG_STDERR: Debug test" in stderr_output
        mock_logger.debug.assert_called_once_with("Debug test")
        
        sys.stderr = old_stderr
    finally:
        replace._DEBUG_REPLACE_LOGIC = original


def test_log_message_warning_level():
    """Test _log_message with WARNING level and no logger."""
    import io
    old_stderr = sys.stderr
    
    try:
        sys.stderr = io.StringIO()
        
        replace._log_message(logging.WARNING, "Warning message", logger=None)
        assert "WARNING: Warning message" in sys.stderr.getvalue()
        
    finally:
        sys.stderr = old_stderr


def test_strip_control_characters_with_controls():
    """Test strip_control_characters with actual control characters."""
    # Test with various control characters
    text = "Hello\x00\x01\x02World\x1f\x7f"
    result = replace.strip_control_characters(text)
    assert result == "HelloWorld"
    
    # Test with newlines and tabs (should be preserved)
    text2 = "Hello\nWorld\tTest"
    result2 = replace.strip_control_characters(text2)
    assert result2 == "Hello\nWorld\tTest"


def test_load_replacement_map_success(tmp_path):
    """Test successful load_replacement_map."""
    mapping_file = tmp_path / "mapping.json"
    mapping = {
        "REPLACEMENT_MAPPING": {
            "OldName": "NewName",
            "old_function": "new_function"
        }
    }
    mapping_file.write_text(json.dumps(mapping))
    
    result = replace.load_replacement_map(mapping_file)
    assert result == True
    assert replace.get_mapping_size() == 2


def test_load_replacement_map_recursive_detection(tmp_path):
    """Test load_replacement_map with recursive mapping."""
    mapping_file = tmp_path / "mapping.json"
    mapping = {
        "REPLACEMENT_MAPPING": {
            "A": "B",
            "B": "C",
            "C": "A"  # Creates a cycle
        }
    }
    mapping_file.write_text(json.dumps(mapping))
    
    result = replace.load_replacement_map(mapping_file)
    assert result == False


def test_load_replacement_map_json_error(tmp_path):
    """Test load_replacement_map with JSON decode error."""
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text("invalid json {")
    
    result = replace.load_replacement_map(mapping_file)
    assert result == False


def test_load_replacement_map_not_dict(tmp_path):
    """Test load_replacement_map when REPLACEMENT_MAPPING is not a dict."""
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": ["not", "a", "dict"]}')
    
    result = replace.load_replacement_map(mapping_file)
    assert result == False


def test_load_replacement_map_os_error(tmp_path):
    """Test load_replacement_map with OS error."""
    with patch('pathlib.Path.open', side_effect=OSError("Permission denied")):
        result = replace.load_replacement_map(Path("/fake/path"))
        assert result == False


def test_get_scan_pattern_with_mapping():
    """Test get_scan_pattern after loading mapping."""
    # First reset and load a mapping
    replace.reset_module_state()
    replace._REPLACEMENT_MAPPING = {"test": "replacement"}
    replace._prepare_internal_structures()
    
    pattern = replace.get_scan_pattern()
    assert pattern is not None


def test_replace_occurrences_basic():
    """Test replace_occurrences with basic replacement."""
    # Set up mapping
    replace.reset_module_state()
    replace._REPLACEMENT_MAPPING = {"old": "new"}
    replace._prepare_internal_structures()
    
    text = "This is old text with old words"
    result = replace.replace_occurrences(text)
    assert result == "This is new text with new words"


def test_replace_occurrences_case_sensitive():
    """Test replace_occurrences preserves case."""
    replace.reset_module_state()
    replace._REPLACEMENT_MAPPING = {"test": "replacement"}
    replace._prepare_internal_structures()
    
    text = "Test TEST test"
    result = replace.replace_occurrences(text)
    assert result == "Replacement REPLACEMENT replacement"


def test_replace_occurrences_with_diacritics():
    """Test replace_occurrences with diacritics."""
    replace.reset_module_state()
    replace._REPLACEMENT_MAPPING = {"cafe": "restaurant"}
    replace._prepare_internal_structures()
    
    # café should match cafe
    text = "Let's go to the café"
    result = replace.replace_occurrences(text)
    assert result == "Let's go to the restaurant"


# Test main_flow additional edge cases

def test_main_flow_user_declines_resume(tmp_path, monkeypatch):
    """Test when user declines to resume."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    
    # Create existing transaction file
    trans_file = test_dir / mfr.MAIN_TRANSACTION_FILE_NAME
    trans_file.write_text(json.dumps([
        {"STATUS": "COMPLETED", "id": "1", "TYPE": "FILE_RENAME", "PATH": "test.txt"},
        {"STATUS": "PENDING", "id": "2", "TYPE": "FILE_RENAME", "PATH": "test2.txt"}
    ]))
    
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
    
    # User says no to resume, then yes to proceed
    inputs = iter(['n', 'y'])
    monkeypatch.setattr('builtins.input', lambda _: next(inputs))
    
    with patch('mass_find_replace.file_system_operations.scan_directory_for_occurrences', return_value=[]):
        mfr.main_flow(
            directory=str(test_dir),
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
            interactive_mode=False
        )
    
    # Transaction file should be deleted
    assert not trans_file.exists()


def test_main_flow_clear_transaction_error(tmp_path, monkeypatch):
    """Test when clearing transaction file fails."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    
    trans_file = test_dir / mfr.MAIN_TRANSACTION_FILE_NAME
    trans_file.write_text(json.dumps([{"STATUS": "PENDING"}]))
    
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
    
    # User says no to resume
    monkeypatch.setattr('builtins.input', lambda _: 'n')
    
    # Mock unlink to fail
    with patch.object(Path, 'unlink', side_effect=Exception("Delete failed")):
        mfr.main_flow(
            directory=str(test_dir),
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
            interactive_mode=False
        )


def test_main_flow_skip_scan_no_transaction_file(tmp_path):
    """Test skip_scan when transaction file doesn't exist."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
    
    mfr.main_flow(
        directory=str(test_dir),
        mapping_file=str(mapping_file),
        extensions=None,
        exclude_dirs=[],
        exclude_files=[],
        dry_run=False,
        skip_scan=True,
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
        interactive_mode=False
    )


def test_main_flow_resume_dry_run(tmp_path):
    """Test resume with dry_run forces rescan."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    
    # Create transaction file
    trans_file = test_dir / mfr.MAIN_TRANSACTION_FILE_NAME
    trans_file.write_text(json.dumps([
        {"id": "1", "TYPE": "FILE_RENAME", "PATH": "test.txt", "STATUS": "COMPLETED"}
    ]))
    
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
    
    with patch('mass_find_replace.file_system_operations.scan_directory_for_occurrences', return_value=[]) as mock_scan:
        mfr.main_flow(
            directory=str(test_dir),
            mapping_file=str(mapping_file),
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=True,
            skip_scan=False,
            resume=True,
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
            interactive_mode=False
        )
        
        # Check that paths_to_force_rescan was None (rescan all)
        args, kwargs = mock_scan.call_args
        assert kwargs.get('paths_to_force_rescan') is None


def test_main_flow_resume_load_error(tmp_path):
    """Test resume when transaction file can't be loaded."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    
    # Create invalid transaction file
    trans_file = test_dir / mfr.MAIN_TRANSACTION_FILE_NAME
    trans_file.write_text("invalid json")
    
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
    
    with patch('mass_find_replace.file_system_operations.scan_directory_for_occurrences', return_value=[]):
        mfr.main_flow(
            directory=str(test_dir),
            mapping_file=str(mapping_file),
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=False,
            skip_scan=False,
            resume=True,
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
            interactive_mode=False
        )


def test_main_flow_resume_empty_transactions(tmp_path):
    """Test resume when transaction file is empty."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    
    trans_file = test_dir / mfr.MAIN_TRANSACTION_FILE_NAME
    trans_file.write_text("[]")
    
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
    
    with patch('mass_find_replace.file_system_operations.scan_directory_for_occurrences', return_value=[]):
        mfr.main_flow(
            directory=str(test_dir),
            mapping_file=str(mapping_file),
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=False,
            skip_scan=False,
            resume=True,
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
            interactive_mode=False
        )


def test_main_flow_resume_check_modified_files(tmp_path):
    """Test resume checking for modified files."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    
    # Create a test file
    test_file = test_dir / "modified.txt"
    test_file.write_text("content")
    
    # Create transaction file with timestamp
    current_time = time.time()
    trans_file = test_dir / mfr.MAIN_TRANSACTION_FILE_NAME
    trans_file.write_text(json.dumps([{
        "id": "1",
        "TYPE": "FILE_CONTENT",
        "PATH": "modified.txt",
        "STATUS": "COMPLETED",
        "timestamp_processed": current_time - 100  # 100 seconds ago
    }]))
    
    # Touch the file to make it newer
    test_file.touch()
    
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
    
    with patch('mass_find_replace.file_system_operations.scan_directory_for_occurrences', return_value=[]) as mock_scan:
        mfr.main_flow(
            directory=str(test_dir),
            mapping_file=str(mapping_file),
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=False,
            skip_scan=False,
            resume=True,
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
            interactive_mode=False
        )
        
        # Check that the file was marked for rescan
        args, kwargs = mock_scan.call_args
        paths_to_rescan = kwargs.get('paths_to_force_rescan')
        assert paths_to_rescan is not None
        assert 'modified.txt' in paths_to_rescan


def test_main_flow_resume_file_stat_error(tmp_path):
    """Test resume when file stat fails."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    
    trans_file = test_dir / mfr.MAIN_TRANSACTION_FILE_NAME
    trans_file.write_text(json.dumps([{
        "id": "1",
        "TYPE": "FILE_CONTENT",
        "PATH": "test.txt",
        "STATUS": "COMPLETED",
        "timestamp_processed": time.time()
    }]))
    
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
    
    # Mock stat to fail
    with patch('pathlib.Path.stat', side_effect=OSError("Stat failed")):
        with patch('mass_find_replace.file_system_operations.scan_directory_for_occurrences', return_value=[]):
            mfr.main_flow(
                directory=str(test_dir),
                mapping_file=str(mapping_file),
                extensions=None,
                exclude_dirs=[],
                exclude_files=[],
                dry_run=False,
                skip_scan=False,
                resume=True,
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
                interactive_mode=False
            )


def test_main_flow_resume_unexpected_error(tmp_path):
    """Test resume with unexpected error during file check."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    
    trans_file = test_dir / mfr.MAIN_TRANSACTION_FILE_NAME
    trans_file.write_text(json.dumps([{
        "id": "1",
        "TYPE": "FILE_CONTENT",
        "PATH": "test.txt",
        "STATUS": "COMPLETED",
        "timestamp_processed": time.time()
    }]))
    
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
    
    # Mock rglob to raise unexpected error
    with patch.object(Path, 'rglob', side_effect=Exception("Unexpected error")):
        with patch('mass_find_replace.file_system_operations.scan_directory_for_occurrences', return_value=[]):
            mfr.main_flow(
                directory=str(test_dir),
                mapping_file=str(mapping_file),
                extensions=None,
                exclude_dirs=[],
                exclude_files=[],
                dry_run=False,
                skip_scan=False,
                resume=True,
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
                interactive_mode=False
            )


def test_main_flow_reset_dry_run_transactions(tmp_path):
    """Test resetting DRY_RUN completed transactions."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    
    trans_file = test_dir / mfr.MAIN_TRANSACTION_FILE_NAME
    trans_file.write_text(json.dumps([{
        "id": "1",
        "TYPE": "FILE_RENAME",
        "PATH": "test.txt",
        "STATUS": "COMPLETED",
        "ERROR_MESSAGE": "DRY_RUN"
    }]))
    
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')
    
    with patch('mass_find_replace.file_system_operations.execute_all_transactions', return_value={}) as mock_exec:
        mfr.main_flow(
            directory=str(test_dir),
            mapping_file=str(mapping_file),
            extensions=None,
            exclude_dirs=[],
            exclude_files=[],
            dry_run=False,
            skip_scan=True,
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
            interactive_mode=False
        )
        
        # Transaction should have been reset to PENDING
        mock_exec.assert_called_once()


def test_cli_small_timeout_warning(monkeypatch):
    """Test CLI warning when timeout adjusted to minimum."""
    monkeypatch.setattr('sys.argv', ['mfr', '.', '--timeout', '0.1'])
    
    mapping_file = "replacement_mapping.json"
    with open(mapping_file, 'w') as f:
        f.write('{"REPLACEMENT_MAPPING": {}}')
    
    try:
        with patch('mass_find_replace.file_system_operations.scan_directory_for_occurrences', return_value=[]):
            mfr.main_cli()
    finally:
        if os.path.exists(mapping_file):
            os.remove(mapping_file)