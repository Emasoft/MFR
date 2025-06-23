#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Edge case tests to improve code coverage."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, Mock
import pytest

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from mass_find_replace import mass_find_replace
from mass_find_replace import file_system_operations
from mass_find_replace import replace_logic


def test_main_flow_directory_errors(tmp_path):
    """Test main_flow with various directory errors."""
    # Test non-existent directory
    result = mass_find_replace.main_flow("/nonexistent/path", dry_run=True)
    assert result == 1
    
    # Test file instead of directory
    test_file = tmp_path / "file.txt"
    test_file.write_text("content")
    result = mass_find_replace.main_flow(str(test_file), dry_run=True)
    assert result == 1
    
    # Test empty directory
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    result = mass_find_replace.main_flow(str(empty_dir), dry_run=True)
    assert result == 1


def test_main_flow_all_skipped(tmp_path):
    """Test main_flow when all operations are skipped."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    
    result = mass_find_replace.main_flow(
        str(test_dir),
        dry_run=True,
        skip_file_renaming=True,
        skip_folder_renaming=True,
        skip_content=True
    )
    assert result == 1


def test_replace_logic_edge_cases():
    """Test replace_logic edge cases."""
    # Test with non-string inputs
    assert replace_logic.strip_diacritics(123) == 123
    assert replace_logic.strip_control_characters(None) is None
    
    # Test with empty mapping
    assert replace_logic.get_mapping_size() == 0
    
    # Test get_key_characters with no mapping
    chars = replace_logic.get_key_characters()
    assert chars == set()


def test_file_operations_edge_cases(tmp_path):
    """Test file_system_operations edge cases."""
    # Test encoding detection with empty file
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("")
    encoding = file_system_operations.get_file_encoding(str(empty_file))
    assert encoding == "utf-8"
    
    # Test load_transactions with missing file
    transactions = file_system_operations.load_transactions("/nonexistent.json")
    assert transactions == []
    
    # Test load_ignore_patterns with missing file
    patterns = file_system_operations.load_ignore_patterns("/nonexistent/.gitignore")
    assert patterns is None


def test_subprocess_command():
    """Test _run_subprocess_command."""
    with patch('subprocess.run') as mock_run:
        # Success case
        mock_run.return_value = Mock(returncode=0, stdout="OK", stderr="")
        result = mass_find_replace._run_subprocess_command(["echo", "test"], "Test")
        assert result is True
        
        # Failure case
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error")
        result = mass_find_replace._run_subprocess_command(["false"], "Test")
        assert result is False
        
        # Exception case
        mock_run.side_effect = FileNotFoundError()
        result = mass_find_replace._run_subprocess_command(["missing"], "Test")
        assert result is False


def test_cli_self_test():
    """Test CLI self-test functionality."""
    with patch('sys.argv', ['mfr', '--self-test']):
        with patch('mass_find_replace.mass_find_replace._run_subprocess_command') as mock_run:
            # Test successful self-test
            mock_run.return_value = True
            result = mass_find_replace.main_cli()
            assert result == 0
            
            # Test pip fallback
            mock_run.side_effect = [False, True]  # uv fails, pip succeeds
            result = mass_find_replace.main_cli()
            assert result == 0
            
            # Test all fail
            mock_run.return_value = False
            result = mass_find_replace.main_cli()
            assert result == 1


def test_invalid_cli_args():
    """Test CLI with invalid arguments."""
    # Test invalid timeout
    with patch('sys.argv', ['mfr', '.', '--timeout', '-1']):
        with pytest.raises(SystemExit) as exc:
            mass_find_replace.main_cli()
        assert exc.value.code == 2


def test_load_replacement_map_errors(tmp_path):
    """Test load_replacement_map error cases."""
    # File not found
    result = replace_logic.load_replacement_map("/nonexistent/map.json")
    assert result is None
    
    # Invalid JSON
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("not json")
    result = replace_logic.load_replacement_map(str(bad_json))
    assert result is None
    
    # Missing REPLACEMENT_MAPPING key
    wrong_key = tmp_path / "wrong.json"
    wrong_key.write_text('{"wrong": {}}')
    result = replace_logic.load_replacement_map(str(wrong_key))
    assert result is None
    
    # REPLACEMENT_MAPPING not a dict
    not_dict = tmp_path / "notdict.json"
    not_dict.write_text('{"REPLACEMENT_MAPPING": "string"}')
    result = replace_logic.load_replacement_map(str(not_dict))
    assert result is None
    
    # Empty mapping
    empty_map = tmp_path / "empty.json"
    empty_map.write_text('{"REPLACEMENT_MAPPING": {}}')
    result = replace_logic.load_replacement_map(str(empty_map))
    assert result == {}
    
    # Recursive mapping
    recursive = tmp_path / "recursive.json"
    recursive.write_text('{"REPLACEMENT_MAPPING": {"a": "b", "b": "a"}}')
    result = replace_logic.load_replacement_map(str(recursive))
    assert result is None


def test_print_mapping_table():
    """Test _print_mapping_table."""
    mock_logger = Mock()
    
    # Empty mapping
    mass_find_replace._print_mapping_table({}, mock_logger)
    mock_logger.info.assert_called_with("Replacement mapping is empty.")
    
    # With data
    mock_logger.reset_mock()
    mass_find_replace._print_mapping_table({"old": "new"}, mock_logger)
    assert mock_logger.info.call_count > 3  # Table has multiple lines


def test_get_operation_description():
    """Test _get_operation_description."""
    # All operations
    desc = mass_find_replace._get_operation_description(False, False, False)
    assert desc == "file names, folder names, and file contents"
    
    # Only files
    desc = mass_find_replace._get_operation_description(False, True, True)
    assert desc == "file names"
    
    # Only folders
    desc = mass_find_replace._get_operation_description(True, False, True)
    assert desc == "folder names"
    
    # Only content
    desc = mass_find_replace._get_operation_description(True, True, False)
    assert desc == "file contents"
    
    # Nothing
    desc = mass_find_replace._get_operation_description(True, True, True)
    assert desc == "nothing (all operations skipped)"


def test_check_existing_transactions(tmp_path):
    """Test _check_existing_transactions."""
    # No file
    has_existing, progress = mass_find_replace._check_existing_transactions("/nonexistent.json")
    assert not has_existing
    assert progress == 0
    
    # With transactions
    trans_file = tmp_path / "trans.json"
    trans_file.write_text(json.dumps([
        {"status": "COMPLETED"},
        {"status": "PENDING"},
        {"status": "COMPLETED"},
        {"status": "FAILED"}
    ]))
    has_existing, progress = mass_find_replace._check_existing_transactions(str(trans_file))
    assert has_existing
    assert progress == 50  # 2/4 completed


def test_log_functions(capsys):
    """Test logging functions."""
    # Test file_system_operations._log_fs_op_message
    file_system_operations._log_fs_op_message("Test message")
    captured = capsys.readouterr()
    assert "INFO: Test message" in captured.out
    
    # Test replace_logic._log_message
    replace_logic._log_message("Test message")
    captured = capsys.readouterr()
    assert "[INFO] Test message" in captured.out


def test_transaction_update_not_found():
    """Test updating transaction that doesn't exist."""
    transactions = [{"id": "123", "status": "PENDING"}]
    file_system_operations.update_transaction_status_in_list(
        transactions, "456", file_system_operations.TransactionStatus.COMPLETED
    )
    # Should not crash, just log warning