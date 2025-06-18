# Mass Find Replace (MFR)

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

A sophisticated Python tool for performing safe, surgical find-and-replace operations across entire directory structures. MFR can rename files, folders, and modify file contents while preserving file encodings, handling Unicode correctly, and preventing data loss through intelligent collision detection.

## 🚀 Features

### Core Capabilities
- **Transaction-based system**: All operations are logged in `planned_transactions.json` for safety and resumability
- **Intelligent collision detection**: Prevents overwriting files with case-insensitive name conflicts
- **Binary file handling**: Detects binary files and logs matches without modification
- **Encoding preservation**: Automatically detects and preserves original file encodings
- **Unicode normalization**: Handles diacritics and control characters correctly with NFC normalization
- **Multiple execution modes**: Dry-run, interactive, force, and resume modes

### Advanced Features
- **Resume capability**: Interrupted operations can be resumed from where they left off
- **Atomic operations**: Uses transaction states (PENDING, IN_PROGRESS, COMPLETED, FAILED, SKIPPED)
- **Selective processing**: Choose to process only file names, folder names, or file contents
- **Symlink support**: Optional processing of symbolic link names
- **Customizable exclusions**: Exclude specific directories or file extensions
- **Detailed logging**: Comprehensive logs for debugging and audit trails

## 📦 Installation

### From Source (Recommended for now)

1. **Clone the repository**:
```bash
git clone https://github.com/Emasoft/MFR.git
cd MFR
```

2. **Create and activate a virtual environment using uv**:
```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv
source .venv/bin/activate  # On Linux/macOS
# or
.venv\Scripts\activate     # On Windows
```

3. **Install dependencies**:
```bash
uv pip install -r requirements.txt
```

4. **Install in development mode**:
```bash
uv pip install -e .
```

### Building from Source

To build a distributable package:
```bash
uv build
# This creates wheel and source distributions in the dist/ directory
```

## 🎯 Usage

### Basic Usage

1. **Configure your replacements** by editing `replacement_mapping.json`:
```json
{
  "REPLACEMENT_MAPPING": {
    "OldProjectName": "NewProjectName",
    "old_function_name": "new_function_name",
    "deprecatedMethod": "modernMethod",
    "legacyModule": "updatedModule"
  }
}
```

2. **Preview changes** (dry run):
```bash
mfr /path/to/project --dry-run
```

3. **Execute replacements**:
```bash
mfr /path/to/project
```

### Real-World Examples

#### Example 1: Renaming a Function Across a Codebase
You need to rename `getUserData()` to `fetchUserProfile()` across your entire JavaScript project:

```json
{
  "REPLACEMENT_MAPPING": {
    "getUserData": "fetchUserProfile"
  }
}
```

```bash
# Preview the changes
mfr ./src --dry-run --extensions .js,.jsx,.ts,.tsx

# Execute with interactive confirmation
mfr ./src --interactive --extensions .js,.jsx,.ts,.tsx
```

#### Example 2: Changing Library Imports
Migrating from an old library to a new one (e.g., `moment` to `date-fns`):

```json
{
  "REPLACEMENT_MAPPING": {
    "from 'moment'": "from 'date-fns'",
    "require('moment')": "require('date-fns')",
    "import moment": "import * as dateFns"
  }
}
```

```bash
# Process only JavaScript/TypeScript files
mfr ./src --extensions .js,.jsx,.ts,.tsx
```

#### Example 3: Rebranding a Project
Changing all variations of a project name:

```json
{
  "REPLACEMENT_MAPPING": {
    "OldBrand": "NewBrand",
    "oldbrand": "newbrand",
    "OLDBRAND": "NEWBRAND",
    "old-brand": "new-brand",
    "old_brand": "new_brand"
  }
}
```

```bash
# Run on entire project, excluding node_modules and .git
mfr . --exclude-dirs node_modules,.git,dist,build
```

#### Example 4: API Endpoint Migration
Updating API endpoints across configuration files:

```json
{
  "REPLACEMENT_MAPPING": {
    "api.oldservice.com": "api.newservice.com",
    "/v1/": "/v2/",
    "apiKey": "accessToken"
  }
}
```

```bash
# Target only configuration files
mfr ./config --extensions .json,.yaml,.yml,.env,.ini
```

### Command-Line Options

```bash
mfr [directory] [options]
```

#### Core Options
- `--dry-run`: Preview changes without executing them
- `--interactive`, `-i`: Approve each change individually
- `--force`, `-y`: Skip confirmation prompt
- `--resume`: Resume from existing transaction file
- `--skip-scan`: Use existing transaction file without re-scanning

#### File Selection Options
- `--mapping-file PATH`: Use custom replacement mapping file (default: `replacement_mapping.json`)
- `--extensions EXT1,EXT2`: File extensions to process (default: common text formats)
- `--exclude-dirs DIR1,DIR2`: Directories to skip (default: `.git,.hg,.svn,__pycache__`)

#### Processing Options
- `--skip-file-renaming`: Skip file rename operations
- `--skip-folder-renaming`: Skip folder rename operations
- `--skip-content`: Skip file content modifications
- `--process-symlink-names`: Enable symbolic link name processing

#### Advanced Options
- `--timeout MINUTES`: Retry timeout for locked files (default: 5)
- `--self-test`: Run the built-in test suite
- `--verbose`: Enable detailed logging

### Understanding the Transaction System

MFR uses a transaction-based approach for safety:

1. **Scan Phase**: Identifies all files and replacements needed
2. **Plan Phase**: Creates `planned_transactions.json` with all operations
3. **Validation Phase**: Checks for conflicts and circular dependencies
4. **Execution Phase**: Applies changes with verification
5. **Completion Phase**: Updates transaction states

Transaction states:
- `PENDING`: Operation not yet started
- `IN_PROGRESS`: Currently being processed
- `COMPLETED`: Successfully finished
- `FAILED`: Operation failed (check logs)
- `SKIPPED`: Skipped due to user choice or conflict
- `RETRY_LATER`: Temporary failure, will retry

### Configuration Files

#### replacement_mapping.json
The main configuration file defining your find-and-replace mappings:

```json
{
  "REPLACEMENT_MAPPING": {
    "search_string": "replacement_string",
    "CaseSensitive": "CaseSensitiveReplacement",
    "special.chars": "special.characters"
  }
}
```

**Important notes**:
- Keys are canonicalized (diacritics stripped, normalized to NFC)
- Values are preserved exactly as written
- The tool prevents recursive mappings automatically
- Unicode is fully supported

#### planned_transactions.json
Generated during the scan phase, this file contains all planned operations:

```json
{
  "version": "1.0",
  "transactions": [
    {
      "id": "unique-transaction-id",
      "type": "file_content",
      "source_path": "/path/to/file.js",
      "status": "PENDING",
      "encoding": "utf-8",
      "changes": [
        {
          "line": 42,
          "old": "getUserData()",
          "new": "fetchUserProfile()"
        }
      ]
    }
  ]
}
```

## 🛡️ Safety Features

### Collision Detection
MFR prevents overwrites when renaming would create conflicts:
- Case-insensitive collision detection on case-insensitive filesystems
- Detailed collision reports in `collisions_errors.log`
- Option to skip or handle manually in interactive mode

### Binary File Protection
- Binary files are detected but never modified
- Matches in binary files are logged to `binary_files_matches.log`
- Prevents corruption of executables, images, and other binary formats

### Encoding Preservation
- Automatically detects file encoding (UTF-8, UTF-16, GB18030, etc.)
- Preserves original encoding when writing files
- Handles files with mixed or unusual encodings gracefully

## 🐛 Troubleshooting

### Common Issues

**1. "Permission denied" errors**
- Ensure you have read/write permissions for all files
- On Windows, close any programs that might be using the files
- Use `--timeout` option for temporarily locked files

**2. "Collision detected" warnings**
- Review `collisions_errors.log` for details
- Use `--interactive` mode to handle case-by-case
- Consider using more specific replacement patterns

**3. Unicode/encoding errors**
- MFR handles encoding automatically, but check logs for details
- Ensure your `replacement_mapping.json` is valid UTF-8
- Use `--verbose` flag for detailed encoding information

**4. Transaction file conflicts**
- Use `--resume` to continue interrupted operations
- Delete `planned_transactions.json` to start fresh
- Check transaction status for `FAILED` entries

### Debug Mode

For detailed debugging information:
```bash
mfr /path/to/project --verbose --dry-run
```

This provides:
- Detailed encoding detection results
- Step-by-step transaction processing
- Full error stack traces
- Performance metrics

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Follow the TDD approach (write tests first)
4. Ensure all tests pass: `uv run pytest`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🏗️ Project Structure

```
MFR/
├── src/
│   └── mass_find_replace/
│       ├── __init__.py           # Package initialization
│       ├── mass_find_replace.py  # Main CLI entry point
│       ├── file_system_operations.py # File I/O and transaction handling
│       └── replace_logic.py      # String replacement logic
├── tests/
│   ├── conftest.py              # Test configuration
│   └── test_mass_find_replace.py # Test suite
├── replacement_mapping.json      # Configuration file
├── requirements.txt             # Production dependencies
├── requirements-dev.txt         # Development dependencies
├── pyproject.toml              # Package configuration
├── README.md                    # This file
└── LICENSE                      # MIT License
```

## 🔮 Future Plans

- PyPI package release
- GUI interface for non-technical users
- Integration with popular IDEs
- Batch configuration management
- Regular expression support
- Parallel processing for large codebases

---

Made with ❤️ by [Emasoft](https://github.com/Emasoft)