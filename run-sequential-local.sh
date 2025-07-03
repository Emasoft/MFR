#!/usr/bin/env bash
# Execute sequential pre-commit and build pipeline locally
set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT"

# Source environment
source .venv/bin/activate
source .sequential-precommit-env

echo "=== Sequential Local Execution Pipeline ==="
echo "Project: $PROJECT_ROOT"
echo "Python: $(which python)"
echo "Memory Limit: ${MEMORY_LIMIT_MB}MB"
echo "=========================================="

# Phase 1: Pre-commit checks
echo -e "\n[1/3] Running pre-commit checks..."
if pre-commit run --all-files; then
    echo "✓ Pre-commit checks passed"
else
    echo "✗ Pre-commit checks failed"
    exit 1
fi

# Phase 2: Tests (if directory exists)
if [ -d "tests" ]; then
    echo -e "\n[2/3] Running tests sequentially..."
    python -m pytest tests -v --tb=short || exit 1
    echo "✓ Tests passed"
else
    echo -e "\n[2/3] No tests directory found, skipping tests"
fi

# Phase 3: Build (if pyproject.toml exists)
if [ -f "pyproject.toml" ]; then
    echo -e "\n[3/3] Building project..."
    uv build || exit 1
    echo "✓ Build completed"
    ls -la dist/
else
    echo -e "\n[3/3] No pyproject.toml found, skipping build"
fi

echo -e "\n=== Pipeline completed successfully ==="
