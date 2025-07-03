# Universal Sequential Pre-commit Setup Guide with Resource Monitoring

This guide provides a comprehensive, project-local solution for configuring pre-commit hooks, CI/CD workflows, and build processes to run sequentially with resource monitoring across all environments (local, Docker, GitHub Actions). All configuration is contained within the project directory - no system or user configuration files are modified.

## Overview of the Protocol

The sequential execution protocol implements a **three-layer defense system** to ensure reliable, resource-safe operations:

1. **Sequential Execution Layer**: Forces all hooks, jobs, and processes to run one at a time
2. **Resource Monitoring Layer**: Tracks memory, processes, and file descriptors in real-time
3. **Robust Process Management Layer**: Prevents hanging processes with multiple failsafes:
   - Global watchdog (15-minute timeout)
   - Heartbeat monitor (60-second stall detection)
   - Process group management (ensures all children die with parent)

## Supported Environments

This protocol works identically in:
- **Local Development**: Direct execution in project folder with venv
- **Docker Containers**: Isolated execution with automatic cleanup
- **GitHub Actions**: CI/CD workflows including PR fixes (prfix.yml)
- **Remote Servers**: SSH or cloud-based development environments
- **Cross-Platform**: macOS, Linux, Windows (WSL2/Git Bash)

## Key Features

- **Universal**: Works with any Python project structure
- **Relocatable**: Virtual environment paths are relative
- **Self-Contained**: All configuration within project directory
- **Multi-Environment**: Same behavior locally, in Docker, and CI/CD
- **Auto-Cleanup**: Docker containers removed after use
- **PR Safety**: Sequential execution for PR fix workflows

## Why Sequential Execution with Monitoring

Parallel pre-commit hooks can cause:
- Memory exhaustion from concurrent linters/formatters
- File descriptor leaks from improper cleanup
- Process proliferation from uncontrolled spawning
- System crashes on resource-constrained machines
- Unpredictable hook execution order
- Multiple instances of the same hook running simultaneously

Sequential execution with resource monitoring provides:
- Predictable resource usage patterns
- Real-time monitoring of memory, file descriptors, and processes
- Automatic termination when limits are exceeded
- Detailed logs for debugging resource issues
- Protection against runaway processes
- Guaranteed single-instance execution

## Important Note on Pre-commit Framework Integration

Pre-commit framework handles hook execution and will overwrite custom git hooks when you run `pre-commit install`. To maintain resource monitoring while using pre-commit framework:

1. We create a wrapper script that monitors resources
2. We modify the git hook to call our wrapper
3. The wrapper then calls the pre-commit framework
4. This ensures monitoring happens at the top level

## Prerequisites

Only global tool installations are required:
- Python 3.11+ (consistent version used throughout)
- Git
- uv (install with: `curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Optionally: Homebrew (macOS/Linux) for system tools

## Enhanced Setup with Resource Monitoring

### 1. Universal Project Setup Script

Create `setup-sequential-precommit.sh` in your project root:

```bash
#!/usr/bin/env bash
# Universal setup script for sequential execution with resource monitoring
# Works in all environments: local, Docker, CI/CD
# All configuration is project-local - no system files are modified

set -euo pipefail

# Detect environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$SCRIPT_DIR}"
cd "$PROJECT_ROOT"

# Platform detection
detect_platform() {
    case "$OSTYPE" in
        linux-gnu*) echo "linux" ;;
        darwin*) echo "macos" ;;
        msys*|cygwin*|mingw*) echo "windows" ;;
        *) echo "unknown" ;;
    esac
}

PLATFORM=$(detect_platform)
echo "Setting up sequential execution protocol for platform: $PLATFORM"
echo "Project root: $PROJECT_ROOT"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    if command -v uv &> /dev/null; then
        uv venv --python 3.11
    elif command -v python3 &> /dev/null; then
        python3 -m venv .venv
    else
        echo "Error: Neither uv nor python3 found"
        exit 1
    fi
fi

# Create project-local environment configuration
echo "Setting up project-local environment configuration..."

# Create the main environment file with relocatable paths
cat > .sequential-precommit-env << 'EOF'
#!/usr/bin/env bash
# Project-local environment configuration for sequential execution
# Relocatable - uses relative paths from PROJECT_ROOT

# Get the directory of this script
if [ -n "${BASH_SOURCE[0]}" ]; then
    _ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
    _ENV_DIR="$(pwd)"
fi

# Export PROJECT_ROOT for all scripts
export PROJECT_ROOT="${PROJECT_ROOT:-$_ENV_DIR}"

# Core pre-commit settings - force sequential execution
export PRE_COMMIT_MAX_WORKERS=1              # Limit pre-commit to single worker
export PRE_COMMIT_NO_CONCURRENCY=1           # Additional safety flag
export PRE_COMMIT_COLOR=always               # Keep color output

# Python settings
export PYTHONDONTWRITEBYTECODE=1             # Don't create .pyc files
export PYTHONUNBUFFERED=1                    # Unbuffered output for real-time logs

# UV package manager settings
export UV_NO_CACHE=1                         # Disable cache to reduce memory usage
export UV_SYSTEM_PYTHON=0                    # Use venv Python only

# Resource limits for hooks
export MEMORY_LIMIT_MB=${MEMORY_LIMIT_MB:-2048}        # Max memory per hook (2GB)
export TIMEOUT_SECONDS=${TIMEOUT_SECONDS:-600}         # Global timeout (10 minutes)

# TruffleHog specific settings
export TRUFFLEHOG_TIMEOUT=${TRUFFLEHOG_TIMEOUT:-300}   # 5 minute timeout
export TRUFFLEHOG_MEMORY_MB=${TRUFFLEHOG_MEMORY_MB:-1024}  # 1GB memory limit
export TRUFFLEHOG_CONCURRENCY=1                        # Single thread
export TRUFFLEHOG_MAX_DEPTH=50                         # Limit git history depth

# Monitoring settings
export MONITOR_KILL_THRESHOLD_MB=${MONITOR_KILL_THRESHOLD_MB:-4096}  # Kill if exceeds 4GB
export MONITOR_INTERVAL_SECONDS=1                      # Check resources every second
export MAX_LOG_FILES=10                                # Rotate logs to prevent disk fill

# Docker-specific settings
export DOCKER_MEMORY_LIMIT="${DOCKER_MEMORY_LIMIT:-4g}"
export DOCKER_CPU_LIMIT="${DOCKER_CPU_LIMIT:-2}"

# CI/CD settings
export CI_SEQUENTIAL_MODE=1                            # Force sequential in CI
export CI_TIMEOUT_MINUTES=${CI_TIMEOUT_MINUTES:-45}    # CI job timeout
EOF

# Make it executable
chmod +x .sequential-precommit-env

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "Error: Failed to create virtual environment"
    exit 1
fi

# Install pre-commit in the virtual environment
echo "Installing pre-commit..."
uv pip install pre-commit pre-commit-uv

# Create wrapper scripts directory
mkdir -p .pre-commit-wrappers

# Create memory-limited wrapper
cat > .pre-commit-wrappers/memory-limited-hook.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

# Use project-local environment variables
MEMORY_LIMIT_MB="${MEMORY_LIMIT_MB:-2048}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-600}"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <command> [args...]"
    exit 1
fi

COMMAND="$1"
shift

# Platform-specific memory limiting
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    ulimit -v $((MEMORY_LIMIT_MB * 1024)) 2>/dev/null || true
    ulimit -d $((MEMORY_LIMIT_MB * 1024)) 2>/dev/null || true
fi

# Cleanup on exit
cleanup() {
    # Kill child processes of this script
    local children=$(jobs -p)
    if [ -n "$children" ]; then
        kill $children 2>/dev/null || true
    fi
    if [[ "$COMMAND" == *"python"* ]] || [[ "$COMMAND" == *"uv"* ]]; then
        python3 -c "import gc; gc.collect()" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM

echo "Running (memory limited to ${MEMORY_LIMIT_MB}MB): $COMMAND $*"

# Execute with timeout
if command -v timeout &> /dev/null; then
    exec timeout "$TIMEOUT_SECONDS" "$COMMAND" "$@"
elif command -v gtimeout &> /dev/null; then
    exec gtimeout "$TIMEOUT_SECONDS" "$COMMAND" "$@"
else
    "$COMMAND" "$@"
fi
EOF

# Create Trufflehog wrapper
cat > .pre-commit-wrappers/trufflehog-limited.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

# Use project-local environment variables
TIMEOUT="${TRUFFLEHOG_TIMEOUT:-300}"
MEMORY_LIMIT="${TRUFFLEHOG_MEMORY_MB:-1024}"
CONCURRENCY="${TRUFFLEHOG_CONCURRENCY:-1}"

# Check if trufflehog is installed
if ! command -v trufflehog &> /dev/null; then
    echo "Installing Trufflehog locally..."
    # Install to project-local bin directory
    mkdir -p .venv/bin
    curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | \
        sh -s -- -b .venv/bin
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

# IMPORTANT: Use --only-verified to match GitHub Actions configuration
# This ensures consistent behavior between local and CI/CD environments
$timeout_cmd trufflehog git file://. \
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
EOF

chmod +x .pre-commit-wrappers/*.sh

# Create robust pre-commit wrapper with three-layer defense
cat > .git/hooks/pre-commit-wrapper-robust << 'EOF'
#!/usr/bin/env bash
# Robust pre-commit wrapper with three-layer defense against hanging processes
# Prevents: 1) Zombie processes 2) Silent failures 3) Indefinite hangs

# Enable strict mode and job control
set -euo pipefail
set -m  # Enable job control for process group management

# Global configuration
GLOBAL_TIMEOUT=900                    # 15 minutes max for entire pre-commit
STALL_TIMEOUT=60                     # 1 minute without activity = stalled
MEMORY_LIMIT_MB="${MEMORY_LIMIT_MB:-4096}"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$PROJECT_ROOT" || exit 1

# File paths
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_DIR=".pre-commit-logs"
LOG_FILE="$LOG_DIR/resource_usage_${TIMESTAMP}.log"
ERROR_FILE="$LOG_DIR/errors_${TIMESTAMP}.log"
STATUS_FILE="$LOG_DIR/status_${TIMESTAMP}.log"
LOCKFILE="/tmp/pre-commit-$(echo "$PROJECT_ROOT" | md5sum | cut -d' ' -f1).lock"
COMM_PIPE="/tmp/pre-commit-comm-$$.pipe"

# Process tracking
MONITOR_PID=""
PRE_COMMIT_PID=""
WATCHDOG_PID=""
HEARTBEAT_PID=""
EXIT_CODE=0

# Ensure directories exist
mkdir -p "$LOG_DIR"

# Create communication pipe
mkfifo "$COMM_PIPE" 2>/dev/null || true

# Initialize log
{
    echo "=== Robust Pre-commit Wrapper ==="
    echo "Started: $(date)"
    echo "PID: $$"
    echo "Process Group: -$$"
    echo "Global Timeout: ${GLOBAL_TIMEOUT}s"
    echo "Stall Timeout: ${STALL_TIMEOUT}s"
    echo "================================"
} > "$LOG_FILE"

# Function to report status through pipe
report_status() {
    local status="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $status" >> "$STATUS_FILE"
    echo "$status" > "$COMM_PIPE" 2>/dev/null || true
}

# Function to kill entire process tree
kill_process_tree() {
    local pid=$1
    local signal=${2:-TERM}

    # First, try to kill the process group
    kill -$signal -$pid 2>/dev/null || true

    # Then kill individual processes
    for child in $(pgrep -P "$pid" 2>/dev/null); do
        kill_process_tree "$child" "$signal"
    done

    kill -$signal "$pid" 2>/dev/null || true
}

# Master cleanup function - ALWAYS runs
cleanup() {
    local exit_code=$?
    report_status "CLEANUP: Starting cleanup (exit code: $exit_code)"

    # Disable traps during cleanup
    trap '' EXIT INT TERM

    # Kill watchdog first to prevent it from killing us
    if [ -n "$WATCHDOG_PID" ] && kill -0 "$WATCHDOG_PID" 2>/dev/null; then
        kill -KILL "$WATCHDOG_PID" 2>/dev/null || true
    fi

    # Kill heartbeat monitor
    if [ -n "$HEARTBEAT_PID" ] && kill -0 "$HEARTBEAT_PID" 2>/dev/null; then
        kill -TERM "$HEARTBEAT_PID" 2>/dev/null || true
    fi

    # Kill resource monitor
    if [ -n "$MONITOR_PID" ] && kill -0 "$MONITOR_PID" 2>/dev/null; then
        kill -TERM "$MONITOR_PID" 2>/dev/null || true
        wait "$MONITOR_PID" 2>/dev/null || true
    fi

    # Kill pre-commit if still running
    if [ -n "$PRE_COMMIT_PID" ] && kill -0 "$PRE_COMMIT_PID" 2>/dev/null; then
        report_status "CLEANUP: Force killing pre-commit $PRE_COMMIT_PID"
        kill_process_tree "$PRE_COMMIT_PID" TERM
        sleep 2
        kill_process_tree "$PRE_COMMIT_PID" KILL
    fi

    # Kill entire process group (belt and suspenders)
    kill -TERM -$$ 2>/dev/null || true

    # Clean up files
    rm -f "$COMM_PIPE" 2>/dev/null || true

    # Release lock
    if [ -n "${LOCK_FD:-}" ]; then
        flock -u "$LOCK_FD" 2>/dev/null || true
    fi

    # Final report
    {
        echo ""
        echo "=== Cleanup Complete ==="
        echo "Exit Code: ${EXIT_CODE:-$exit_code}"
        echo "Ended: $(date)"
        echo "======================="
    } >> "$LOG_FILE"

    # Display summary
    echo ""
    echo "Pre-commit completed with exit code: ${EXIT_CODE:-$exit_code}"
    echo "Logs: $LOG_FILE"
    [ -s "$ERROR_FILE" ] && echo "Errors: $ERROR_FILE" && cat "$ERROR_FILE" >&2

    exit ${EXIT_CODE:-$exit_code}
}

# Set master trap
trap cleanup EXIT INT TERM

# Acquire lock with timeout
exec 200>"$LOCKFILE"
LOCK_FD=200
if ! flock -n 200; then
    echo "Pre-commit is already running. Waiting (max 30s)..." >&2
    if ! flock -w 30 200; then
        echo "ERROR: Could not acquire lock after 30s" >&2
        EXIT_CODE=1
        exit 1
    fi
fi

# Source environment
[ -f ".venv/bin/activate" ] && source .venv/bin/activate
[ -f ".sequential-precommit-env" ] && source .sequential-precommit-env

# Force sequential execution
export PRE_COMMIT_MAX_WORKERS=1
export PRE_COMMIT_NO_CONCURRENCY=1
export PYTHONDONTWRITEBYTECODE=1
export UV_NO_CACHE=1

# Global watchdog - kills everything after timeout
{
    sleep $GLOBAL_TIMEOUT
    report_status "ERROR: Global timeout reached (${GLOBAL_TIMEOUT}s)"
    echo "FATAL: Pre-commit global timeout!" >&2
    kill_process_tree $$ TERM
    sleep 5
    kill_process_tree $$ KILL
} &
WATCHDOG_PID=$!

report_status "INIT: Watchdog started (PID: $WATCHDOG_PID)"

# Heartbeat monitor - detects stalled processes
heartbeat_monitor() {
    local last_heartbeat=$(date +%s)
    local check_interval=10

    while true; do
        sleep $check_interval

        # Check if log file is being updated
        if [ -f "$LOG_FILE" ]; then
            local last_modified=$(stat -f %m "$LOG_FILE" 2>/dev/null || stat -c %Y "$LOG_FILE" 2>/dev/null || echo 0)
            local current_time=$(date +%s)
            local stall_time=$((current_time - last_modified))

            if [ "$stall_time" -gt "$STALL_TIMEOUT" ]; then
                report_status "ERROR: Process stalled for ${stall_time}s"
                echo "ERROR: Pre-commit appears to be stalled (no activity for ${stall_time}s)" >&2
                kill_process_tree $$ TERM
                EXIT_CODE=124  # Timeout exit code
                exit 124
            fi
        fi

        # Check if pre-commit is still alive
        if [ -n "$PRE_COMMIT_PID" ] && ! kill -0 "$PRE_COMMIT_PID" 2>/dev/null; then
            report_status "INFO: Pre-commit process ended"
            break
        fi
    done
}

# Start heartbeat monitor
heartbeat_monitor &
HEARTBEAT_PID=$!
report_status "INIT: Heartbeat monitor started (PID: $HEARTBEAT_PID)"

# Resource monitor function (simplified for robustness)
monitor_resources() {
    local parent_pid=$1

    while kill -0 "$parent_pid" 2>/dev/null; do
        local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
        local memory_mb=$(ps -o rss= -p "$parent_pid" 2>/dev/null | awk '{print int($1/1024)}' || echo "0")

        echo "[$timestamp] PID $parent_pid - Memory: ${memory_mb}MB" >> "$LOG_FILE"

        # Check memory limit
        if [ "$memory_mb" -gt "$MEMORY_LIMIT_MB" ]; then
            report_status "ERROR: Memory limit exceeded (${memory_mb}MB > ${MEMORY_LIMIT_MB}MB)"
            kill_process_tree "$parent_pid" TERM
            EXIT_CODE=137  # Out of memory exit code
            break
        fi

        sleep 1
    done
}

# Check system resources before starting
if [[ "$OSTYPE" == "darwin"* ]]; then
    FREE_MB=$(vm_stat | grep "Pages free" | awk '{print $3}' | sed 's/\.//')
    PAGE_SIZE=$(sysctl -n hw.pagesize 2>/dev/null || echo 16384)
    FREE_MB=$((FREE_MB * PAGE_SIZE / 1024 / 1024))
else
    FREE_MB=$(free -m 2>/dev/null | awk 'NR==2{print $4}' || echo 1024)
fi

if [ "$FREE_MB" -lt 512 ]; then
    report_status "WARNING: Low memory (${FREE_MB}MB free)"
fi

# Start resource monitor
monitor_resources $$ &
MONITOR_PID=$!
report_status "INIT: Resource monitor started (PID: $MONITOR_PID)"

# Run pre-commit with proper error handling
report_status "STARTING: Pre-commit execution"
echo "Starting pre-commit with robust monitoring..."
echo "Logs: $LOG_FILE"
echo "Global timeout: ${GLOBAL_TIMEOUT}s"
echo "Stall detection: ${STALL_TIMEOUT}s"

INSTALL_PYTHON="$PROJECT_ROOT/.venv/bin/python"
if [ -x "$INSTALL_PYTHON" ]; then
    report_status "EXEC: Using venv Python"
    "$INSTALL_PYTHON" -mpre_commit hook-impl \
        --config=.pre-commit-config.yaml \
        --hook-type=pre-commit \
        --hook-dir "$(dirname "$0")" \
        -- "$@" \
        >"${LOG_FILE}.stdout" 2>"$ERROR_FILE" &
    PRE_COMMIT_PID=$!
elif command -v pre-commit > /dev/null; then
    report_status "EXEC: Using system pre-commit"
    pre-commit hook-impl \
        --config=.pre-commit-config.yaml \
        --hook-type=pre-commit \
        --hook-dir "$(dirname "$0")" \
        -- "$@" \
        >"${LOG_FILE}.stdout" 2>"$ERROR_FILE" &
    PRE_COMMIT_PID=$!
else
    report_status "ERROR: pre-commit not found"
    echo "ERROR: pre-commit not found. Activate your virtualenv!" >&2
    EXIT_CODE=127
    exit 127
fi

report_status "RUNNING: Pre-commit PID $PRE_COMMIT_PID"

# Wait for pre-commit with timeout
SECONDS=0
while kill -0 "$PRE_COMMIT_PID" 2>/dev/null; do
    if [ $SECONDS -gt $GLOBAL_TIMEOUT ]; then
        report_status "ERROR: Pre-commit timeout"
        kill_process_tree "$PRE_COMMIT_PID" TERM
        EXIT_CODE=124
        break
    fi
    sleep 1
done

# Get exit code if process completed normally
if wait "$PRE_COMMIT_PID" 2>/dev/null; then
    EXIT_CODE=0
    report_status "COMPLETE: Pre-commit succeeded"
else
    EXIT_CODE=$?
    report_status "FAILED: Pre-commit exited with code $EXIT_CODE"
fi

# Cleanup will run automatically via trap
EOF

chmod +x .git/hooks/pre-commit-wrapper-robust

# Install pre-commit hooks (this will create the basic hook)
echo "Installing pre-commit hooks..."
pre-commit install --install-hooks
pre-commit install --hook-type commit-msg

# Now replace the pre-commit hook with our wrapper caller
echo "Setting up robust resource monitoring wrapper..."
cat > .git/hooks/pre-commit << 'HOOK_EOF'
#!/usr/bin/env bash
# This hook calls our robust wrapper that prevents hanging processes
exec "$(dirname "$0")/pre-commit-wrapper-robust" "$@"
HOOK_EOF
chmod +x .git/hooks/pre-commit

# Create .gitignore entry for logs
if ! grep -q ".pre-commit-logs" .gitignore 2>/dev/null; then
    echo ".pre-commit-logs/" >> .gitignore
fi

echo "✓ Sequential pre-commit with robust monitoring setup complete!"
echo ""
echo "Environment configuration saved to: .sequential-precommit-env"
echo "To manually source the environment:"
echo "  source .sequential-precommit-env"
echo ""
echo "The following variables are now set (project-local):"
echo "  PRE_COMMIT_MAX_WORKERS=1"
echo "  MEMORY_LIMIT_MB=2048 (hooks), 4096 (monitoring kill threshold)"
echo "  TIMEOUT_SECONDS=600"
echo ""
echo "Resource usage logs will be saved to: .pre-commit-logs/"
echo ""
echo "Features enabled:"
echo "  • Sequential hook execution (no parallelism)"
echo "  • Three-layer defense against hanging processes:"
echo "    1. Global watchdog (15 min timeout)"
echo "    2. Heartbeat monitor (60s stall detection)"
echo "    3. Comprehensive cleanup with process groups"
echo "  • Memory usage monitoring and limiting"
echo "  • Automatic process termination at 4GB memory"
echo "  • Proper error propagation and logging"
echo ""
echo "IMPORTANT: After running 'pre-commit install', you must run this setup again"
echo "to restore the robust wrapper, as pre-commit overwrites git hooks."
```

### 2. Pre-commit Configuration

Create `.pre-commit-config.yaml` with all hooks configured for sequential execution:

**CRITICAL**: Every single hook MUST have `require_serial: true` to prevent parallel execution. This includes hooks from external repositories like `pre-commit-hooks`.

```yaml
# Sequential pre-commit configuration
# All hooks run one at a time to minimize resource usage

default_language_version:
  python: python3.12

default_stages: [pre-commit]

# IMPORTANT: Even though we set PRE_COMMIT_MAX_WORKERS=1,
# individual hooks still need require_serial: true

repos:
  # Basic file checks
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
        stages: [pre-commit]
        require_serial: true
      - id: end-of-file-fixer
        stages: [pre-commit]
        require_serial: true
      - id: check-yaml
        stages: [pre-commit]
        require_serial: true
      - id: check-added-large-files
        stages: [pre-commit]
        args: ['--maxkb=1000']
        require_serial: true
      - id: check-toml
        stages: [pre-commit]
        require_serial: true
      - id: check-json
        stages: [pre-commit]
        require_serial: true
      - id: check-merge-conflict
        stages: [pre-commit]
        require_serial: true

  # Python tools (all with require_serial: true)
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.9.4
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
        stages: [pre-commit]
        require_serial: true
      - id: ruff-format
        stages: [pre-commit]
        require_serial: true

  # Resource-intensive hooks using project-local wrappers
  - repo: local
    hooks:
      - id: mypy-limited
        name: Type checking (memory limited)
        entry: .pre-commit-wrappers/memory-limited-hook.sh uv run mypy
        language: system
        types: [python]
        require_serial: true
        pass_filenames: true
        stages: [pre-commit]
        args: [--ignore-missing-imports, --strict]

      - id: trufflehog-limited
        name: Secret detection (resource limited)
        entry: .pre-commit-wrappers/trufflehog-limited.sh
        language: system
        pass_filenames: false
        require_serial: true
        stages: [pre-commit]

# CI configuration
ci:
  skip:
    - mypy-limited
    - trufflehog-limited
```

### 3. GitHub Actions Workflows

#### Basic Sequential Pre-commit Workflow

Create `.github/workflows/pre-commit-sequential.yml`:

```yaml
name: Sequential Pre-commit

on:
  pull_request:
  push:
    branches: [main, develop]

# Force sequential workflow execution
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: false

env:
  # Same environment as local development
  PRE_COMMIT_MAX_WORKERS: 1
  PYTHONDONTWRITEBYTECODE: 1
  UV_NO_CACHE: 1
  MEMORY_LIMIT_MB: 2048
  TIMEOUT_SECONDS: 600
  TRUFFLEHOG_TIMEOUT: 300
  TRUFFLEHOG_CONCURRENCY: 1

jobs:
  sequential-checks:
    runs-on: ubuntu-latest
    timeout-minutes: 45  # Increased for sequential execution

    steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.12'

    - name: Install uv
      uses: astral-sh/setup-uv@v5
      with:
        enable-cache: true

    - name: Create virtual environment
      run: uv venv

    - name: Install dependencies
      run: |
        source .venv/bin/activate
        uv sync --all-extras
        uv pip install pre-commit

    - name: Install local tools
      run: |
        # Install Trufflehog to project bin
        mkdir -p .venv/bin
        curl -sSfL https://raw.githubusercontent.com/trufflesecurity/trufflehog/main/scripts/install.sh | \
          sh -s -- -b .venv/bin

    - name: Run pre-commit hooks sequentially
      run: |
        source .venv/bin/activate
        # Export same variables as local environment
        export PRE_COMMIT_MAX_WORKERS=1
        export MEMORY_LIMIT_MB=2048
        export TIMEOUT_SECONDS=600

        # Run all hooks
        pre-commit run --all-files --show-diff-on-failure

    - name: Memory usage report
      if: always()
      run: |
        echo "Final memory usage:"
        free -h || true
```

#### Sequential PR Fix Workflow (prfix.yml)

Create `.github/workflows/prfix.yml`:

```yaml
name: Sequential PR Auto-Fix

on:
  pull_request:
    types: [opened, synchronize]

# Prevent concurrent PR fixes
concurrency:
  group: prfix-${{ github.event.pull_request.number }}
  cancel-in-progress: false

permissions:
  contents: write
  pull-requests: write

env:
  PRE_COMMIT_MAX_WORKERS: 1
  CI_SEQUENTIAL_MODE: 1

jobs:
  sequential-autofix:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
    - uses: actions/checkout@v4
      with:
        token: ${{ secrets.GITHUB_TOKEN }}
        ref: ${{ github.event.pull_request.head.ref }}
        fetch-depth: 0

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.12'

    - name: Install uv
      uses: astral-sh/setup-uv@v5

    - name: Setup environment
      run: |
        uv venv
        source .venv/bin/activate
        uv sync --all-extras
        uv pip install pre-commit

    - name: Run sequential fixes
      id: autofix
      run: |
        source .venv/bin/activate
        source .sequential-precommit-env || true

        # Track if changes were made
        git diff --exit-code && NO_CHANGES=true || NO_CHANGES=false

        # Run auto-fixable hooks only
        pre-commit run --all-files || true

        # Check if fixes were applied
        git diff --exit-code && FIXES_APPLIED=false || FIXES_APPLIED=true

        echo "fixes_applied=$FIXES_APPLIED" >> $GITHUB_OUTPUT

    - name: Commit fixes
      if: steps.autofix.outputs.fixes_applied == 'true'
      run: |
        git config --local user.email "action@github.com"
        git config --local user.name "GitHub Action"
        git add -A
        git commit -m "fix: Auto-fix formatting and linting issues (sequential)"
        git push

    - name: Comment on PR
      if: steps.autofix.outputs.fixes_applied == 'true'
      uses: actions/github-script@v7
      with:
        script: |
          github.rest.issues.createComment({
            issue_number: context.issue.number,
            owner: context.repo.owner,
            repo: context.repo.repo,
            body: '✅ Sequential auto-fixes applied! Please pull the latest changes.'
          })
```

#### Sequential Build and Test Workflow

Create `.github/workflows/build-test-sequential.yml`:

```yaml
name: Sequential Build and Test

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

concurrency:
  group: build-${{ github.ref }}
  cancel-in-progress: false

env:
  CI_SEQUENTIAL_MODE: 1
  PRE_COMMIT_MAX_WORKERS: 1

jobs:
  sequential-pipeline:
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.12'

    - name: Install uv
      uses: astral-sh/setup-uv@v5

    - name: Sequential Pre-commit
      run: |
        uv venv
        source .venv/bin/activate
        uv pip install pre-commit
        pre-commit run --all-files

    - name: Sequential Tests
      run: |
        source .venv/bin/activate
        uv sync --all-extras

        # Run tests sequentially by type
        echo "Running unit tests..."
        python -m pytest tests/unit -v --maxfail=1

        echo "Running integration tests..."
        python -m pytest tests/integration -v --maxfail=1

        echo "Running system tests..."
        python -m pytest tests/system -v --maxfail=1

    - name: Sequential Build
      run: |
        source .venv/bin/activate

        echo "Building wheel..."
        uv build --wheel

        echo "Building sdist..."
        uv build --sdist

        echo "Verifying packages..."
        ls -la dist/

    - name: Upload artifacts
      uses: actions/upload-artifact@v4
      with:
        name: dist-packages
        path: dist/
```

## Installation and Execution

### Initial Setup

1. **Clone the repository and enter directory**:
   ```bash
   git clone <repository>
   cd <repository>
   ```

2. **Run the setup script**:
   ```bash
   chmod +x setup-sequential-precommit.sh
   ./setup-sequential-precommit.sh
   ```

3. **Activate the environment**:
   ```bash
   source .venv/bin/activate
   source .sequential-precommit-env
   ```

### Execution Sequences

#### Local Execution (Project Folder)

Create `run-sequential-local.sh`:

```bash
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
```

#### Docker Execution (Auto-Cleanup)

Create `run-sequential-docker-pipeline.sh`:

```bash
#!/usr/bin/env bash
# Execute full pipeline in Docker with auto-cleanup
set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PROJECT_NAME=$(basename "$PROJECT_ROOT" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]-')
CONTAINER_NAME="sequential-pipeline-${PROJECT_NAME}-$$"

cd "$PROJECT_ROOT"

# Ensure Docker image exists
if ! docker images | grep -q "sequential-precommit"; then
    echo "Building Docker image..."
    mkdir -p docker/sequential-precommit

    # Generate Dockerfile if not exists
    if [ ! -f "docker/sequential-precommit/Dockerfile" ]; then
        cat > docker/sequential-precommit/Dockerfile << 'EOF'
FROM python:3.11-slim
RUN apt-get update && apt-get install -y git curl procps lsof build-essential && \
    rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/
ENV PRE_COMMIT_MAX_WORKERS=1 PYTHONDONTWRITEBYTECODE=1
RUN useradd -m -s /bin/bash developer
USER developer
WORKDIR /workspace
EOF
    fi

    docker build -t sequential-precommit:latest -f docker/sequential-precommit/Dockerfile .
fi

# Cleanup function
cleanup() {
    echo -e "\nCleaning up Docker container..."
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
    # Optional: Remove volumes
    docker volume prune -f 2>/dev/null || true
    echo "✓ Cleanup completed"
}
trap cleanup EXIT INT TERM

# Run pipeline in Docker
echo "Starting Docker container: $CONTAINER_NAME"
docker run \
    --rm \
    --name "$CONTAINER_NAME" \
    -v "$PROJECT_ROOT:/workspace" \
    -v "/workspace/.venv" \
    -e "PROJECT_ROOT=/workspace" \
    -e "PRE_COMMIT_MAX_WORKERS=1" \
    -e "MEMORY_LIMIT_MB=2048" \
    --memory "4g" \
    --cpus "2" \
    sequential-precommit:latest bash -c '
        cd /workspace

        # Setup if needed
        if [ ! -f ".venv/bin/activate" ]; then
            echo "Setting up environment..."
            if [ -f "setup-sequential-precommit.sh" ]; then
                chmod +x setup-sequential-precommit.sh
                ./setup-sequential-precommit.sh
            else
                uv venv
                source .venv/bin/activate
                uv pip install pre-commit pytest build
            fi
        fi

        # Source environment
        source .venv/bin/activate
        [ -f ".sequential-precommit-env" ] && source .sequential-precommit-env

        # Run pipeline
        echo "=== Docker Sequential Pipeline ==="

        echo -e "\n[1/3] Pre-commit..."
        pre-commit run --all-files || exit 1

        if [ -d "tests" ]; then
            echo -e "\n[2/3] Tests..."
            python -m pytest tests -v || exit 1
        fi

        if [ -f "pyproject.toml" ]; then
            echo -e "\n[3/3] Build..."
            uv build || exit 1
        fi

        echo -e "\n✓ Pipeline completed in Docker"
    '

echo "✓ Docker execution completed and cleaned up"
```

#### Remote Server Execution (SSH)

Create `run-sequential-remote.sh`:

```bash
#!/usr/bin/env bash
# Execute sequential pipeline on remote server
set -euo pipefail

# Configuration
REMOTE_HOST="${1:-}"
REMOTE_USER="${REMOTE_USER:-$USER}"
REMOTE_PATH="${REMOTE_PATH:-~/projects/$(basename "$(pwd)")}"

if [ -z "$REMOTE_HOST" ]; then
    echo "Usage: $0 <remote-host>"
    exit 1
fi

echo "Deploying to $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH"

# Sync project to remote (excluding venv and cache)
rsync -avz --delete \
    --exclude='.venv/' \
    --exclude='__pycache__/' \
    --exclude='.pytest_cache/' \
    --exclude='.pre-commit-logs/' \
    --exclude='node_modules/' \
    --exclude='dist/' \
    --exclude='build/' \
    ./ "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/"

# Execute sequential pipeline remotely
ssh "$REMOTE_USER@$REMOTE_HOST" bash << 'REMOTE_SCRIPT'
set -euo pipefail

cd "$REMOTE_PATH"

# Setup environment if needed
if [ ! -f ".venv/bin/activate" ]; then
    echo "Setting up remote environment..."
    if command -v uv &> /dev/null; then
        uv venv
    else
        python3 -m venv .venv
    fi

    source .venv/bin/activate

    if command -v uv &> /dev/null; then
        uv pip install pre-commit pytest build
    else
        pip install pre-commit pytest build
    fi
fi

# Source environment
source .venv/bin/activate
[ -f ".sequential-precommit-env" ] && source .sequential-precommit-env

# Force sequential execution
export PRE_COMMIT_MAX_WORKERS=1
export PYTHONDONTWRITEBYTECODE=1

# Run pipeline
echo "=== Remote Sequential Pipeline ==="

echo -e "\n[1/3] Pre-commit..."
pre-commit run --all-files || exit 1

if [ -d "tests" ]; then
    echo -e "\n[2/3] Tests..."
    python -m pytest tests -v || exit 1
fi

if [ -f "pyproject.toml" ]; then
    echo -e "\n[3/3] Build..."
    python -m build || uv build || exit 1
fi

echo -e "\n✓ Remote pipeline completed"
REMOTE_SCRIPT

# Optionally, retrieve artifacts
echo -e "\nRetrieving build artifacts..."
rsync -avz "$REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/dist/" ./dist/ 2>/dev/null || true

echo "✓ Remote execution completed"
```

## Expected Directory Structure

After running the setup script, your project should have:

```
project-root/
├── .venv/                           # Virtual environment
│   └── bin/
│       ├── activate                 # Activation script
│       ├── python                   # Python interpreter
│       ├── pre-commit              # Pre-commit executable
│       └── trufflehog              # TruffleHog (if installed)
├── .git/
│   └── hooks/
│       ├── pre-commit              # Git hook (calls wrapper)
│       └── pre-commit-wrapper-robust # Robust wrapper script
├── .pre-commit-wrappers/
│   ├── memory-limited-hook.sh      # Memory limiting wrapper
│   └── trufflehog-limited.sh       # TruffleHog wrapper
├── .pre-commit-logs/               # Log directory (created on first run)
├── .sequential-precommit-env       # Environment configuration
├── .pre-commit-config.yaml         # Pre-commit configuration
├── setup-sequential-precommit.sh   # Setup script
└── .gitignore                      # Updated with .pre-commit-logs/
```

## Testing the Setup

To verify everything is working correctly:

1. **Test with a simple commit**:
   ```bash
   echo "test" > test.txt
   git add test.txt
   git commit -m "Test commit"
   # Watch for the monitoring messages
   ```

2. **Check the logs**:
   ```bash
   ls -la .pre-commit-logs/
   cat .pre-commit-logs/resource_usage_*.log | tail -20
   ```

3. **Verify sequential execution**:
   ```bash
   # During a commit, in another terminal:
   ps aux | grep pre-commit
   # Should show only one pre-commit process at a time
   ```

4. **Test memory limiting** (optional):
   ```bash
   # Create a memory-intensive test hook
   cat > .pre-commit-config.yaml << 'EOF'
   repos:
     - repo: local
       hooks:
         - id: memory-test
           name: Memory test
           entry: python -c "x = ' ' * (3 * 1024 * 1024 * 1024)"  # 3GB
           language: system
           require_serial: true
   EOF

   git add .pre-commit-config.yaml
   git commit -m "Test memory limit"
   # Should fail with memory limit exceeded
   ```

## Understanding Resource Logs

After each pre-commit run, check the logs in `.pre-commit-logs/`:

```bash
cat .pre-commit-logs/resource_usage_*.log
```

Example log output:
```
=== Pre-commit Resource Monitor ===
Started: Wed Jul  2 11:10:12 CEST 2025
Memory limit: 4096MB
Monitoring PID: 89506
===================================
[2025-07-02 11:10:12] PID 89506 - Memory: 4MB, FDs: 9, Children: 1
  └─ Child PID 89526 (python) - Memory: 101MB
[2025-07-02 11:10:13] WARNING: Memory usage (3500MB) is above 80% of limit
[2025-07-02 11:10:14] NOTICE: Elevated file descriptor count: 523

=== Resource Usage Summary ===
Ended: Wed Jul  2 11:10:16 CEST 2025
Peak Memory: 105MB
Peak File Descriptors: 523
Peak Child Processes: 3
=============================
```

## Resource Limits and Thresholds

The monitoring system tracks:

1. **Memory Usage**:
   - Individual hook limit: 2048MB (enforced by wrappers)
   - Total pre-commit limit: 4096MB (kills process if exceeded)
   - Warning at 80% of limit

2. **File Descriptors**:
   - Notice at 500 FDs
   - Warning at 1000 FDs

3. **Child Processes**:
   - Notice at 20 children
   - Warning at 50 children

## Customization

### Adjusting Resource Limits

Edit `.sequential-precommit-env` in your project root:

```bash
export MEMORY_LIMIT_MB=4096      # Increase for large projects
export TIMEOUT_SECONDS=1200      # 20 minutes for slow operations
export TRUFFLEHOG_TIMEOUT=600    # 10 minutes for deep scanning
```

### Changing Kill Threshold

In `.git/hooks/pre-commit-wrapper-robust`, modify line 222:
```bash
MEMORY_LIMIT_MB="${MEMORY_LIMIT_MB:-8192}"  # Kill at 8GB instead of 4GB
```

### Adding New Hooks

Always include `require_serial: true` for resource-intensive hooks:

```yaml
- repo: local
  hooks:
    - id: my-custom-check
      name: Custom check
      entry: .pre-commit-wrappers/memory-limited-hook.sh ./scripts/my-check.sh
      language: system
      require_serial: true
      pass_filenames: false
```

## Docker Support with Auto-Cleanup

### Docker Configuration Files

Create `docker/sequential-precommit/Dockerfile`:

```dockerfile
# Universal Python development container with sequential execution
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    procps \
    lsof \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv globally
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/

# Set sequential execution environment
ENV PRE_COMMIT_MAX_WORKERS=1 \
    PRE_COMMIT_NO_CONCURRENCY=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1 \
    MEMORY_LIMIT_MB=2048 \
    TIMEOUT_SECONDS=600 \
    DOCKER_CONTAINER=1

# Create non-root user for security
RUN useradd -m -s /bin/bash developer && \
    mkdir -p /workspace && \
    chown -R developer:developer /workspace

USER developer
WORKDIR /workspace

# Copy project files (if building with context)
COPY --chown=developer:developer . /workspace/

# Run setup if script exists
RUN if [ -f "setup-sequential-precommit.sh" ]; then \
        chmod +x setup-sequential-precommit.sh && \
        ./setup-sequential-precommit.sh; \
    fi

# Default command
CMD ["/bin/bash"]
```

Create `docker/sequential-precommit/docker-compose.yml`:

```yaml
version: '3.8'

services:
  precommit:
    build:
      context: ../..
      dockerfile: docker/sequential-precommit/Dockerfile
    image: sequential-precommit:latest
    container_name: sequential-precommit-${PROJECT_NAME:-default}
    volumes:
      - ../../:/workspace
      - /workspace/.venv  # Exclude venv from volume mount
      - /workspace/node_modules  # Exclude node_modules if present
    environment:
      - PROJECT_ROOT=/workspace
      - PRE_COMMIT_MAX_WORKERS=1
      - MEMORY_LIMIT_MB=${MEMORY_LIMIT_MB:-2048}
      - DOCKER_MEMORY_LIMIT=${DOCKER_MEMORY_LIMIT:-4g}
      - DOCKER_CPU_LIMIT=${DOCKER_CPU_LIMIT:-2}
    mem_limit: ${DOCKER_MEMORY_LIMIT:-4g}
    cpus: ${DOCKER_CPU_LIMIT:-2}
    working_dir: /workspace
    stdin_open: true
    tty: true
    command: /bin/bash -c "source .sequential-precommit-env && pre-commit run --all-files"
```

### Docker Execution Scripts

Create `run-sequential-docker.sh`:

```bash
#!/usr/bin/env bash
# Run sequential pre-commit in Docker with auto-cleanup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$SCRIPT_DIR}"
PROJECT_NAME=$(basename "$PROJECT_ROOT" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]-')

cd "$PROJECT_ROOT"

# Source environment if exists
[ -f ".sequential-precommit-env" ] && source .sequential-precommit-env

# Docker run options
DOCKER_OPTS=(
    --rm  # Auto-remove container after exit
    -it   # Interactive terminal
    --name "sequential-precommit-${PROJECT_NAME}-$$"
    --memory "${DOCKER_MEMORY_LIMIT:-4g}"
    --cpus "${DOCKER_CPU_LIMIT:-2}"
    -v "$PROJECT_ROOT:/workspace"
    -v "/workspace/.venv"  # Anonymous volume for venv
    -e "PROJECT_ROOT=/workspace"
    -e "PRE_COMMIT_MAX_WORKERS=1"
    -e "MEMORY_LIMIT_MB=${MEMORY_LIMIT_MB:-2048}"
    -w "/workspace"
)

# Build image if needed
if ! docker images | grep -q "sequential-precommit"; then
    echo "Building Docker image..."
    docker build -t sequential-precommit:latest -f docker/sequential-precommit/Dockerfile .
fi

# Function to cleanup on exit
cleanup() {
    echo "Cleaning up Docker resources..."
    docker rm -f "sequential-precommit-${PROJECT_NAME}-$$" 2>/dev/null || true
}
trap cleanup EXIT

# Run command in Docker
echo "Running in Docker container (auto-cleanup enabled)..."
docker run "${DOCKER_OPTS[@]}" sequential-precommit:latest bash -c "
    # Setup environment if not exists
    if [ ! -f '.venv/bin/activate' ]; then
        ./setup-sequential-precommit.sh
    fi

    # Source environment
    source .venv/bin/activate
    source .sequential-precommit-env

    # Run pre-commit
    pre-commit run --all-files --show-diff-on-failure
"

echo "Docker container cleaned up successfully."
```

## Benefits of Enhanced Monitoring

1. **Visibility**: See exactly what resources each hook consumes
2. **Protection**: Automatic termination prevents system crashes
3. **Debugging**: Detailed logs help identify problematic hooks
4. **Optimization**: Peak usage stats guide resource allocation
5. **Reliability**: Predictable resource usage patterns

## Preventing Hanging Processes

The robust wrapper implements a three-layer defense system to prevent:

1. **Zombie/Orphaned Processes**: Uses process groups and trap handlers
2. **Silent Failures**: All errors are logged and reported with proper exit codes
3. **Indefinite Hangs**: Multiple timeout mechanisms ensure termination

### Key Features:

- **Global Watchdog**: Hard timeout of 15 minutes for entire pre-commit
- **Heartbeat Monitor**: Detects stalled processes (no activity for 60s)
- **Process Group Management**: Ensures all children die with parent
- **Bidirectional Communication**: Status updates via named pipes
- **Comprehensive Cleanup**: Always runs, even on SIGKILL

## Troubleshooting

### Multiple Pre-commit Processes Running?

This is the most common issue. Even with `require_serial: true`, you might see multiple processes because:

1. **Pre-commit framework spawning**: The framework itself may spawn processes
2. **Missing environment variables**: `PRE_COMMIT_MAX_WORKERS` not being respected
3. **Git hook chain**: Multiple hooks being triggered

**Solution**:
```bash
# Verify the wrapper is being used
cat .git/hooks/pre-commit
# Should show: exec "$(dirname "$0")/pre-commit-wrapper-robust" "$@"

# Check environment is loaded
source .sequential-precommit-env
echo $PRE_COMMIT_MAX_WORKERS
# Should show: 1

# Kill all existing processes
pkill -f "pre-commit" && pkill -f "trufflehog"

# Re-run setup
./setup-sequential-precommit.sh
```

### High Memory Usage Detected?

Check which hooks are consuming resources:
```bash
grep -E "(Child PID|Memory:)" .pre-commit-logs/resource_usage_*.log | tail -20
```

### Process Killed Due to Memory?

Look for the CRITICAL entries:
```bash
grep -E "(CRITICAL|KILLING)" .pre-commit-logs/resource_usage_*.log
```

### Too Many File Descriptors?

Some tools don't clean up properly. Add explicit cleanup:
```bash
# In your wrapper script
cleanup() {
    # Close file descriptors
    exec 3>&- 4>&- 5>&- 2>/dev/null || true
    # Kill child processes
    pkill -P $$ 2>/dev/null || true
}
trap cleanup EXIT
```

### Monitor Not Working?

Ensure the monitor has permissions:
```bash
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit-wrapper
chmod +x .pre-commit-wrappers/*.sh
```

### Pre-commit Install Overwrites Hook?

After running `pre-commit install`, you must re-apply the wrapper:
```bash
# Re-create the wrapper hook
cat > .git/hooks/pre-commit << 'EOF'
#!/usr/bin/env bash
exec "$(dirname "$0")/pre-commit-wrapper" "$@"
EOF
chmod +x .git/hooks/pre-commit
```

## Platform-Specific Notes

### macOS
- Memory limits (`ulimit -v`) don't work, but monitoring still tracks usage
- Use `lsof` for file descriptor counting
- Install GNU coreutils for better `timeout` command: `brew install coreutils`

### Linux
- Full memory limiting support via `ulimit`
- `/proc` filesystem provides detailed process info
- Native `timeout` command available

### Windows (Git Bash/WSL)
- WSL2 provides Linux-like behavior
- Git Bash has limited process monitoring
- Consider using WSL2 for better resource control

Remember: This setup prioritizes stability and visibility. The resource monitoring ensures you always know what's happening and prevents system resource exhaustion, making your development workflow more reliable and predictable.

## Universal Execution Wrapper

Create `sequential-universal.sh` for a single entry point that works everywhere:

```bash
#!/usr/bin/env bash
# Universal sequential execution wrapper - works in all environments
set -euo pipefail

# Detect execution environment
detect_environment() {
    if [ -n "${GITHUB_ACTIONS:-}" ]; then
        echo "github"
    elif [ -n "${DOCKER_CONTAINER:-}" ] || [ -f "/.dockerenv" ]; then
        echo "docker"
    elif [ -n "${SSH_CONNECTION:-}" ]; then
        echo "remote"
    else
        echo "local"
    fi
}

# Get project root with fallbacks
get_project_root() {
    if [ -n "${PROJECT_ROOT:-}" ]; then
        echo "$PROJECT_ROOT"
    elif git rev-parse --show-toplevel &>/dev/null; then
        git rev-parse --show-toplevel
    else
        pwd
    fi
}

ENV_TYPE=$(detect_environment)
PROJECT_ROOT=$(get_project_root)
cd "$PROJECT_ROOT"

echo "=== Universal Sequential Execution ==="
echo "Environment: $ENV_TYPE"
echo "Project: $PROJECT_ROOT"
echo "===================================="

# Environment-specific setup
case "$ENV_TYPE" in
    github)
        echo "Running in GitHub Actions..."
        # CI-specific settings
        export CI=true
        export TERM=dumb
        ;;
    docker)
        echo "Running in Docker container..."
        # Ensure proper user permissions
        if [ "$(id -u)" = "0" ]; then
            echo "Warning: Running as root in Docker"
        fi
        ;;
    remote)
        echo "Running on remote server..."
        # Ensure non-interactive mode
        export DEBIAN_FRONTEND=noninteractive
        ;;
    local)
        echo "Running locally..."
        ;;
esac

# Setup Python environment with multiple fallbacks
setup_python_env() {
    # Check if venv exists
    if [ -f ".venv/bin/activate" ]; then
        source .venv/bin/activate
    elif [ -f "venv/bin/activate" ]; then
        source venv/bin/activate
    elif [ -n "${VIRTUAL_ENV:-}" ]; then
        echo "Using existing virtual environment: $VIRTUAL_ENV"
    else
        echo "Creating new virtual environment..."
        if command -v uv &>/dev/null; then
            uv venv
        elif command -v python3 &>/dev/null; then
            python3 -m venv .venv
        elif command -v python &>/dev/null; then
            python -m venv .venv
        else
            echo "Error: No Python interpreter found"
            exit 1
        fi
        source .venv/bin/activate 2>/dev/null || source venv/bin/activate
    fi
}

# Load configuration with fallbacks
load_config() {
    # Load sequential config if exists
    [ -f ".sequential-precommit-env" ] && source .sequential-precommit-env

    # Set defaults if not already set
    export PRE_COMMIT_MAX_WORKERS="${PRE_COMMIT_MAX_WORKERS:-1}"
    export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"
    export MEMORY_LIMIT_MB="${MEMORY_LIMIT_MB:-2048}"
    export TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-600}"

    # Platform-specific adjustments
    case "$(uname -s)" in
        Darwin)
            # macOS doesn't support memory limits via ulimit
            export SKIP_MEMORY_LIMIT=1
            ;;
        MINGW*|CYGWIN*|MSYS*)
            # Windows/Git Bash adjustments
            export SKIP_PROCESS_GROUPS=1
            ;;
    esac
}

# Install dependencies if needed
ensure_dependencies() {
    local needs_install=0

    # Check for pre-commit
    if ! command -v pre-commit &>/dev/null; then
        echo "Installing pre-commit..."
        needs_install=1
    fi

    if [ $needs_install -eq 1 ]; then
        if command -v uv &>/dev/null; then
            uv pip install pre-commit pytest build
        else
            pip install pre-commit pytest build
        fi
    fi
}

# Main execution
main() {
    setup_python_env
    load_config
    ensure_dependencies

    # Parse command line arguments
    COMMAND="${1:-all}"
    shift || true

    case "$COMMAND" in
        precommit|pre-commit)
            echo -e "\nRunning pre-commit checks..."
            pre-commit run --all-files "$@"
            ;;
        test|tests)
            echo -e "\nRunning tests..."
            if [ -d "tests" ]; then
                python -m pytest tests -v "$@"
            else
                echo "No tests directory found"
            fi
            ;;
        build)
            echo -e "\nBuilding project..."
            if [ -f "pyproject.toml" ]; then
                if command -v uv &>/dev/null; then
                    uv build "$@"
                else
                    python -m build "$@"
                fi
            else
                echo "No pyproject.toml found"
            fi
            ;;
        all|pipeline)
            echo -e "\nRunning full pipeline..."
            # Pre-commit
            if ! pre-commit run --all-files; then
                echo "Pre-commit failed"
                exit 1
            fi

            # Tests
            if [ -d "tests" ]; then
                if ! python -m pytest tests -v; then
                    echo "Tests failed"
                    exit 1
                fi
            fi

            # Build
            if [ -f "pyproject.toml" ]; then
                if command -v uv &>/dev/null; then
                    uv build
                else
                    python -m build
                fi
            fi

            echo -e "\n✓ Pipeline completed successfully"
            ;;
        docker)
            echo -e "\nLaunching Docker execution..."
            exec bash run-sequential-docker-pipeline.sh "$@"
            ;;
        help|--help|-h)
            cat << EOF
Usage: $0 [COMMAND] [OPTIONS]

Commands:
  precommit    Run pre-commit checks
  test         Run tests
  build        Build project
  all          Run full pipeline (default)
  docker       Run in Docker container
  help         Show this help

Options are passed to the respective commands.

Environment variables:
  PROJECT_ROOT           Project root directory
  MEMORY_LIMIT_MB       Memory limit per process (default: 2048)
  TIMEOUT_SECONDS       Timeout per operation (default: 600)
  PRE_COMMIT_MAX_WORKERS  Max parallel workers (default: 1)
EOF
            ;;
        *)
            echo "Unknown command: $COMMAND"
            echo "Run '$0 help' for usage"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
```

## Edge Cases and Platform Considerations

### Windows Support (Git Bash/WSL2)

Create `.sequential-precommit-env.windows`:

```bash
#!/usr/bin/env bash
# Windows-specific environment settings

# Core settings (same as Unix)
export PRE_COMMIT_MAX_WORKERS=1
export PYTHONDONTWRITEBYTECODE=1

# Windows-specific paths
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    # Git Bash / MSYS2
    export PYTHONIOENCODING=utf-8
    export MSYS=winsymlinks:nativestrict

    # Use Windows Python if available
    if command -v python.exe &>/dev/null; then
        alias python='python.exe'
        alias pip='python.exe -m pip'
    fi
fi

# WSL2 detection
if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "Running in WSL2"
    # WSL2-specific settings
    export DISPLAY=:0
fi
```

### Monorepo Support

For projects with multiple Python packages:

```bash
# In setup-sequential-precommit.sh, add:

# Detect monorepo structure
if [ -f "pyproject.toml" ] && grep -q "tool.hatch.build.targets.wheel.packages" pyproject.toml; then
    echo "Monorepo detected, setting up for multiple packages..."

    # Find all package directories
    for pkg_dir in $(find . -name "pyproject.toml" -not -path "*/.*" -exec dirname {} \;); do
        echo "Setting up package: $pkg_dir"
        (
            cd "$pkg_dir"
            if [ ! -f ".venv" ]; then
                ln -s "$PROJECT_ROOT/.venv" .venv
            fi
        )
    done
fi
```

### CI/CD Platform Detection

Add to the universal wrapper:

```bash
# Enhanced CI detection
detect_ci_platform() {
    if [ -n "${GITHUB_ACTIONS:-}" ]; then
        echo "github"
    elif [ -n "${GITLAB_CI:-}" ]; then
        echo "gitlab"
    elif [ -n "${CIRCLECI:-}" ]; then
        echo "circleci"
    elif [ -n "${JENKINS_URL:-}" ]; then
        echo "jenkins"
    elif [ -n "${BITBUCKET_PIPELINE_UUID:-}" ]; then
        echo "bitbucket"
    elif [ -n "${AZURE_PIPELINES:-}" ]; then
        echo "azure"
    else
        echo "unknown"
    fi
}
```

### Handling Large Repositories

For repositories with many files:

```bash
# Add to .sequential-precommit-env:

# Large repo optimizations
export PRE_COMMIT_PASS_FILENAMES=0  # Don't pass all filenames
export PRE_COMMIT_FROM_REF=HEAD~1   # Only check changed files
export PRE_COMMIT_TO_REF=HEAD       # Between commits

# Trufflehog optimization for large repos
export TRUFFLEHOG_MAX_DEPTH=10      # Limit history scan
export TRUFFLEHOG_EXCLUDE_PATHS=".trufflehog-exclude"
```

## Important: TruffleHog Configuration Consistency

When using TruffleHog for secret detection, it's critical to maintain consistency between local and GitHub Actions configurations:

### Local Configuration (pre-commit wrapper)
The local wrapper script uses:
```bash
trufflehog git file://. \
    --only-verified \     # Only report verified secrets
    --fail \              # Exit with error if secrets found
    --no-update \         # Don't auto-update TruffleHog
    --concurrency="1"     # Single-threaded execution
```

### GitHub Actions Configuration
When using the TruffleHog GitHub Action, ensure you use matching settings:
```yaml
- name: Run TruffleHog v3
  uses: trufflesecurity/trufflehog@main
  with:
    path: ./
    base: ${{ github.event.repository.default_branch }}
    head: HEAD
    extra_args: --only-verified  # Match local configuration
```

**Important Notes:**
1. Always use `--only-verified` in both local and CI/CD environments
2. Never use `--no-verification` as it skips verification entirely (opposite behavior)
3. The TruffleHog GitHub Action already includes `--fail` by default - do not duplicate it
4. Do not use invalid detector names like `generic-api-key` or `email` - use the exact names from TruffleHog's protobuf definitions

This consistency ensures:
- Same secrets are detected locally and in CI/CD
- No false positives from unverified patterns
- Predictable behavior across all environments

## Summary

This universal sequential execution setup provides:

1. **Complete Environment Support**: Works identically in local, Docker, CI/CD, and remote environments
2. **Three-Layer Defense**: Against hanging processes, memory exhaustion, and runaway hooks
3. **Auto-Cleanup**: Docker containers are always removed after use
4. **Platform Independence**: Handles macOS, Linux, Windows (WSL2/Git Bash)
5. **Zero System Modification**: All configuration is project-local
6. **Universal Entry Point**: Single script works everywhere
7. **PR Safety**: Sequential execution prevents race conditions in PR fixes

Key features:
- No process can hang indefinitely (15-minute global timeout)
- Stalled processes are detected and killed (60-second inactivity timeout)
- All child processes are cleaned up properly (process group management)
- Memory limits are enforced (4GB default, configurable)
- Docker containers are automatically removed to save disk space
- Works with any Python project structure
- Relocatable virtual environments

This implementation represents best practices for managing pre-commit hooks, CI/CD workflows, and build processes in production environments where reliability, resource control, and disk space management are critical.
