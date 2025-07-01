#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Created simplified binary file test to verify core functionality
#

"""
Simplified test for binary file handling in Mass Find Replace.

This test focuses on the core binary file detection and logging functionality
without the complexity of the full test fixture setup.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import json
import pytest

from mass_find_replace.mass_find_replace import main_flow
from mass_find_replace.core.constants import BINARY_MATCHES_LOG_FILE
from mass_find_replace import replace_logic


@pytest.fixture(autouse=True)
def reset_replace_logic():
    """Reset replace_logic module state between tests."""
    replace_logic.reset_module_state()
    yield


def test_binary_file_logging_simple():
    """Test that binary files with patterns are logged correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_dir = Path(tmpdir)

        # Create mapping file
        map_file = test_dir / "mapping.json"
        map_data = {
            "REPLACEMENT_MAPPING": {
                "OLDNAME": "NEWNAME",
                "oldName": "newName",
                "Oldname": "Newname",
            }
        }
        map_file.write_text(json.dumps(map_data))

        # Create binary file with patterns
        bin_file = test_dir / "data.bin"
        bin_file.write_bytes(b"HeaderOLDNAME\x00\x01MiddleoldName\x02FooterOldname\xff")

        # Create text file for comparison
        txt_file = test_dir / "data.txt"
        txt_file.write_text("HeaderOLDNAME MiddleoldName FooterOldname")

        # Run main flow
        main_flow(
            str(test_dir),
            str(map_file),
            [".bin", ".txt"],
            [],  # exclude_dirs
            ["mapping.json", BINARY_MATCHES_LOG_FILE],  # exclude_files
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
        assert log_path.exists(), f"Binary log should exist. Files: {list(test_dir.iterdir())}"

        log_content = log_path.read_text()

        # Verify all patterns were found
        assert "OLDNAME" in log_content, "OLDNAME should be in log"
        assert "oldName" in log_content, "oldName should be in log"
        assert "Oldname" in log_content, "Oldname should be in log"

        # Verify file path and offsets
        assert "data.bin" in log_content, "Binary filename should be in log"
        assert "Offset: 6" in log_content, "Should have offset for OLDNAME"
        assert "Offset: 20" in log_content, "Should have offset for oldName"
        assert "Offset: 38" in log_content, "Should have offset for Oldname"

        # Verify text file was modified
        txt_content = txt_file.read_text()
        assert "NEWNAME" in txt_content, "Text file should be modified"
        assert "newName" in txt_content, "Text file should be modified"
        assert "Newname" in txt_content, "Text file should be modified"

        # Verify binary file was NOT modified
        bin_content = bin_file.read_bytes()
        assert b"OLDNAME" in bin_content, "Binary file should NOT be modified"
        assert b"NEWNAME" not in bin_content, "Binary file should NOT contain replacements"


if __name__ == "__main__":
    test_binary_file_logging_simple()
    print("✓ Binary file logging test passed!")
