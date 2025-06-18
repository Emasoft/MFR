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
    (runtime_dir / "atlasvibe_root").mkdir()
    (runtime_dir / "atlasvibe_root" / "sub_atlasvibe_folder").mkdir()
    (
        runtime_dir
        / "atlasvibe_root"
        / "sub_atlasvibe_folder"
        / "another_ATLASVIBE_dir"
    ).mkdir()
    deep_file = (
        runtime_dir
        / "atlasvibe_root"
        / "sub_atlasvibe_folder"
        / "another_ATLASVIBE_dir"
        / "deep_atlasvibe_file.txt"
    )
    deep_file.write_text(
        "This file contains ATLASVIBE multiple times: Atlasvibe atlasVibe"
    )

    # Create excluded items in runtime directory
    (runtime_dir / "excluded_atlasvibe_dir").mkdir()
    (runtime_dir / "excluded_atlasvibe_dir" / "excluded_file.txt").write_text(
        "ATLASVIBE content"
    )
    (runtime_dir / "exclude_this_atlasvibe_file.txt").write_text(
        "Atlasvibe exclusion test"
    )

    # Verify structure
    assert (runtime_dir / "atlasvibe_root").exists(), (
        "Required dir not created in fixture"
    )
    context = {"runtime": runtime_dir, "config": config_dir}
    yield context
    # Cleanup
    shutil.rmtree(tmp_path)


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
            "atlasvibe": "flojoy",
            "Atlasvibe": "Flojoy",
            "atlasVibe": "floJoy",
            "AtlasVibe": "FloJoy",
            "ATLASVIBE": "FLOJOY",
        }
    }
    map_file.write_text(
        json.dumps(map_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
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
