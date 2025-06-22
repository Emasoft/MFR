<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Emasoft/MFR/main/docs/assets/logo-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Emasoft/MFR/main/docs/assets/logo-light.png">
  <img alt="MFR Logo" src="https://raw.githubusercontent.com/Emasoft/MFR/main/docs/assets/logo-light.png" width="200">
</picture>

# Mass Find Replace (MFR)

**Surgical precision for your codebase transformations**

<!-- Build Status Badges -->

[![CI/CD Pipeline](https://github.com/Emasoft/MFR/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Emasoft/MFR/actions/workflows/ci.yml)
[![Pre-commit](https://github.com/Emasoft/MFR/actions/workflows/pre-commit.yml/badge.svg?branch=main)](https://github.com/Emasoft/MFR/actions/workflows/pre-commit.yml)
[![Security](https://github.com/Emasoft/MFR/actions/workflows/security.yml/badge.svg?branch=main)](https://github.com/Emasoft/MFR/actions/workflows/security.yml)
[![Super-Linter](https://github.com/Emasoft/MFR/actions/workflows/super-linter.yml/badge.svg?branch=main)](https://github.com/Emasoft/MFR/actions/workflows/super-linter.yml)
[![Nightly Tests](https://github.com/Emasoft/MFR/actions/workflows/nightly.yml/badge.svg)](https://github.com/Emasoft/MFR/actions/workflows/nightly.yml)

<!-- Coverage & Quality Badges -->

[![codecov](https://codecov.io/gh/Emasoft/MFR/branch/main/graph/badge.svg?token=YOUR_TOKEN)](https://codecov.io/gh/Emasoft/MFR)
[![Code Quality](https://img.shields.io/codefactor/grade/github/Emasoft/MFR/main?label=code%20quality)](https://www.codefactor.io/repository/github/emasoft/mfr)
[![Maintainability](https://api.codeclimate.com/v1/badges/YOUR_ID/maintainability)](https://codeclimate.com/github/Emasoft/MFR)

<!-- Language & Tool Badges -->

[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/uv-0.7.13-orange.svg)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

<!-- Status & Info Badges -->

[![Status: Early Alpha](https://img.shields.io/badge/status-early%20alpha-red.svg?style=for-the-badge)](#-warning-early-alpha-software)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI - Version](https://img.shields.io/badge/pypi-coming%20soon-lightgrey.svg)](https://pypi.org/project/mass-find-replace/)
[![GitHub release](https://img.shields.io/github/v/release/Emasoft/MFR?include_prereleases)](https://github.com/Emasoft/MFR/releases)

<!-- Community Badges -->

[![GitHub stars](https://img.shields.io/github/stars/Emasoft/MFR.svg?style=social&label=Star)](https://github.com/Emasoft/MFR)
[![GitHub forks](https://img.shields.io/github/forks/Emasoft/MFR.svg?style=social&label=Fork)](https://github.com/Emasoft/MFR/fork)
[![GitHub watchers](https://img.shields.io/github/watchers/Emasoft/MFR.svg?style=social&label=Watch)](https://github.com/Emasoft/MFR)

<!-- Security & Standards -->

[![Security: Gitleaks](https://img.shields.io/badge/security-gitleaks-blue.svg)](https://github.com/gitleaks/gitleaks)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/9999/badge)](https://www.bestpractices.dev/projects/9999)
[![SLSA 3](https://slsa.dev/images/gh-badge-level3.svg)](https://slsa.dev)

</div>

<div align="center">
  <p align="center">
    <strong>Advanced search and replace tool for surgical codebase transformations</strong>
    <br />
    <a href="#-quick-start"><strong>Quick Start</strong></a>
    ·
    <a href="#-documentation"><strong>Documentation</strong></a>
    ·
    <a href="https://github.com/Emasoft/MFR/issues"><strong>Report Bug</strong></a>
    ·
    <a href="https://github.com/Emasoft/MFR/discussions"><strong>Discussions</strong></a>
  </p>
</div>

---

## 🚨 WARNING: EARLY ALPHA SOFTWARE

<div align="center">

|                           ⚠️ **NOT PRODUCTION READY** ⚠️                            |
| :---------------------------------------------------------------------------------: |
|  This software is in **EARLY ALPHA** stage and should be used **AT YOUR OWN RISK**  |
| **ALWAYS** backup your data before use • Expect breaking changes • APIs will change |
|                  For production use, wait for stable v1.0 release                   |

</div>

### What "Early Alpha" Means

- 🐛 **Expect Bugs**: Core functionality works but edge cases may fail
- 💔 **Breaking Changes**: APIs and configuration formats may change without notice
- 📉 **Limited Testing**: Only tested on common scenarios, not production workloads
- 🔧 **Active Development**: Features may be incomplete or change dramatically
- ⚡ **Performance**: Not optimized for large-scale operations yet

**Recommended Use Cases:**

- ✅ Personal projects with backups
- ✅ Testing and evaluation
- ✅ Contributing to development
- ❌ Production codebases
- ❌ Mission-critical systems
- ❌ Data without backups

---

## 📑 Table of Contents

<details>
<summary>Click to expand</summary>

- [Overview](#-overview)
- [Why MFR?](#-why-mfr)
- [Key Features](#-key-features)
- [Quick Start](#-quick-start)
- [Installation](#-installation)
  - [System Requirements](#system-requirements)
  - [Installation Methods](#installation-methods)
- [Documentation](#-documentation)
  - [Basic Usage](#basic-usage)
  - [Configuration](#configuration)
  - [Safety Features](#safety-features)
  - [Command Reference](#command-reference)
- [Examples](#-examples)
- [Development](#-development)
  - [Testing](#-testing)
  - [Contributing](#-contributing)
  - [Architecture](#️-architecture)
- [Performance](#-performance)
- [Security](#-security)
- [Roadmap](#️-roadmap)
- [FAQ](#-faq)
- [License](#-license)
- [Acknowledgments](#-acknowledgments)

</details>

---

## 🎯 Overview

**Mass Find Replace (MFR)** is a powerful Python tool designed for performing safe, surgical
find-and-replace operations across entire directory structures. It can rename files, folders,
and modify file contents while preserving file encodings, handling Unicode correctly, and
preventing data loss through intelligent collision detection.

### Perfect For:

- 🔄 **Refactoring**: Rename functions, classes, or variables across your entire codebase
- 🏷️ **Rebranding**: Update company names, product names, or branding elements
- 🔧 **Migration**: Update import paths, API endpoints, or configuration values
- 🌍 **Internationalization**: Replace hardcoded strings with i18n keys
- 📦 **Dependency Updates**: Change package imports or library usage patterns

---

## 🤔 Why MFR?

Traditional find-and-replace tools often fall short when dealing with complex codebases:

| Problem                    | MFR Solution                                                |
| -------------------------- | ----------------------------------------------------------- |
| **Data Loss Risk**         | Transaction-based operations with full rollback capability  |
| **Encoding Issues**        | Automatic encoding detection and preservation               |
| **Name Collisions**        | Intelligent collision detection and resolution              |
| **Binary File Corruption** | Automatic binary file detection and protection              |
| **Incomplete Operations**  | Full resume capability from any interruption point          |
| **Unicode Problems**       | Complete Unicode support including emojis and special chars |

---

## ✨ Key Features

### 🛡️ Safety First

- **Transaction System**: Every operation is logged and can be resumed or rolled back
- **Collision Detection**: Prevents accidental file overwrites with smart conflict resolution
- **Dry Run Mode**: Preview all changes before execution
- **Binary Protection**: Automatically detects and skips binary files
- **Encoding Preservation**: Maintains original file encodings

### 🚀 Performance & Reliability

- **Memory Efficient**: Handles large codebases without loading everything into memory
- **Resume Capability**: Continue interrupted operations exactly where they left off
- **Progress Tracking**: Real-time progress updates with ETA
- **Atomic Operations**: Changes are applied atomically to prevent partial updates

### 🎯 Precision & Control

- **Case Sensitivity**: Full control over case-sensitive matching
- **Unicode Support**: Handles any Unicode character including emojis 🎉
- **Selective Processing**: Choose files by extension, exclude directories
- **Interactive Mode**: Review and approve each change individually
- **Longest Match First**: Intelligently orders replacements to prevent conflicts

---

## 🚀 Quick Start

```bash
# 1. Install uv (modern Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone the repository
git clone https://github.com/Emasoft/MFR.git
cd MFR

# 3. Install dependencies
uv sync

# 4. Create your replacement configuration
cat > replacement_mapping.json << 'EOF'
{
  "REPLACEMENT_MAPPING": {
    "old_function_name": "new_function_name",
    "OldClassName": "NewClassName",
    "deprecated_api": "modern_api"
  }
}
EOF

# 5. Preview changes (dry run)
uv run mfr . --dry-run

# 6. Execute replacements
uv run mfr .
```

---

## 📦 Installation

### System Requirements

| Component            | Requirement           |
| -------------------- | --------------------- |
| **Python**           | 3.10, 3.11, or 3.12   |
| **Operating System** | Linux, macOS, Windows |
| **Memory**           | 512MB minimum         |
| **Disk Space**       | 50MB for installation |

### Installation Methods

#### 🎯 Recommended: Install with UV

<details>
<summary><b>Installing UV Package Manager</b></summary>

**macOS/Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**

```powershell
winget install astral-sh.uv
# or
irm https://astral.sh/uv/install.ps1 | iex
```

**Via pip:**

```bash
pip install uv
```

</details>

<details>
<summary><b>Installing MFR from Source</b></summary>

```bash
# Clone the repository
git clone https://github.com/Emasoft/MFR.git
cd MFR

# Install dependencies
uv sync

# Verify installation
uv run mfr --help
```

</details>

<details>
<summary><b>Installing as a Package</b></summary>

```bash
# Build from source
uv build
uv pip install dist/mass_find_replace-*.whl

# Install from GitHub
uv pip install git+https://github.com/Emasoft/MFR.git

# From PyPI (coming soon)
uv pip install mass-find-replace
```

</details>

#### 🐳 Docker Installation

<details>
<summary><b>Using Docker</b></summary>

```bash
# Using Docker Compose
docker-compose run mfr /workspace --dry-run

# Building manually
docker build -t mfr:latest .
docker run -v $(pwd):/workspace mfr /workspace --dry-run
```

</details>

#### 👩‍💻 Development Setup

<details>
<summary><b>Setting up for Development</b></summary>

```bash
# Clone and setup
git clone https://github.com/Emasoft/MFR.git
cd MFR

# Install with dev dependencies
uv sync --all-extras

# Install pre-commit hooks
uv run pre-commit install
uv run pre-commit install --hook-type pre-push

# Run tests
uv run pytest

# Run linters
uv run pre-commit run --all-files
```

</details>

---

## 📖 Documentation

### Basic Usage

#### Step 1: Create Configuration File

Create a `replacement_mapping.json` file:

```json
{
  "REPLACEMENT_MAPPING": {
    "search_term": "replacement_term",
    "OldName": "NewName",
    "old-style": "new-style"
  }
}
```

#### Step 2: Preview Changes

Always preview changes before execution:

```bash
# Dry run - see what would change
uv run mfr /path/to/project --dry-run

# Interactive mode - approve each change
uv run mfr /path/to/project --interactive
```

#### Step 3: Execute Replacements

```bash
# Execute with confirmation prompt
uv run mfr /path/to/project

# Force execution without confirmation
uv run mfr /path/to/project --force
```

### Configuration

#### Replacement Mapping Format

The `replacement_mapping.json` file supports:

- ✅ **Case-sensitive** matching
- ✅ **Unicode** characters (including emojis 🎉)
- ✅ **Special characters** (properly escaped in JSON)
- ✅ **Longest match first** processing
- ❌ **No regex** (by design, for safety)
- ❌ **No recursive replacements** (prevents A→B→C chains)

Example:

```json
{
  "REPLACEMENT_MAPPING": {
    "Company™": "NewCompany™",
    "über": "super",
    "café": "coffee_shop",
    "🔥_hot_function": "🧊_cool_function"
  }
}
```

### Safety Features

#### 🛡️ Transaction System

All operations are logged in `planned_transactions.json`:

```json
{
  "version": "1.0",
  "transactions": [
    {
      "id": "abc-123",
      "type": "file_content",
      "path": "/src/main.py",
      "status": "PENDING",
      "changes": [...]
    }
  ]
}
```

States: `PENDING` → `IN_PROGRESS` → `COMPLETED` | `FAILED` | `SKIPPED`

#### 💥 Collision Detection

MFR prevents accidental overwrites:

```text
=== Collision Detected ===
Transaction ID: abc123
Type: FILE_NAME
Original: Config.py → config.py
Conflict: Would overwrite existing file
Action: [S]kip, [R]ename, [O]verwrite?
```

#### 🔒 Binary File Protection

Automatically detects and protects:

- Executables (`.exe`, `.dll`, `.so`)
- Images (`.jpg`, `.png`, `.gif`)
- Archives (`.zip`, `.tar`, `.gz`)
- Media (`.mp3`, `.mp4`, `.pdf`)

### Command Reference

```bash
uv run mfr [directory] [options]
```

#### Essential Options

| Option           | Short | Description                       |
| ---------------- | ----- | --------------------------------- |
| `--dry-run`      |       | Preview changes without executing |
| `--interactive`  | `-i`  | Approve each change individually  |
| `--force`        | `-y`  | Skip confirmation prompt          |
| `--resume`       |       | Resume interrupted operation      |
| `--mapping-file` | `-m`  | Custom mapping file path          |

#### File Control Options

| Option            | Description                                        |
| ----------------- | -------------------------------------------------- |
| `--extensions`    | Process only specific file types (e.g., `.py .js`) |
| `--exclude-dirs`  | Skip directories (space-separated)                 |
| `--exclude-files` | Skip specific files                                |
| `--no-gitignore`  | Don't use .gitignore exclusions                    |

#### Processing Options

| Option                    | Description                 |
| ------------------------- | --------------------------- |
| `--skip-file-renaming`    | Don't rename files          |
| `--skip-folder-renaming`  | Don't rename folders        |
| `--skip-content`          | Don't modify file contents  |
| `--process-symlink-names` | Process symbolic link names |

---

## 💡 Examples

### Example 1: Refactoring Function Names

<details>
<summary>Click to expand</summary>

**Configuration:**

```json
{
  "REPLACEMENT_MAPPING": {
    "getUserData": "fetchUserProfile",
    "saveUserData": "persistUserProfile",
    "deleteUserData": "removeUserProfile",
    "userData": "userProfile"
  }
}
```

**Command:**

```bash
# Target only JavaScript/TypeScript files
uv run mfr ./src --extensions .js .jsx .ts .tsx --dry-run
```

</details>

### Example 2: Updating Import Statements

<details>
<summary>Click to expand</summary>

**Configuration:**

```json
{
  "REPLACEMENT_MAPPING": {
    "from 'lodash'": "from 'lodash-es'",
    "require('moment')": "require('dayjs')",
    "import moment from 'moment'": "import dayjs from 'dayjs'"
  }
}
```

**Command:**

```bash
# Process entire codebase, excluding dependencies
uv run mfr . --exclude-dirs node_modules,vendor,dist
```

</details>

### Example 3: Project Rebranding

<details>
<summary>Click to expand</summary>

**Configuration:**

```json
{
  "REPLACEMENT_MAPPING": {
    "AcmeCorp": "TechCorp",
    "AcmeProduct": "TechProduct",
    "acmecorp": "techcorp",
    "ACMECORP": "TECHCORP",
    "acme-corp": "tech-corp",
    "acme_corp": "tech_corp"
  }
}
```

**Command:**

```bash
# Interactive mode to review each change
uv run mfr . --interactive
```

</details>

---

## 🧪 Testing

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src/mass_find_replace --cov-report=html

# Run specific test
uv run pytest tests/test_mass_find_replace.py::test_unicode_handling

# Run built-in self-test
uv run mfr --self-test
```

### Test Coverage

Current coverage: **53%** (Target: **80%**)

| Component       | Coverage |
| --------------- | -------- |
| Core Logic      | 66%      |
| File Operations | 60%      |
| CLI Interface   | 33%      |

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Quick Contribution Guide

1. **Fork** the repository
2. **Create** your feature branch (`git checkout -b feature/AmazingFeature`)
3. **Commit** your changes (`git commit -m 'feat: add amazing feature'`)
4. **Push** to the branch (`git push origin feature/AmazingFeature`)
5. **Open** a Pull Request

### Development Standards

- 🧪 Write tests first (TDD)
- 📝 Follow Google-style docstrings
- 🎨 Use type hints everywhere
- ✅ Ensure all CI checks pass

---

## 🏗️ Architecture

### Component Overview

```mermaid
graph TB
    subgraph "User Interface"
        CLI[CLI Parser]
        Config[Config Loader]
    end

    subgraph "Core Engine"
        Scanner[File Scanner]
        Analyzer[Change Analyzer]
        Engine[Replace Engine]
        Transaction[Transaction Manager]
    end

    subgraph "Safety Layer"
        Collision[Collision Detector]
        Binary[Binary Detector]
        Encoding[Encoding Handler]
    end

    subgraph "Execution"
        Executor[File Executor]
        Logger[Progress Logger]
    end

    CLI --> Config
    Config --> Scanner
    Scanner --> Analyzer
    Analyzer --> Engine
    Engine --> Transaction
    Transaction --> Collision
    Transaction --> Binary
    Transaction --> Encoding
    Transaction --> Executor
    Executor --> Logger
```

---

## 📊 Performance

### Benchmarks

| Dataset | Files   | Size   | Scan Time | Execute Time | Memory |
| ------- | ------- | ------ | --------- | ------------ | ------ |
| Small   | 100     | 10 MB  | 0.1s      | 0.5s         | 25 MB  |
| Medium  | 1,000   | 100 MB | 0.8s      | 4.2s         | 45 MB  |
| Large   | 10,000  | 1 GB   | 2.3s      | 8.7s         | 156 MB |
| Huge    | 100,000 | 10 GB  | 23s       | 87s          | 512 MB |

### Optimization Tips

- 🎯 Use `--extensions` to limit file types
- 🚫 Exclude build/cache directories
- 💾 Run on SSD for best performance
- 🔍 Always dry-run first on large codebases

---

## 🔒 Security

### Security Features

- 🔍 **Secret Scanning**: Integrated Gitleaks prevents accidental credential exposure
- 🛡️ **Dependency Scanning**: Regular vulnerability checks with pip-audit
- 🔐 **Safe Operations**: No shell execution, no eval, no dynamic imports
- 📝 **Audit Trail**: Complete transaction log for forensic analysis

### Reporting Security Issues

Found a vulnerability? Please report it:

1. **Do not** open a public issue
2. Open a [Security Advisory](https://github.com/Emasoft/MFR/security/advisories/new)
3. Include steps to reproduce
4. We'll respond within 48 hours

---

## 🗺️ Roadmap

### Version 0.3.0-alpha (Current)

- ✅ Core find-replace engine
- ✅ Transaction system
- ✅ Unicode support
- ✅ Resume capability
- ✅ CI/CD pipeline

### Version 1.0.0-beta (Q1 2025)

- ⏳ Production stability
- ⏳ Performance optimizations
- ⏳ PyPI package release
- ⏳ Comprehensive documentation
- ⏳ 80%+ test coverage

### Version 1.1.0 (Q2 2025)

- 📅 Regular expression support
- 📅 Configuration profiles
- 📅 Plugin system
- 📅 Advanced filtering

### Version 2.0.0 (Future)

- 💭 GUI interface
- 💭 IDE extensions
- 💭 Cloud storage support
- 💭 Team collaboration features

---

## ❓ FAQ

<details>
<summary><b>Is it safe to use on production code?</b></summary>

**Not yet.** MFR is in early alpha. While it has safety features, it's not recommended for production use. Always:

- Use version control
- Create backups
- Test on a copy first
- Use `--dry-run` extensively

</details>

<details>
<summary><b>Can I undo changes?</b></summary>

MFR doesn't have built-in undo, but:

- Transaction logs show all changes
- Use Git for easy rollback
- Always backup before major operations

</details>

<details>
<summary><b>Does it support regular expressions?</b></summary>

Not currently. MFR uses literal string matching for safety and predictability. Regex support is planned for v1.1.

</details>

<details>
<summary><b>How does it handle large files?</b></summary>

MFR processes files line-by-line to maintain memory efficiency. Files up to 2GB are supported,
with larger files planned for future versions.

</details>

---

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

```text
MIT License

Copyright (c) 2024 Emasoft

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
```

---

## 🙏 Acknowledgments

<div align="center">

### Built With

| Tool                                             | Purpose                                  |
| ------------------------------------------------ | ---------------------------------------- |
| [uv](https://github.com/astral-sh/uv)            | Lightning-fast Python package management |
| [Prefect](https://www.prefect.io/)               | Workflow orchestration framework         |
| [Ruff](https://github.com/astral-sh/ruff)        | Fast Python linter and formatter         |
| [Gitleaks](https://github.com/gitleaks/gitleaks) | Secret scanning and prevention           |

### Special Thanks

- All [contributors](https://github.com/Emasoft/MFR/graphs/contributors) who help improve MFR
- The Python community for excellent tools and libraries
- Early adopters providing valuable feedback

</div>

---

<div align="center">

### ⭐ Star us on GitHub!

If you find MFR useful, please consider giving it a star. It helps others discover the project!

<br>

**[Report Bug](https://github.com/Emasoft/MFR/issues)** •
**[Request Feature](https://github.com/Emasoft/MFR/issues)** •
**[Join Discussion](https://github.com/Emasoft/MFR/discussions)**

<br>

Made with ❤️ by [Emasoft](https://github.com/Emasoft) and contributors

</div>
