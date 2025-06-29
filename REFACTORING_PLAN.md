# MFR Refactoring Plan

## Current Issues

### 1. Critical Issues
- **File size violations**:
  - `file_system_operations.py`: 87KB (should be <10KB) - **8.8x over limit**
  - `mass_find_replace.py`: 32KB (should be <10KB) - **3.2x over limit**
  - `replace_logic.py`: 18KB (should be <10KB) - **1.8x over limit**

### 2. Code Quality Issues
- 9 type annotation issues (use of `Any`)
- 55 missing docstrings
- Import organization issues

### 3. Configuration Issues
- Pre-commit configuration is complete (includes deptry, yamllint, actionlint)
- All tests passing
- No security vulnerabilities

## Refactoring Strategy

### Phase 1: Immediate Fixes (Low Risk)
1. Fix the 9 `Any` type annotations to use proper types
2. Add critical missing docstrings to public APIs
3. Document the refactoring plan

### Phase 2: File Splitting (High Risk, High Priority)

#### 2.1 Split `file_system_operations.py` (87KB → ~10 files)
This is the most critical refactoring. The file will be split into:

1. **core/**
   - `constants.py` (~2KB) - All constants and configuration
   - `exceptions.py` (~1KB) - Custom exceptions
   - `types.py` (~2KB) - Type definitions and enums

2. **utils/**
   - `json_handlers.py` (~3KB) - JSON encoding/decoding
   - `file_encoding.py` (~8KB) - Encoding detection
   - `file_locking.py` (~3KB) - Cross-platform file locking
   - `logging_utils.py` (~3KB) - Logging utilities
   - `path_utils.py` (~3KB) - Path manipulation

3. **scanning/**
   - `pattern_matching.py` (~3KB) - Pattern/ignore handling
   - `directory_scanner.py` (~15KB) - Directory scanning

4. **transactions/**
   - `transaction_io.py` (~5KB) - Save/load transactions
   - `rename_executor.py` (~5KB) - Rename operations
   - `content_executor.py` (~20KB) - Content modifications
   - `executor.py` (~25KB) - Main execution flow

#### 2.2 Split `mass_find_replace.py` (32KB → ~4 files)
1. **cli.py** (~8KB) - Command-line interface
2. **workflow.py** (~10KB) - Main workflow logic
3. **config.py** (~5KB) - Configuration handling
4. **utils.py** (~5KB) - Helper functions

#### 2.3 Split `replace_logic.py` (18KB → ~2 files)
1. **string_processing.py** (~10KB) - String manipulation
2. **validation.py** (~8KB) - Validation logic

### Phase 3: Final Cleanup
1. Update all imports
2. Add remaining docstrings
3. Run full test suite
4. Update documentation

## Implementation Order

1. **Create new directory structure**:
   ```
   src/mass_find_replace/
   ├── core/
   ├── utils/
   ├── scanning/
   ├── transactions/
   └── cli/
   ```

2. **Start with lowest-risk extractions**:
   - Extract constants, exceptions, types
   - Extract utility functions
   - Test after each extraction

3. **Extract major components**:
   - Extract scanning functionality
   - Extract transaction handling
   - Keep main flow intact until last

4. **Update and test**:
   - Update all imports
   - Run tests after each major change
   - Ensure backward compatibility

## Risk Mitigation

1. **Create comprehensive tests first** for critical paths
2. **Extract in small increments** with tests after each
3. **Maintain backward compatibility** with re-exports
4. **Use git branches** for major changes
5. **Run full CI/CD** after each phase

## Success Criteria

- All files under 10KB (except where cohesion requires slightly larger)
- All tests passing
- No functionality changes
- Improved code organization
- Better separation of concerns
