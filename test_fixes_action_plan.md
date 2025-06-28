# Test Fixes Action Plan

## Priority 1: Parameter Name Fixes

### In all test files calling main_flow():
1. Replace `interactive` with `interactive_mode`
2. Replace `no_gitignore` with `use_gitignore` (and invert the boolean value)
3. Replace `process_symlink_names` with `ignore_symlinks_arg` (and invert the boolean value)
4. Replace `ignore_file` with `custom_ignore_file_path`

## Priority 2: Function Signature Fixes

### group_and_process_file_transactions():
- Add `skip_content` parameter to all calls in tests

### scan_directory_for_occurrences():
- Remove `directory` keyword argument from test calls (use positional argument)

### _run_subprocess_command():
- Fix calls to use only 2 arguments instead of 3

### load_ignore_patterns():
- Convert string paths to Path objects before calling

## Priority 3: Missing Functions

### Either add these functions to the codebase OR remove from tests:
1. `file_system_operations._convert_to_relative_display_path`
2. `file_system_operations._is_running_in_test`
3. `file_system_operations._is_running_in_ci`
4. `file_system_operations._strip_control_characters`
5. `file_system_operations._canonicalize_for_matching`
6. `mass_find_replace.get_run_logger`
7. `mass_find_replace.run_self_test`

## Priority 4: Enum Fixes

### TransactionType enum:
- Change `TransactionType.FOLDER_RENAME` to `TransactionType.FOLDER_NAME` in tests

## Priority 5: Test-Specific Fixes

### Interactive mode tests:
- Mock user input instead of reading from stdin
- Use pytest's monkeypatch or mock to handle input

### Logging tests:
- Update test expectations to match actual logging implementation

## Files to Modify

1. `tests/test_coverage_improvements.py` (28 failing tests)
2. `tests/test_additional_coverage.py` (2 failing tests)
3. `tests/test_final_coverage.py` (21 failing tests)
4. `tests/test_surgical_replacements.py` (2 failing tests - Windows only)

## Verification Steps

After fixing:
1. Run tests locally: `uv run pytest -xvs`
2. Check parameter binding errors are resolved
3. Verify all function calls match signatures
4. Ensure no missing attribute errors
