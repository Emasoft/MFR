# CI Test Failures Analysis

## Summary of Issues Found

### 1. Parameter Name Mismatches (main_flow function)

The tests are passing incorrect parameter names when calling `main_flow`:

**Expected parameters in function signature:**
- `ignore_symlinks_arg` (bool)
- `use_gitignore` (bool)
- `custom_ignore_file_path` (str | None)
- `interactive_mode` (bool)

**Incorrect parameters being passed by tests:**
- `interactive` → should be `interactive_mode`
- `no_gitignore` → should be `use_gitignore` (with inverted logic)
- `process_symlink_names` → should be `ignore_symlinks_arg` (with inverted logic)
- `ignore_file` → should be `custom_ignore_file_path`

### 2. Missing Function Arguments

1. **group_and_process_file_transactions()** - Missing `skip_content` parameter
   - Tests are calling it without the required `skip_content` argument

2. **scan_directory_for_occurrences()** - Unexpected keyword argument `directory`
   - The function doesn't accept a `directory` keyword argument

3. **_run_subprocess_command()** - Too many positional arguments
   - Tests are passing 3 arguments but function only takes 2

### 3. Missing Functions/Attributes

These functions are being called by tests but don't exist:

1. `file_system_operations._convert_to_relative_display_path`
2. `file_system_operations._is_running_in_test`
3. `file_system_operations._is_running_in_ci`
4. `file_system_operations._strip_control_characters`
5. `file_system_operations._canonicalize_for_matching`
6. `mass_find_replace.get_run_logger`
7. `mass_find_replace.run_self_test` (tests expect --self-test to run this function)

### 4. Enum Value Errors

1. **TransactionType** enum:
   - Tests expect `TransactionType.FOLDER_RENAME`
   - Actual enum has `TransactionType.FOLDER_NAME`

### 5. Type/Signature Issues

1. **load_ignore_patterns** - Tests pass a string but function expects a Path object
   - Error: `'str' object has no attribute 'is_file'`

2. **Multiple values for argument 'dry_run'**
   - Some functions are being called with `dry_run` both as positional and keyword argument

### 6. Test-Specific Issues

1. **Pytest stdin issue** - Tests trying to read from stdin during pytest execution
   - Error: "pytest: reading from stdin while output is captured\!"
   - Affects interactive mode tests

2. **Logging issues** - Tests expect different logging signatures than implemented

## Files Affected

1. `tests/test_coverage_improvements.py`
2. `tests/test_additional_coverage.py`
3. `tests/test_final_coverage.py`
4. `tests/test_surgical_replacements.py` (Windows-specific failures)

## Complete List of Failed Tests

### test_additional_coverage.py (2 tests)
1. `TestUtilityFunctions::test_group_and_process_file_transactions_edge_cases`
2. `TestUtilityFunctions::test_update_transaction_status_edge_cases`

### test_coverage_improvements.py (28 tests)
1. `TestColorFunctions::test_color_functions`
2. `TestExecuteTransactions::test_interactive_mode_apply_all`
3. `TestExecuteTransactions::test_interactive_mode_skip`
4. `TestExecuteTransactions::test_transaction_with_high_retry_count`
5. `TestFileOperations::test_folder_rename_collision`
6. `TestFileOperations::test_load_ignore_patterns`
7. `TestFileOperations::test_transaction_status_update`
8. `TestHelperFunctions::test_get_logger_with_context_error`
9. `TestHelperFunctions::test_get_logger_without_prefect`
10. `TestHelperFunctions::test_get_operation_description`
11. `TestMainCLI::test_main_cli_empty_mapping`
12. `TestMainCLI::test_main_cli_force_interactive_conflict`
13. `TestMainCLI::test_main_cli_invalid_directory`
14. `TestMainCLI::test_main_cli_invalid_json`
15. `TestMainCLI::test_main_cli_invalid_mapping_file`
16. `TestMainCLI::test_main_cli_not_directory`
17. `TestMainCLI::test_main_cli_self_test`
18. `TestMainCLI::test_main_cli_self_test_failure`
19. `TestMainCLI::test_main_cli_successful_run`
20. `TestMainCLI::test_main_cli_timeout_validation`
21. `TestMainCLI::test_main_cli_with_failures`
22. `TestMainFlow::test_main_flow_empty_transaction_file`
23. `TestMainFlow::test_main_flow_interactive_mode`
24. `TestMainFlow::test_main_flow_quiet_mode`
25. `TestMainFlow::test_main_flow_resume_no_file`
26. `TestMainFlow::test_main_flow_skip_scan_no_file`
27. `TestMainFlow::test_main_flow_verbose_mode`
28. `TestMainFlow::test_main_flow_with_dry_run_reset`
29. `TestReplaceLogic::test_validate_mapping_cyclic`

### test_final_coverage.py (21 tests)
1. `TestFileOperationHelpers::test_convert_to_relative_display_path`
2. `TestFileOperationHelpers::test_is_running_in_ci`
3. `TestFileOperationHelpers::test_is_running_in_test`
4. `TestLoggerFunctions::test_log_message_functions`
5. `TestLoggerFunctions::test_replace_logic_logging`
6. `TestMainCLIEdgeCases::test_main_cli_cyclic_mapping`
7. `TestMainCLIEdgeCases::test_main_cli_exception_handling`
8. `TestMainCLIEdgeCases::test_main_cli_json_key_error`
9. `TestMainCLIEdgeCases::test_main_cli_timeout_zero`
10. `TestMainCLIEdgeCases::test_main_cli_user_confirmation_no`
11. `TestPrefectIntegration::test_main_flow_with_prefect`
12. `TestPrefectIntegration::test_subprocess_flush_handlers`
13. `TestPrefectIntegration::test_subprocess_without_flush`
14. `TestScanEdgeCases::test_scan_with_permission_error`
15. `TestStringProcessing::test_canonicalize_edge_cases`
16. `TestStringProcessing::test_strip_functions`
17. `TestTransactionProcessing::test_content_change_with_no_changes`
18. `TestTransactionProcessing::test_file_rename_permission_error`
19. `TestTransactionProcessing::test_symlink_rename_dry_run`

### test_surgical_replacements.py (2 tests - Windows only)
1. `TestSurgicalReplacements::test_preserves_trailing_spaces`
2. `TestSurgicalReplacements::test_unicode_edge_cases`

## Summary

Total failed tests: **~52 tests** across 4 test files

The main issues are:
1. Parameter name mismatches between tests and actual function signatures
2. Missing required arguments in function calls
3. Functions/attributes that tests expect but don't exist in the code
4. Enum value mismatches
5. Type mismatches (str vs Path objects)
6. Test-specific issues with stdin handling
