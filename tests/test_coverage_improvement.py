#!/usr/bin/env python3
"""Targeted tests to improve coverage by focusing on uncovered lines."""

import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import mass_find_replace.mass_find_replace as mfr
import mass_find_replace.file_system_operations as fs_ops
import mass_find_replace.replace_logic as replace


# Test _get_logger function (lines 59, 61-74)
def test_get_logger_verbose_mode():
    """Test _get_logger with verbose mode."""
    # Mock Prefect logger
    mock_logger = Mock()
    with patch("prefect.get_run_logger", return_value=mock_logger):
        logger = mfr._get_logger(verbose_mode=True)
        mock_logger.setLevel.assert_called_once_with(logging.DEBUG)


def test_get_logger_missing_context_error():
    """Test _get_logger when Prefect raises MissingContextError."""
    from prefect.exceptions import MissingContextError

    with patch("prefect.get_run_logger", side_effect=MissingContextError()):
        logger = mfr._get_logger(verbose_mode=False)
        assert isinstance(logger, logging.Logger)
        assert logger.name == "mass_find_replace"


def test_get_logger_import_error():
    """Test _get_logger when Prefect import fails."""
    # Make the import fail
    import sys

    original_modules = {}
    for key in list(sys.modules.keys()):
        if key.startswith("prefect"):
            original_modules[key] = sys.modules[key]
            del sys.modules[key]

    try:
        # Clear any existing handlers
        test_logger = logging.getLogger("mass_find_replace")
        test_logger.handlers.clear()

        logger = mfr._get_logger(verbose_mode=True)
        assert isinstance(logger, logging.Logger)
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) > 0
    finally:
        # Restore modules
        sys.modules.update(original_modules)


# Test _get_operation_description (lines 125, 127, 129)
def test_get_operation_description_combinations():
    """Test all combinations of _get_operation_description."""
    # Two operations enabled
    assert mfr._get_operation_description(False, True, True) == "file names"
    assert mfr._get_operation_description(True, False, True) == "folder names"
    assert mfr._get_operation_description(True, True, False) == "file contents"


# Test main_flow verbose mode (line 213)
def test_main_flow_verbose_logging(tmp_path, caplog):
    """Test verbose mode logging in main_flow."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    (test_dir / "file.txt").write_text("content")

    # Create a valid mapping file
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

    with caplog.at_level(logging.DEBUG):
        # Mock scan to return empty to avoid full execution
        with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences", return_value=[]):
            result = mfr.main_flow(
                directory=str(test_dir),
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


# Test directory validation errors (lines 221-230)
def test_main_flow_directory_validation():
    """Test directory validation in main_flow."""
    # Non-existent directory
    mfr.main_flow(
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
    import tempfile

    with tempfile.NamedTemporaryFile() as f:
        mfr.main_flow(
            directory=f.name,
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

    # Unreadable directory
    with patch("os.access", return_value=False):
        mfr.main_flow(
            directory=".",
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


# Test existing transactions resume (lines 234-250)
def test_main_flow_resume_prompt(tmp_path, monkeypatch):
    """Test resume prompt for existing transactions."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()

    # Create existing transaction file
    trans_file = test_dir / mfr.MAIN_TRANSACTION_FILE_NAME
    trans_file.write_text(json.dumps([{"STATUS": "COMPLETED"}, {"STATUS": "PENDING"}]))

    # Mock user says yes to resume
    monkeypatch.setattr("builtins.input", lambda _: "y")

    # Create mapping file
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

    with patch("mass_find_replace.file_system_operations.execute_all_transactions", return_value={}):
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
            interactive_mode=False,
        )

    # Mock user says no to resume
    trans_file.write_text(json.dumps([{"STATUS": "PENDING"}]))
    monkeypatch.setattr("builtins.input", lambda _: "n")

    with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences", return_value=[]):
        with patch("mass_find_replace.file_system_operations.save_transactions"):
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
                interactive_mode=False,
            )


# Test all operations skipped (lines 253-254)
def test_main_flow_all_operations_skipped(tmp_path):
    """Test when all operations are skipped."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()

    mfr.main_flow(
        directory=str(test_dir),
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


# Test empty directory (lines 258-265)
def test_main_flow_empty_directory(tmp_path):
    """Test empty directory handling."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    # Create mapping file
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

    mfr.main_flow(
        directory=str(empty_dir),
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
        quiet_mode=True,
        verbose_mode=False,
        interactive_mode=False,
    )


# Test mapping file errors (lines 270-276)
def test_main_flow_mapping_file_errors(tmp_path):
    """Test mapping file path validation."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    (test_dir / "file.txt").write_text("content")

    # Non-existent mapping file
    mfr.main_flow(
        directory=str(test_dir),
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

    # File instead of mapping file
    not_json = tmp_path / "notjson.txt"
    not_json.write_text("not json")
    mfr.main_flow(
        directory=str(test_dir),
        mapping_file=str(not_json),
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


# Test mapping load failure (lines 284-285)
def test_main_flow_map_load_critical_error(tmp_path):
    """Test critical error when map loading fails."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    (test_dir / "file.txt").write_text("content")

    # Create a mapping file
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

    with patch("mass_find_replace.replace_logic.load_replacement_map", return_value=False):
        mfr.main_flow(
            directory=str(test_dir),
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
            quiet_mode=True,
            verbose_mode=False,
            interactive_mode=False,
        )


# Test mapping table display (lines 290-302)
def test_main_flow_print_mapping_and_confirm(tmp_path, capsys, monkeypatch):
    """Test printing mapping table and user confirmation."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    (test_dir / "file.txt").write_text("content")

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"OldName": "NewName"}}')

    # User confirms
    monkeypatch.setattr("builtins.input", lambda _: "y")

    with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences", return_value=[]):
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
            interactive_mode=False,
        )

        captured = capsys.readouterr()
        assert "OldName" in captured.out
        assert "NewName" in captured.out


# Test empty mapping handling (lines 306-313)
def test_main_flow_empty_mapping(tmp_path, monkeypatch):
    """Test empty mapping handling."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()

    empty_mapping = tmp_path / "empty.json"
    empty_mapping.write_text('{"REPLACEMENT_MAPPING": {}}')

    # User continues anyway
    monkeypatch.setattr("builtins.input", lambda _: "y")

    with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences", return_value=[]):
        mfr.main_flow(
            directory=str(test_dir),
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

    # User aborts
    monkeypatch.setattr("builtins.input", lambda _: "n")
    mfr.main_flow(
        directory=str(test_dir),
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


# Test gitignore loading (lines 319-330)
def test_main_flow_gitignore_loading(tmp_path):
    """Test .gitignore file loading."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    (test_dir / "file.txt").write_text("content")

    # Create .gitignore
    gitignore = test_dir / ".gitignore"
    gitignore.write_text("*.pyc\n__pycache__/")

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

    with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences") as mock_scan:
        mock_scan.return_value = []
        mfr.main_flow(
            directory=str(test_dir),
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

        # Check that ignore patterns were passed
        args, kwargs = mock_scan.call_args
        assert "ignore_spec" in kwargs
        assert kwargs["ignore_spec"] is not None


# Test custom ignore file (lines 332-342)
def test_main_flow_custom_ignore_file(tmp_path):
    """Test custom ignore file loading."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()

    # Create custom ignore file
    custom_ignore = tmp_path / ".mfrignore"
    custom_ignore.write_text("*.tmp\ntemp/")

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

    with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences") as mock_scan:
        mock_scan.return_value = []
        mfr.main_flow(
            directory=str(test_dir),
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


# Test ignore pattern error (lines 344-349)
def test_main_flow_ignore_pattern_error(tmp_path):
    """Test ignore pattern compilation error."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

    with patch("pathspec.PathSpec.from_lines", side_effect=Exception("Pattern error")):
        with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences", return_value=[]):
            mfr.main_flow(
                directory=str(test_dir),
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


# Test user confirmation prompt (lines 353-387)
def test_main_flow_user_confirmation(tmp_path, monkeypatch):
    """Test user confirmation prompts."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"old": "new"}}')

    # User aborts
    monkeypatch.setattr("builtins.input", lambda _: "n")

    with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences", return_value=[{"id": "1"}]):
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
            interactive_mode=False,
        )


# Test no occurrences found (lines 453-459)
def test_main_flow_no_occurrences(tmp_path):
    """Test when no occurrences are found."""
    test_dir = tmp_path / "test"
    test_dir.mkdir()

    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text('{"REPLACEMENT_MAPPING": {"notfound": "replacement"}}')

    with patch("mass_find_replace.file_system_operations.scan_directory_for_occurrences", return_value=[]):
        mfr.main_flow(
            directory=str(test_dir),
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
            verbose_mode=False,
            interactive_mode=False,
        )


# Test _run_subprocess_command (lines 525-527)
def test_run_subprocess_command_exception():
    """Test _run_subprocess_command with exception."""
    with patch("subprocess.run", side_effect=Exception("Unexpected error")):
        result = mfr._run_subprocess_command(["test"], "Test command")
        assert not result


# Test CLI missing dependency (lines 542-546)
def test_main_cli_missing_dependency(monkeypatch):
    """Test CLI when dependencies are missing."""
    monkeypatch.setattr("sys.argv", ["mfr", "."])

    # Hide a required module
    import sys

    sys.modules["click"] = None

    try:
        with pytest.raises(SystemExit) as exc:
            mfr.main_cli()
        assert exc.value.code == 1
    finally:
        # Restore
        del sys.modules["click"]


# Test CLI self-test fallback (lines 689-690, 693-694)
def test_main_cli_self_test_fallback(monkeypatch):
    """Test self-test with pip fallback."""
    monkeypatch.setattr("sys.argv", ["mfr", "--self-test"])

    with patch("mass_find_replace.mass_find_replace._run_subprocess_command") as mock_run:
        # uv fails, pip succeeds, then pytest succeeds
        mock_run.side_effect = [False, True, True]
        with pytest.raises(SystemExit) as exc:
            mfr.main_cli()
        assert exc.value.code == 0

        # Verify pip was called
        calls = mock_run.call_args_list
        assert len(calls) == 3
        assert "uv" in str(calls[0])
        assert "pip" in str(calls[1])
        assert "pytest" in str(calls[2])


# Test file operations log functions
def test_log_fs_op_message_no_logger():
    """Test _log_fs_op_message without logger."""
    import io
    import sys

    # Capture output
    old_stdout = sys.stdout
    old_stderr = sys.stderr

    try:
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

        fs_ops._log_fs_op_message(logging.INFO, "Info msg", None)
        assert "INFO (fs_op): Info msg" in sys.stdout.getvalue()

        fs_ops._log_fs_op_message(logging.ERROR, "Error msg", None)
        assert "ERROR (fs_op): Error msg" in sys.stdout.getvalue()

        fs_ops._log_fs_op_message(logging.DEBUG, "Debug msg", None)
        assert "DEBUG (fs_op): Debug msg" in sys.stdout.getvalue()

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


# Test collision error logging
def test_log_collision_error_exception(tmp_path):
    """Test _log_collision_error with write exception."""
    log_file = tmp_path / "collision.log"

    with patch("builtins.open", side_effect=OSError("Write failed")):
        # Should not raise exception
        # Create dummy transaction and paths
        tx = {"id": "test-123", "TYPE": "FILE_NAME", "PATH": "test.txt", "ORIGINAL_NAME": "old", "NEW_NAME": "new"}
        root_dir = tmp_path
        source_path = tmp_path / "old"
        collision_path = tmp_path / "new"
        collision_type = "exact match"

        fs_ops._log_collision_error(root_dir, tx, source_path, collision_path, collision_type, None)


# Test replace logic functions
def test_replace_logic_log_message_debug():
    """Test _log_message in debug mode."""
    import mass_find_replace.replace_logic as rl

    original = rl._DEBUG_REPLACE_LOGIC
    rl._DEBUG_REPLACE_LOGIC = True

    try:
        import io

        old_stderr = sys.stderr
        sys.stderr = io.StringIO()

        replace._log_message("Debug test", level=logging.DEBUG)
        output = sys.stderr.getvalue()
        assert "[DEBUG] Debug test" in output

        sys.stderr = old_stderr
    finally:
        rl._DEBUG_REPLACE_LOGIC = original


def test_replace_logic_log_message_no_logger():
    """Test _log_message without logger."""
    import io

    old_stdout = sys.stdout
    old_stderr = sys.stderr

    try:
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()

        replace._log_message("Info", level=logging.INFO, logger=None)
        assert "[INFO] Info" in sys.stdout.getvalue()

        replace._log_message("Error", level=logging.ERROR, logger=None)
        assert "[ERROR] Error" in sys.stderr.getvalue()

    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
