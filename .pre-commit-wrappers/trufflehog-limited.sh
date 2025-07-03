#!/usr/bin/env bash
set -euo pipefail

# Use project-local environment variables with validation
TIMEOUT="${TRUFFLEHOG_TIMEOUT:-300}"
CONCURRENCY="${TRUFFLEHOG_CONCURRENCY:-1}"

# Validate numeric inputs
if ! [[ "$TIMEOUT" =~ ^[0-9]+$ ]]; then
    echo "Error: TRUFFLEHOG_TIMEOUT must be a positive integer" >&2
    exit 1
fi

if ! [[ "$CONCURRENCY" =~ ^[0-9]+$ ]]; then
    echo "Error: TRUFFLEHOG_CONCURRENCY must be a positive integer" >&2
    exit 1
fi

# Get project root
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT" || exit 1

# Check if we need to install Trufflehog
TRUFFLEHOG_BIN=".venv/bin/trufflehog"
if [[ ! -x "$TRUFFLEHOG_BIN" ]] && ! command -v trufflehog &> /dev/null; then
    echo "Installing Trufflehog locally..."
    # Install to project-local bin directory
    mkdir -p .venv/bin

    # Download installer script first for security
    INSTALLER_SCRIPT="$(mktemp)"
    if ! curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh -o "$INSTALLER_SCRIPT"; then
        echo "Error: Failed to download Trufflehog installer" >&2
        rm -f "$INSTALLER_SCRIPT"
        exit 1
    fi

    # Verify it's a shell script
    if ! head -1 "$INSTALLER_SCRIPT" | grep -q '^#!/'; then
        echo "Error: Downloaded file is not a shell script" >&2
        rm -f "$INSTALLER_SCRIPT"
        exit 1
    fi

    # Run installer
    if ! sh "$INSTALLER_SCRIPT" -b .venv/bin; then
        echo "Error: Failed to install Trufflehog" >&2
        rm -f "$INSTALLER_SCRIPT"
        exit 1
    fi

    rm -f "$INSTALLER_SCRIPT"

    # Add to PATH for this session
    export PATH="$PROJECT_ROOT/.venv/bin:$PATH"
fi

# Ensure Trufflehog is in PATH
if [[ -x "$TRUFFLEHOG_BIN" ]]; then
    export PATH="$PROJECT_ROOT/.venv/bin:$PATH"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running Trufflehog"
echo "Timeout: ${TIMEOUT}s, Concurrency: ${CONCURRENCY}, Max depth: ${TRUFFLEHOG_MAX_DEPTH:-50}"

# Run with resource limits
if command -v timeout &> /dev/null; then
    timeout_cmd="timeout ${TIMEOUT}s"
elif command -v gtimeout &> /dev/null; then
    timeout_cmd="gtimeout ${TIMEOUT}s"
else
    timeout_cmd=""
fi

# Check for exclude file
EXCLUDE_ARGS=""
if [[ -f ".trufflehog-exclude" ]]; then
    EXCLUDE_ARGS="--exclude-paths .trufflehog-exclude"
fi

# Run Trufflehog with all options
# shellcheck disable=SC2086
$timeout_cmd trufflehog git file://. \
    --only-verified \
    --fail \
    --no-update \
    --concurrency="$CONCURRENCY" \
    --max-depth="${TRUFFLEHOG_MAX_DEPTH:-50}" \
    $EXCLUDE_ARGS || exit_code=$?

if [ "${exit_code:-0}" -eq 124 ]; then
    echo "Warning: Trufflehog timed out after ${TIMEOUT}s"
    exit 0
elif [ "${exit_code:-0}" -ne 0 ]; then
    echo "Error: Trufflehog found verified secrets!"
    exit 1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ No verified secrets found"
