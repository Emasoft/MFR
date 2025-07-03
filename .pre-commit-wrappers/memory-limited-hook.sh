#!/usr/bin/env bash
set -euo pipefail

# Use project-local environment variables with validation
MEMORY_LIMIT_MB="${MEMORY_LIMIT_MB:-2048}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-600}"

# Validate numeric inputs
if ! [[ "$MEMORY_LIMIT_MB" =~ ^[0-9]+$ ]]; then
    echo "Error: MEMORY_LIMIT_MB must be a positive integer" >&2
    exit 1
fi

if ! [[ "$TIMEOUT_SECONDS" =~ ^[0-9]+$ ]]; then
    echo "Error: TIMEOUT_SECONDS must be a positive integer" >&2
    exit 1
fi

if [ $# -lt 1 ]; then
    echo "Usage: $0 <command> [args...]" >&2
    echo "Memory limit: ${MEMORY_LIMIT_MB}MB" >&2
    echo "Timeout: ${TIMEOUT_SECONDS}s" >&2
    exit 1
fi

COMMAND="$1"
shift

# Validate command exists
if ! command -v "$COMMAND" &> /dev/null; then
    echo "Error: Command not found: $COMMAND" >&2
    exit 127
fi

# Platform-specific memory limiting
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    ulimit -v $((MEMORY_LIMIT_MB * 1024)) 2>/dev/null || true
    ulimit -d $((MEMORY_LIMIT_MB * 1024)) 2>/dev/null || true
fi

# Cleanup on exit with proper quoting
cleanup() {
    local exit_code=$?
    # Kill child processes of this script
    local children
    children=$(jobs -p 2>/dev/null || true)
    if [[ -n "$children" ]]; then
        # shellcheck disable=SC2086
        kill $children 2>/dev/null || true
    fi
    # Cleanup Python processes
    case "$COMMAND" in
        *python*|*uv*)
            python3 -c "import gc; gc.collect()" 2>/dev/null || true
            ;;
    esac
    exit $exit_code
}
trap cleanup EXIT INT TERM

# Show progress
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running: $COMMAND $*"
echo "Memory limit: ${MEMORY_LIMIT_MB}MB, Timeout: ${TIMEOUT_SECONDS}s"

# Execute with timeout and error handling
if command -v timeout &> /dev/null; then
    exec timeout --preserve-status "$TIMEOUT_SECONDS" "$COMMAND" "$@"
elif command -v gtimeout &> /dev/null; then
    exec gtimeout --preserve-status "$TIMEOUT_SECONDS" "$COMMAND" "$@"
else
    # Fallback: run without timeout
    echo "Warning: timeout command not available, running without timeout" >&2
    exec "$COMMAND" "$@"
fi
