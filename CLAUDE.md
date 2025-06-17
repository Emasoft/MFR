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
```

### Building and Packaging

#### Complete uv Package Setup Workflow

1. **Initialize Project**
```bash
# For new projects
uv init --name your-package-name --no-readme

# For existing projects (creates pyproject.toml)
uv init --name your-package-name
```

2. **Configure pyproject.toml**
```toml
[project]
name = "your-package-name"
version = "0.1.0"
description = "Package description"
authors = [{name = "Name", email = "email@example.com"}]
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
dependencies = [
    "dependency1>=1.0.0",
    "dependency2>=2.0.0",
]

[project.scripts]
command-name = "module:main_function"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-cov>=6.0.0",
    "mypy>=1.0.0",
    "ruff>=0.5.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build]
# For flat layout (modules in root)
packages = ["module1", "module2"]

# For src layout
# packages = ["src/module1", "src/module2"]
```

3. **Sync Dependencies**
```bash
# Install project dependencies
uv sync

# Install with optional dependencies
uv sync --extra dev

# Add new dependencies
uv add package-name
uv add --dev pytest  # Add to dev group
```

4. **Build the Package**
```bash
# Build both wheel and source distribution
uv build

# Build only wheel
uv build --wheel

# Build only source distribution
uv build --sdist

# Build with constraints
uv build --build-constraint constraints.txt
```

5. **Install for Development**
```bash
# Install in editable mode
uv pip install -e .

# Install with dev dependencies
uv pip install -e ".[dev]"
```

6. **Project Structure**
```
project-root/
├── pyproject.toml       # Project configuration
├── uv.lock             # Lock file (auto-generated)
├── README.md           # Project readme
├── .gitignore          # Git ignore file
├── module1.py          # Python modules (flat layout)
├── module2.py
├── test_module.py      # Tests
└── dist/               # Built distributions (after uv build)
    ├── package-0.1.0.tar.gz
    └── package-0.1.0-py3-none-any.whl
```

#### Key uv Commands Summary
- `uv init` - Initialize new project
- `uv add` - Add dependencies
- `uv remove` - Remove dependencies
- `uv sync` - Sync environment with pyproject.toml
- `uv build` - Build distributions
- `uv run` - Run commands in project environment
- `uv pip install -e .` - Install project in editable mode

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

### Critical Rules
- **ALWAYS read entire source files** when searching or editing (not just a few lines)
- **Never make unplanned changes** - discuss with user first and update DEVELOPMENT_PLAN.md
- **Commit after EACH change**, no matter how small
- **Always run linters** (ruff, mypy) before committing
- **Never output abridged code** with placeholders like `# ... rest of code ...`

### Code Quality Standards
- Use Test-Driven Development (TDD) - write tests first, implementation later
- Keep source files under 10KB - split into modules if larger
- Always use type annotations
- Write Google-style docstrings (no markdown in comments)
- Preserve the surgical nature of replacements
- Use Prefect for scripted processing with max_concurrency=1 for safety

### Python File Requirements
```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE CODE:
# <your changelog here...>
# 
```

### Testing Requirements
- Use pytest and pytest-cov
- Never use mocked tests unless absolutely necessary
- Show results in a formatted table with unicode borders
- Include test descriptions from docstrings
- Mark slow tests with 🐌 emoji

### Linting Commands
```bash
# Python formatting and linting
uv run ruff format
uv run ruff check --ignore E203,E402,E501,E266,W505,F841,F842,F401,W293,I001,UP015,C901,W291 --isolated --fix --output-format full
COLUMNS=400 uv run mypy --strict --show-error-context --pretty --install-types --no-color-output --non-interactive --show-error-codes --show-error-code-links --no-error-summary --follow-imports=normal <files>

# Check for secrets
gitleaks git --verbose
gitleaks dir --verbose
```

### Git Configuration
- Author: Emasoft
- Email: 713559+Emasoft@users.noreply.github.com
- Commit messages: atomic, specific, focus on WHAT changed with WHY in body
- Never mention Claude as author or co-author

### Development Best Practices
- Be conservative - only change what's strictly necessary
- Check if features already exist before implementing
- Reuse existing functions instead of duplicating code
- Create small, focused, reusable modules
- Always set Bash timeout to 1800000 (30 minutes)
- If solution isn't obvious, ask user for help
- Never use workarounds - implement proper solutions