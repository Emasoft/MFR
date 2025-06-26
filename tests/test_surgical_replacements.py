#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Creation of comprehensive tests for surgical string replacements
# - Tests that MFR preserves all file characteristics except replaced strings
# - Verifies preservation of: encoding errors, trailing spaces, line endings, binary data
# - Tests that intentionally broken files remain broken (only strings replaced)
#

"""
Test suite to verify MFR performs surgical string replacements.

These tests ensure that MFR:
1. Only replaces the exact strings specified in the mapping
2. Preserves all other file characteristics including:
   - Encoding errors and invalid bytes
   - Trailing spaces and tabs
   - Line ending styles (LF, CRLF, CR, mixed)
   - File encoding (UTF-8, UTF-16, Latin-1, etc.)
   - Binary sections in mixed files
   - Intentionally malformed data
"""

import pytest
from pathlib import Path
import json
import tempfile
import shutil
import sys

from mass_find_replace.mass_find_replace import main_flow


class TestSurgicalReplacements:
    """Test that MFR only changes what it's supposed to change."""

    def run_mfr(self, directory, mapping, **kwargs):
        """Helper to run MFR with default settings."""
        mapping_file = directory / "mapping.json"
        mapping_file.write_text(json.dumps({"REPLACEMENT_MAPPING": mapping}))

        defaults = {
            "directory": str(directory),
            "mapping_file": str(mapping_file),
            "extensions": None,
            "exclude_dirs": [],
            "exclude_files": [],
            "dry_run": False,
            "skip_scan": False,
            "resume": False,
            "force_execution": True,
            "ignore_symlinks_arg": False,  # Changed from process_symlink_names
            "use_gitignore": False,  # Changed from no_gitignore (inverted)
            "custom_ignore_file_path": None,  # Changed from ignore_file
            "skip_file_renaming": False,
            "skip_folder_renaming": False,
            "skip_content": False,
            "timeout_minutes": 30,
            "quiet_mode": True,
            "verbose_mode": False,
            "interactive_mode": False,  # Changed from interactive
        }
        defaults.update(kwargs)

        return main_flow(**defaults)

    def test_preserves_trailing_spaces(self, tmp_path):
        """Test that trailing spaces are preserved."""
        test_file = tmp_path / "spaces.txt"
        # Create content with various trailing spaces
        original_content = "Line with no trailing space\n" "Line with one trailing space \n" "Line with multiple trailing spaces   \n" "Line with OLDNAME and trailing spaces   \n" "Line with tabs\t\t\n" "Line with OLDNAME and tabs\t\t\n" "Last line without newline and spaces   "
        test_file.write_text(original_content)

        # Run MFR
        mapping = {"OLDNAME": "NEWNAME"}
        self.run_mfr(tmp_path, mapping)

        # Verify exact preservation except for OLDNAME -> NEWNAME
        expected_content = original_content.replace("OLDNAME", "NEWNAME")
        actual_content = test_file.read_text()

        assert actual_content == expected_content
        # Verify byte-by-byte for extra safety
        assert test_file.read_bytes() == expected_content.encode("utf-8")

    def test_preserves_line_endings(self, tmp_path):
        """Test that various line ending styles are preserved."""
        # Test LF (Unix)
        lf_file = tmp_path / "unix.txt"
        lf_content = "Line 1 with OLDNAME\nLine 2\nLine 3 with OLDNAME\n"
        lf_file.write_bytes(lf_content.encode("utf-8"))

        # Test CRLF (Windows)
        crlf_file = tmp_path / "windows.txt"
        crlf_content = "Line 1 with OLDNAME\r\nLine 2\r\nLine 3 with OLDNAME\r\n"
        crlf_file.write_bytes(crlf_content.encode("utf-8"))

        # Test CR (Old Mac)
        cr_file = tmp_path / "oldmac.txt"
        cr_content = "Line 1 with OLDNAME\rLine 2\rLine 3 with OLDNAME\r"
        cr_file.write_bytes(cr_content.encode("utf-8"))

        # Test mixed line endings
        mixed_file = tmp_path / "mixed.txt"
        mixed_content = "Line 1 OLDNAME\nLine 2 OLDNAME\r\nLine 3 OLDNAME\rLine 4"
        mixed_file.write_bytes(mixed_content.encode("utf-8"))

        # Run MFR
        mapping = {"OLDNAME": "NEWNAME"}
        self.run_mfr(tmp_path, mapping)

        # Verify each file preserves its line endings
        assert lf_file.read_bytes() == lf_content.replace("OLDNAME", "NEWNAME").encode("utf-8")
        assert crlf_file.read_bytes() == crlf_content.replace("OLDNAME", "NEWNAME").encode("utf-8")
        assert cr_file.read_bytes() == cr_content.replace("OLDNAME", "NEWNAME").encode("utf-8")
        assert mixed_file.read_bytes() == mixed_content.replace("OLDNAME", "NEWNAME").encode("utf-8")

    def test_preserves_encoding_errors(self, tmp_path):
        """Test that files with encoding errors are preserved (except for replacements)."""
        test_file = tmp_path / "broken_encoding.txt"

        # Create file with invalid UTF-8 sequences
        # \x80-\xFF are invalid UTF-8 start bytes
        broken_bytes = b"Valid UTF-8 with OLDNAME\n" b"Invalid UTF-8: \x80\x81\x82 OLDNAME \x83\x84\x85\n" b"More text with OLDNAME\n" b"Mixed: \xc0\xc1 OLDNAME \xfe\xff\n"
        test_file.write_bytes(broken_bytes)

        # Run MFR
        mapping = {"OLDNAME": "NEWNAME"}
        self.run_mfr(tmp_path, mapping)

        # Read back and verify
        result_bytes = test_file.read_bytes()
        expected_bytes = broken_bytes.replace(b"OLDNAME", b"NEWNAME")

        # Debug: print what we got
        if result_bytes != expected_bytes:
            print(f"\nExpected: {expected_bytes!r}")
            print(f"Got:      {result_bytes!r}")

        assert result_bytes == expected_bytes

    def test_preserves_different_encodings(self, tmp_path):
        """Test that files with different encodings are handled correctly."""
        # UTF-16 BE file
        utf16_be_file = tmp_path / "utf16be.txt"
        utf16_content = "Text with OLDNAME in UTF-16"
        utf16_be_file.write_bytes(utf16_content.encode("utf-16-be"))

        # UTF-16 LE file with BOM
        utf16_le_file = tmp_path / "utf16le.txt"
        utf16_le_file.write_bytes(b"\xff\xfe" + utf16_content.encode("utf-16-le"))

        # Latin-1 file
        latin1_file = tmp_path / "latin1.txt"
        latin1_content = "Café with OLDNAME résumé"
        latin1_file.write_bytes(latin1_content.encode("latin-1"))

        # Run MFR
        mapping = {"OLDNAME": "NEWNAME"}
        self.run_mfr(tmp_path, mapping)

        # Verify each file maintains its encoding
        expected_utf16_be = utf16_content.replace("OLDNAME", "NEWNAME").encode("utf-16-be")
        assert utf16_be_file.read_bytes() == expected_utf16_be

        expected_utf16_le = b"\xff\xfe" + utf16_content.replace("OLDNAME", "NEWNAME").encode("utf-16-le")
        assert utf16_le_file.read_bytes() == expected_utf16_le

        expected_latin1 = latin1_content.replace("OLDNAME", "NEWNAME").encode("latin-1")
        assert latin1_file.read_bytes() == expected_latin1

    def test_preserves_null_bytes(self, tmp_path):
        """Test that null bytes and binary data are preserved."""
        test_file = tmp_path / "nullbytes.txt"

        # Create content with null bytes
        content_with_nulls = b"Text before null\x00Text after null with OLDNAME\x00\n" b"More text\x00\x00\x00OLDNAME in the middle\x00\n" b"\x00\x00Leading nulls OLDNAME\n" b"OLDNAME trailing nulls\x00\x00\x00"
        test_file.write_bytes(content_with_nulls)

        # Run MFR
        mapping = {"OLDNAME": "NEWNAME"}
        self.run_mfr(tmp_path, mapping)

        # Verify preservation
        expected = content_with_nulls.replace(b"OLDNAME", b"NEWNAME")
        assert test_file.read_bytes() == expected

    def test_preserves_corrupt_test_files(self, tmp_path):
        """Test that intentionally corrupt test files remain corrupt (only strings replaced)."""
        # Create a malformed JSON file
        bad_json = tmp_path / "corrupt.json"
        bad_json_content = '{"key": "OLDNAME", "broken": [1, 2, 3'  # Missing closing brackets
        bad_json.write_text(bad_json_content)

        # Create a malformed XML file
        bad_xml = tmp_path / "corrupt.xml"
        bad_xml_content = "<root><item>OLDNAME</item><broken>"  # Unclosed tag
        bad_xml.write_text(bad_xml_content)

        # Create a file with mixed binary and text
        mixed_file = tmp_path / "mixed_binary.dat"
        mixed_content = b"\x89PNG\r\n\x1a\nOLDNAME\x00\x00\x00\rIHDR"
        mixed_file.write_bytes(mixed_content)

        # Run MFR with appropriate extensions
        mapping = {"OLDNAME": "NEWNAME"}
        self.run_mfr(tmp_path, mapping, extensions=[".json", ".xml", ".dat"])

        # Verify files remain corrupt but strings are replaced
        assert bad_json.read_text() == bad_json_content.replace("OLDNAME", "NEWNAME")
        assert bad_xml.read_text() == bad_xml_content.replace("OLDNAME", "NEWNAME")
        assert mixed_file.read_bytes() == mixed_content.replace(b"OLDNAME", b"NEWNAME")

    def test_very_long_lines(self, tmp_path):
        """Test that very long lines are handled correctly."""
        test_file = tmp_path / "longlines.txt"

        # Create a very long line with patterns scattered throughout
        long_line = "Start " + ("x" * 10000) + " OLDNAME " + ("y" * 10000) + " OLDNAME " + ("z" * 10000) + " End"
        content = f"Short line with OLDNAME\n{long_line}\nAnother short line with OLDNAME"

        test_file.write_text(content)

        # Run MFR
        mapping = {"OLDNAME": "NEWNAME"}
        self.run_mfr(tmp_path, mapping)

        # Verify
        expected = content.replace("OLDNAME", "NEWNAME")
        assert test_file.read_text() == expected

    def test_unicode_edge_cases(self, tmp_path):
        """Test Unicode edge cases including surrogates and special characters."""
        test_file = tmp_path / "unicode_edge.txt"

        # Create content with various Unicode challenges
        content = (
            "Normal text with OLDNAME\n"
            "Emoji: 🎉 OLDNAME 🎊\n"
            "Zero-width chars: O\u200bLDNAME (with ZWSP)\n"  # Zero-width space inside OLDNAME
            "Combining chars: OLDNAMÉ (with combining acute)\n"
            "Right-to-left: مرحبا OLDNAME שלום\n"
            "Math symbols: ∑ OLDNAME ∫\n"
        )
        test_file.write_text(content)

        # Run MFR
        mapping = {"OLDNAME": "NEWNAME"}
        self.run_mfr(tmp_path, mapping)

        # Verify - note that OLDNAME with ZWSP inside won't be replaced (correct behavior)
        result = test_file.read_text()
        assert "Normal text with NEWNAME" in result
        assert "Emoji: 🎉 NEWNAME 🎊" in result
        assert "O\u200bLDNAME" in result  # Not replaced due to ZWSP
        assert "NEWNAMÉ" in result  # Replaced, combining char preserved
        assert "مرحبا NEWNAME שלום" in result
        assert "∑ NEWNAME ∫" in result

    def test_empty_files_and_edge_cases(self, tmp_path):
        """Test empty files and edge cases."""
        # Empty file
        empty_file = tmp_path / "empty.txt"
        empty_file.touch()

        # File with only whitespace
        whitespace_file = tmp_path / "whitespace.txt"
        whitespace_file.write_text("   \t\t\n\n\t   ")

        # File with only the pattern
        pattern_only = tmp_path / "pattern_only.txt"
        pattern_only.write_text("OLDNAME")

        # Run MFR
        mapping = {"OLDNAME": "NEWNAME"}
        self.run_mfr(tmp_path, mapping)

        # Verify
        assert empty_file.read_bytes() == b""
        assert whitespace_file.read_text() == "   \t\t\n\n\t   "
        assert pattern_only.read_text() == "NEWNAME"

    def test_concurrent_patterns(self, tmp_path):
        """Test multiple patterns that might interfere with each other."""
        test_file = tmp_path / "concurrent.txt"

        content = "OLDNAME1 OLDNAME2 OLDNAME3\n" "OLDNAME1OLDNAME2OLDNAME3\n" "Nested: OLDNAME1 contains OLDNAME2\n" "Partial: OLDNAME12 and 3OLDNAME\n"
        test_file.write_text(content)

        # Run MFR with multiple mappings
        mapping = {"OLDNAME1": "NEWNAME1", "OLDNAME2": "NEWNAME2", "OLDNAME3": "NEWNAME3"}
        self.run_mfr(tmp_path, mapping)

        # Verify each pattern is replaced independently
        result = test_file.read_text()
        assert "NEWNAME1 NEWNAME2 NEWNAME3\n" in result
        assert "NEWNAME1NEWNAME2NEWNAME3\n" in result
        assert "Nested: NEWNAME1 contains NEWNAME2\n" in result
        assert "Partial: OLDNAME12 and 3OLDNAME\n" in result  # These shouldn't change

    def test_file_permissions_preserved(self, tmp_path):
        """Test that file permissions are preserved (on Unix-like systems)."""
        if sys.platform.startswith("win"):
            pytest.skip("File permissions test not applicable on Windows")

        import stat

        test_file = tmp_path / "executable.sh"
        test_file.write_text("#!/bin/bash\necho OLDNAME\n")

        # Make file executable
        test_file.chmod(stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)
        original_mode = test_file.stat().st_mode

        # Run MFR
        mapping = {"OLDNAME": "NEWNAME"}
        self.run_mfr(tmp_path, mapping)

        # Verify permissions preserved
        assert test_file.stat().st_mode == original_mode
        assert test_file.read_text() == "#!/bin/bash\necho NEWNAME\n"


class TestErrorHandling:
    """Test error handling during surgical replacements."""

    def run_mfr(self, directory, mapping, **kwargs):
        """Helper to run MFR with default settings."""
        mapping_file = directory / "mapping.json"
        mapping_file.write_text(json.dumps({"REPLACEMENT_MAPPING": mapping}))

        defaults = {
            "directory": str(directory),
            "mapping_file": str(mapping_file),
            "extensions": None,
            "exclude_dirs": [],
            "exclude_files": [],
            "dry_run": False,
            "skip_scan": False,
            "resume": False,
            "force_execution": True,
            "ignore_symlinks_arg": False,  # Changed from process_symlink_names
            "use_gitignore": False,  # Changed from no_gitignore (inverted)
            "custom_ignore_file_path": None,  # Changed from ignore_file
            "skip_file_renaming": False,
            "skip_folder_renaming": False,
            "skip_content": False,
            "timeout_minutes": 30,
            "quiet_mode": True,
            "verbose_mode": False,
            "interactive_mode": False,  # Changed from interactive
        }
        defaults.update(kwargs)

        return main_flow(**defaults)

    def test_handles_read_only_files(self, tmp_path):
        """Test handling of read-only files."""
        if sys.platform.startswith("win"):
            pytest.skip("Read-only file test needs adjustment for Windows")

        import stat

        test_file = tmp_path / "readonly.txt"
        test_file.write_text("Content with OLDNAME")

        # Make file read-only
        test_file.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

        # Run MFR
        mapping = {"OLDNAME": "NEWNAME"}
        result = self.run_mfr(tmp_path, mapping)

        # Should handle gracefully (might skip or handle the read-only file)
        # The important thing is it doesn't crash
        # main_flow doesn't return a value, so we just check it didn't crash

    def test_handles_files_with_no_newline_at_end(self, tmp_path):
        """Test files without trailing newline."""
        test_file = tmp_path / "no_newline.txt"
        # Write without trailing newline
        test_file.write_bytes(b"Last line with OLDNAME")

        # Run MFR
        mapping = {"OLDNAME": "NEWNAME"}
        self.run_mfr(tmp_path, mapping)

        # Verify no newline was added
        assert test_file.read_bytes() == b"Last line with NEWNAME"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
