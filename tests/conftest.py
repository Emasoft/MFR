# conftest.py
import pytest
from pathlib import Path
import json
import shutil


@pytest.fixture
def temp_test_dir(tmp_path: Path):
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
    def handle_remove_readonly(func, path, exc):
        """Error handler for Windows readonly files."""
        import stat
        import os

        if os.name == "nt":  # Windows
            os.chmod(path, stat.S_IWRITE)
            func(path)
        else:
            raise

    shutil.rmtree(tmp_path, onerror=handle_remove_readonly)


@pytest.fixture
def default_map_file(temp_test_dir: dict) -> Path:
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
def assert_file_content():
    def _assert(file_path: Path, expected_content: str):
        """Helper to validate file content with readable diffs"""
        actual = file_path.read_text(encoding="utf-8")
        assert actual == expected_content, (
            f"Content mismatch in {file_path}: Expected {expected_content!r}, got {actual!r}"
        )

    return _assert
