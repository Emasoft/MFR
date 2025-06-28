#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE CODE:
# - Added shebang and encoding header as per project requirements
# - Added proper type annotations for all functions
# - Fixed dict type annotation to use modern Python 3.10+ syntax
# - Added return type annotations for all functions
# - Added license header
#

# Copyright (c) 2024 Emasoft
#
# This software is licensed under the MIT License.
# Refer to the LICENSE file for more details.

"""
Pytest configuration and fixtures for Mass Find Replace tests.
"""

import pytest
from pathlib import Path
import json
import shutil
from typing import Any, Callable, Generator, Tuple
import sys
import logging
import os


@pytest.fixture
def temp_test_dir(tmp_path: Path) -> Generator[dict[str, Path], None, None]:
    """Fixture that creates separate config and runtime directories for testing.
    Verify that the directory structure is correct.
    Ensures virtual directory tree for consistent transaction counts"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(exist_ok=True)

    # Create sample directories and files in runtime directory
    (runtime_dir / "oldname_root").mkdir()
    (runtime_dir / "oldname_root" / "sub_oldname_folder").mkdir()
    (runtime_dir / "oldname_root" / "sub_oldname_folder" / "another_OLDNAME_dir").mkdir()
    deep_file = runtime_dir / "oldname_root" / "sub_oldname_folder" / "another_OLDNAME_dir" / "deep_oldname_file.txt"
    deep_file.write_text("This file contains OLDNAME multiple times: Oldname oldName")

    # Create excluded items in runtime directory
    (runtime_dir / "excluded_oldname_dir").mkdir()
    (runtime_dir / "excluded_oldname_dir" / "excluded_file.txt").write_text("OLDNAME content")
    (runtime_dir / "exclude_this_oldname_file.txt").write_text("Oldname exclusion test")

    # Verify structure
    assert (runtime_dir / "oldname_root").exists(), "Required dir not created in fixture"
    context = {"runtime": runtime_dir, "config": config_dir}
    yield context

    # Cleanup - handle Windows read-only files
    def handle_remove_readonly(func: Callable[..., Any], path: str, exc_info: Tuple[type[BaseException], BaseException, Any]) -> None:
        """Error handler for Windows readonly files."""
        import stat
        import os

        if os.name == "nt":  # Windows
            os.chmod(path, stat.S_IWRITE)
            func(path)
        else:
            raise exc_info[1]

    shutil.rmtree(tmp_path, onerror=handle_remove_readonly)


@pytest.fixture
def default_map_file(temp_test_dir: dict[str, Path]) -> Path:
    """
    Create the default replacement mapping file in config directory.
    """
    config_dir = temp_test_dir["config"]
    map_file = config_dir / "replacement_mapping.json"

    # Create and populate replacement mapping file
    map_data = {
        "REPLACEMENT_MAPPING": {
            "oldname": "newname",
            "Oldname": "Newname",
            "oldName": "newName",
            "OldName": "NewName",
            "OLDNAME": "NEWNAME",
        }
    }
    map_file.write_text(json.dumps(map_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return map_file


@pytest.fixture
def assert_file_content() -> Callable[[Path, str], None]:
    """Fixture that provides a helper function to validate file content."""

    def _assert(file_path: Path, expected_content: str) -> None:
        """Helper to validate file content with readable diffs"""
        actual = file_path.read_text(encoding="utf-8")
        assert actual == expected_content, f"Content mismatch in {file_path}: Expected {expected_content!r}, got {actual!r}"

    return _assert


@pytest.fixture(autouse=True, scope="session")
def disable_prefect_rich_output():
    """Disable Prefect's Rich console output to avoid 'I/O operation on closed file' errors."""
    # Disable Rich output in Prefect during tests
    os.environ["PREFECT__LOGGING__ENABLE_RICH_LOGS"] = "false"
    os.environ["PREFECT_LOGGING_ENABLE_RICH_LOGS"] = "false"

    # Disable Prefect's server communication during tests
    os.environ["PREFECT__TESTING_MODE"] = "true"
    os.environ["PREFECT__SERVER__ANALYTICS_ENABLED"] = "false"
    os.environ["PREFECT__TELEMETRY__ENABLED"] = "false"

    # Use simpler logging
    os.environ["PREFECT__LOGGING__LEVEL"] = "WARNING"
    os.environ["PREFECT__LOGGING__COLORS"] = "false"

    # Also disable ANSI colors
    os.environ["NO_COLOR"] = "1"

    yield

    # Cleanup is not needed as environment variables are process-local


@pytest.fixture(autouse=True)
def cleanup_logging_handlers():
    """Clean up logging handlers after each test to avoid file handle issues."""
    yield

    # After each test, ensure all handlers are properly closed
    try:
        # Force garbage collection to clean up any remaining objects
        import gc

        gc.collect()

        # Get all loggers and clean them up
        for logger_name in list(logging.Logger.manager.loggerDict.keys()):
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers[:]:
                try:
                    handler.flush()
                    handler.close()
                except Exception:
                    pass  # Ignore any errors
                logger.removeHandler(handler)

        # Clean root logger as well
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            try:
                handler.flush()
                handler.close()
            except Exception:
                pass
    except Exception:
        pass  # Ignore any errors during cleanup
