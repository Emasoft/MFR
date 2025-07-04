#!/usr/bin/env bash
# safe-run.sh - Wrapper that delegates to sequential-executor.sh
# Usage: ./scripts/safe-run.sh <command> [args...]
#
# This wrapper ensures TRUE sequential execution by using the
# sequential-executor.sh which enforces one-at-a-time execution.

set -euo pipefail

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEQUENTIAL_EXECUTOR="${SCRIPT_DIR}/sequential-executor.sh"

# Check if sequential executor exists
if [ ! -x "$SEQUENTIAL_EXECUTOR" ]; then
    echo "ERROR: sequential-executor.sh not found or not executable" >&2
    echo "Path: $SEQUENTIAL_EXECUTOR" >&2
    exit 1
fi

# Delegate to sequential executor
exec "$SEQUENTIAL_EXECUTOR" "$@"