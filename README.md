# Mass Find Replace (MFR)

A sophisticated Python tool for safe, surgical find-and-replace operations across directory structures.

## Features

- Transaction-based system for safety and resumability
- Collision detection prevents data loss
- Binary file detection and reporting
- Encoding preservation
- Unicode normalization with diacritic handling
- Multiple execution modes (dry-run, interactive, force, resume)

## Installation

```bash
pip install mass-find-replace
```

## Usage

```bash
# Preview changes (dry run)
mfr . --dry-run

# Execute replacements
mfr .

# Interactive mode
mfr . --interactive

# Resume interrupted operation
mfr . --resume
```

## Development

See CLAUDE.md for development guidelines.