#!/usr/bin/env bash
# Execute sequential pre-commit and build pipeline locally
# Version: 1.0.0
set -euo pipefail

# Script info
readonly SCRIPT_VERSION="1.0.0"
readonly SCRIPT_NAME="$(basename "$0")"

# Interrupt handler
cleanup() {
    local exit_code=$?
    echo
    echo "Pipeline interrupted (exit code: $exit_code)"
    exit $exit_code
}
trap cleanup INT TERM

# Get project root
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT" || exit 1

# Check if virtual environment exists
if [[ ! -f ".venv/bin/activate" ]]; then
    echo "Error: Virtual environment not found. Run setup-sequential-precommit.sh first." >&2
    exit 1
fi

# Check if environment config exists
if [[ ! -f ".sequential-precommit-env" ]]; then
    echo "Error: Sequential pre-commit environment not configured. Run setup-sequential-precommit.sh first." >&2
    exit 1
fi

# Source environment
source .venv/bin/activate || exit 1
source .sequential-precommit-env || exit 1

# Show version and environment info
echo "=== Sequential Local Execution Pipeline v${SCRIPT_VERSION} ==="
echo "Project: $PROJECT_ROOT"
echo "Python: $(which python)"
echo "Python version: $(python --version 2>&1)"
echo "Memory Limit: ${MEMORY_LIMIT_MB:-2048}MB"
echo "Timeout: ${TIMEOUT_SECONDS:-600}s"
echo "=========================================="

# Phase 1: Pre-commit checks
printf "\n[1/3] Running pre-commit checks...\n"
START_TIME=$(date +%s)
if pre-commit run --all-files --show-diff-on-failure; then
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo "✓ Pre-commit checks passed (${DURATION}s)"
else
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))
    echo "✗ Pre-commit checks failed (${DURATION}s)" >&2
    exit 1
fi

# Phase 2: Tests (if directory exists)
if [[ -d "tests" ]]; then
    printf "\n[2/3] Running tests sequentially...\n"
    START_TIME=$(date +%s)
    if python -m pytest tests -v --tb=short --color=yes; then
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        echo "✓ Tests passed (${DURATION}s)"
    else
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        echo "✗ Tests failed (${DURATION}s)" >&2
        exit 1
    fi
else
    printf "\n[2/3] No tests directory found, skipping tests\n"
fi

# Phase 3: Build (if pyproject.toml exists)
if [[ -f "pyproject.toml" ]]; then
    printf "\n[3/3] Building project...\n"
    START_TIME=$(date +%s)
    if uv build; then
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        echo "✓ Build completed (${DURATION}s)"
        echo "Build artifacts:"
        ls -la dist/ 2>/dev/null || echo "No dist directory found"
    else
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        echo "✗ Build failed (${DURATION}s)" >&2
        exit 1
    fi
else
    printf "\n[3/3] No pyproject.toml found, skipping build\n"
fi

# Calculate total duration
TOTAL_END=$(date +%s)
TOTAL_START=${PIPELINE_START:-$TOTAL_END}
TOTAL_DURATION=$((TOTAL_END - TOTAL_START))

printf "\n=== Pipeline completed successfully in ${TOTAL_DURATION}s ===\n"
