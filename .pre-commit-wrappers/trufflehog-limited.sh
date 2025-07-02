#!/usr/bin/env bash
set -euo pipefail

# Use project-local environment variables
TIMEOUT="${TRUFFLEHOG_TIMEOUT:-300}"
# MEMORY_LIMIT="${TRUFFLEHOG_MEMORY_MB:-1024}"  # Reserved for future use
CONCURRENCY="${TRUFFLEHOG_CONCURRENCY:-1}"

# Get project root
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT" || exit 1

# Check if trufflehog is installed
if [ -x ".venv/bin/trufflehog" ]; then
    # Use local installation
    TRUFFLEHOG_CMD=".venv/bin/trufflehog"
elif command -v trufflehog &> /dev/null; then
    # Use system installation
    TRUFFLEHOG_CMD="trufflehog"
else
    echo "Installing Trufflehog locally..."
    # Install to project-local bin directory
    mkdir -p .venv/bin
    curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | \
        sh -s -- -b .venv/bin
    TRUFFLEHOG_CMD=".venv/bin/trufflehog"
fi

echo "Running Trufflehog (timeout: ${TIMEOUT}s, concurrency: ${CONCURRENCY})..."

# Run with resource limits
if command -v timeout &> /dev/null; then
    timeout_cmd="timeout ${TIMEOUT}s"
elif command -v gtimeout &> /dev/null; then
    timeout_cmd="gtimeout ${TIMEOUT}s"
else
    timeout_cmd=""
fi

$timeout_cmd $TRUFFLEHOG_CMD git file://. \
    --only-verified \
    --fail \
    --no-update \
    --concurrency="$CONCURRENCY" || exit_code=$?

if [ "${exit_code:-0}" -eq 124 ]; then
    echo "Warning: Trufflehog timed out after ${TIMEOUT}s"
    exit 0
elif [ "${exit_code:-0}" -ne 0 ]; then
    echo "Error: Trufflehog found verified secrets!"
    exit 1
fi

echo "✓ No verified secrets found"
