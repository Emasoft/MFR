# Surgical Replacement Test Results

## Summary

MFR is generally performing surgical replacements correctly for standard UTF-8 files, preserving:
- Trailing spaces
- Line endings (LF, CRLF, CR, mixed)
- Empty files
- File permissions
- UTF-8 with BOM

However, there are several issues preventing truly universal surgical replacements:

## Issues Found

### 1. Invalid UTF-8 Byte Sequences (CRITICAL)
**Status**: FAILING
**Issue**: Files containing invalid UTF-8 sequences (e.g., `\x80\x81\x82`) cannot be processed.
**Root Cause**: When reading with `errors='surrogateescape'`, invalid bytes are converted to surrogate characters. When saving the transaction JSON, these surrogates cannot be encoded to UTF-8, causing a `UnicodeEncodeError`.
**Impact**: Any file with encoding errors will crash MFR during the scan phase.

### 2. UTF-16 Encoding Without BOM (HIGH)
**Status**: FAILING
**Issue**: UTF-16 files without BOM are incorrectly detected as UTF-8.
**Root Cause**: The encoding detection logic doesn't properly identify UTF-16 BE/LE without BOM markers.
**Impact**: UTF-16 files are corrupted because they're read as UTF-8 and the replacement happens on incorrectly decoded text.

### 3. Binary File Handling (WORKING)
**Status**: PASSING
**Behavior**: Binary files are correctly detected and skipped for content modification. Matches are logged to `binary_files_matches.log`.

### 4. Read-Only Files (PARTIAL)
**Status**: HANDLED
**Behavior**: Read-only files cause a permission error during write, which is logged as a failed transaction. The program continues without crashing.

## Technical Details

### Working Correctly
- Standard UTF-8 files (with or without BOM)
- ASCII files
- Empty files
- Files with trailing spaces/tabs
- Files with different line endings
- File permission preservation (on Unix)

### Not Working
1. **Surrogate Escape Problem**: The transaction JSON serialization needs to handle surrogate characters properly
2. **Encoding Detection**: The `chardet` library is not reliably detecting UTF-16 without BOM
3. **Transaction Saving**: Need a way to save file content with encoding errors in JSON format

## Recommendations

1. **Fix JSON Serialization**:
   - Option A: Encode strings with surrogates to base64 before JSON serialization
   - Option B: Use a custom JSON encoder that can handle surrogates
   - Option C: Save transaction data in a format that supports arbitrary bytes (e.g., pickle, msgpack)

2. **Improve Encoding Detection**:
   - Add heuristics for UTF-16 detection (check for null bytes pattern)
   - Consider using multiple detection libraries
   - Allow user to specify encoding for specific file patterns

3. **Add Test Coverage**:
   - Test all common encodings (UTF-8, UTF-16, UTF-32, Latin-1, etc.)
   - Test files with mixed encodings in the same directory
   - Test extremely large files with encoding errors

## Conclusion

MFR performs surgical replacements correctly for the majority of text files (UTF-8/ASCII). However, to truly handle all files surgically, the encoding error handling and UTF-16 detection issues must be resolved. The surrogate escape issue is the most critical as it prevents processing any file with encoding errors.
