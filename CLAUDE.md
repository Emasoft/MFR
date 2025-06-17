# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Mass Find Replace (MFR) is a sophisticated Python tool designed to perform safe, surgical find-and-replace operations across entire directory structures. It can rename files, folders, and modify file contents while preserving file encodings, handling Unicode correctly, and preventing data loss through collision detection.

## Key Features
- **Transaction-based system**: All operations are logged in `planned_transactions.json` for safety and resumability
- **Collision detection**: Prevents overwriting files with case-insensitive name conflicts
- **Binary file handling**: Detects but doesn't modify binary files (logs matches)
- **Encoding preservation**: Detects and preserves original file encodings
- **Resume capability**: Can resume interrupted operations
- **Multiple execution modes**: Dry-run, interactive, force, and resume modes
- **Unicode normalization**: Handles diacritics and control characters correctly

## Development Commands

### Environment Setup
```bash
# Create virtual environment with uv
uv venv
source .venv/bin/activate  # Linux/macOS

# Install dependencies
uv pip install -r requirements-dev.txt

# Or install individual dependencies
uv pip install prefect chardet isbinary pathspec striprtf
```

### Running the Tool

```bash
# Preview changes (dry run)
uv run python mass_find_replace.py . --dry-run

# Execute replacements
uv run python mass_find_replace.py .

# Resume interrupted operation
uv run python mass_find_replace.py . --resume

# Interactive mode (approve each change)
uv run python mass_find_replace.py . --interactive

# Force execution (skip confirmation)
uv run python mass_find_replace.py . --force

# Run with custom mapping file
uv run python mass_find_replace.py . --mapping-file custom_mapping.json
```

### Testing
```bash
# Run all tests
uv run pytest test_mass_find_replace.py -v

# Run with coverage
uv run pytest test_mass_find_replace.py --cov=. --cov-report=html

# Run specific test
uv run pytest test_mass_find_replace.py::test_name -v

# Run self-test
uv run python mass_find_replace.py . --self-test
```

### Code Quality
```bash
# Format with ruff
uv run ruff format .

# Lint with ruff
uv run ruff check --fix .

# Type checking with mypy
uv run mypy --strict mass_find_replace.py file_system_operations.py replace_logic.py
```

## Architecture Overview

### Core Modules
- **`mass_find_replace.py`**: Main entry point with CLI interface and workflow orchestration
- **`file_system_operations.py`**: Handles file I/O, transactions, and execution logic
- **`replace_logic.py`**: Manages string replacement logic with Unicode normalization

### Key Components

#### Replacement Mapping
- Configured via `replacement_mapping.json` with key-value pairs
- Keys are canonicalized (diacritics stripped, control chars removed, NFC normalized)
- Values are preserved as-is for replacement
- Prevents recursive mappings

#### Transaction System
- All changes planned in `planned_transactions.json` before execution
- Transaction states: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `SKIPPED`, `RETRY_LATER`
- Atomic updates ensure consistency
- Supports resume from any state

#### Unicode Handling
- Files decoded with `errors='surrogateescape'` to preserve all bytes
- NFC normalization for consistent matching
- Diacritics and control characters stripped for canonical matching
- Original encoding preserved on write-back

### Execution Flow
1. **Scan Phase**: Recursively scan directory for matches
2. **Plan Phase**: Create transaction log with all planned changes
3. **Validation Phase**: Verify transactions are deterministic
4. **Execution Phase**: Apply changes with byte-level verification
5. **Completion**: Update transaction statuses

### Command-Line Options
- `--dry-run`: Preview changes without executing
- `--interactive` / `-i`: Approve each change individually
- `--force` / `-y`: Skip confirmation prompt
- `--resume`: Resume from existing transaction file
- `--skip-scan`: Use existing transaction file without re-scanning
- `--mapping-file`: Specify custom replacement mapping
- `--extensions`: File extensions to process (default: common text formats)
- `--exclude-dirs`: Directories to skip
- `--skip-file-renaming`: Skip file rename operations
- `--skip-folder-renaming`: Skip folder rename operations
- `--skip-content`: Skip file content modifications
- `--process-symlink-names`: Enable symlink name processing
- `--timeout`: Retry timeout in minutes
- `--self-test`: Run the test suite

### Error Handling
- Graceful handling of I/O errors and encoding issues
- Retry mechanism for transient OS errors (file busy)
- Detailed logging to console and transaction file
- Preserves original state on failure

### Important Files
- `replacement_mapping.json`: Defines string replacements
- `planned_transactions.json`: Transaction log
- `binary_files_matches.log`: Binary file matches (informational)
- `collisions_errors.log`: Naming collision details

## Development Guidelines

- Use TDD methodology - write tests first
- Keep functions small and focused
- Use type annotations throughout
- Follow Google-style docstrings (no markdown)
- Commit frequently with atomic changes
- Run linters before committing
- Preserve the surgical nature of replacements