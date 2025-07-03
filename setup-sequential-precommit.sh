#!/usr/bin/env bash
# Universal setup script for sequential execution with resource monitoring
# Works in all environments: local, Docker, CI/CD
# All configuration is project-local - no system files are modified
# Version: 1.0.0

set -euo pipefail

# Script version
readonly SCRIPT_VERSION="1.0.0"

# Constants
readonly DEFAULT_MEMORY_LIMIT_MB=2048
readonly DEFAULT_TIMEOUT_SECONDS=600
readonly DEFAULT_GLOBAL_TIMEOUT=900
readonly DEFAULT_STALL_TIMEOUT=60
readonly DEFAULT_MONITOR_KILL_THRESHOLD_MB=4096
readonly MIN_FREE_MEMORY_MB=512
readonly MIN_FREE_DISK_MB=100
readonly LOCK_WAIT_SECONDS=30
readonly PYTHON_VERSION="3.11"

# Help function
show_help() {
    cat << EOF
Universal Sequential Pre-commit Setup Script v${SCRIPT_VERSION}

Usage: $0 [OPTIONS]

Options:
    -h, --help          Show this help message
    -v, --version       Show version information
    -f, --force         Force reinstall even if already configured
    -q, --quiet         Suppress non-error output
    --no-color          Disable colored output

Environment Variables:
    PROJECT_ROOT        Project root directory (default: current directory)
    MEMORY_LIMIT_MB     Memory limit for hooks (default: ${DEFAULT_MEMORY_LIMIT_MB})
    TIMEOUT_SECONDS     Timeout for individual hooks (default: ${DEFAULT_TIMEOUT_SECONDS})

This script sets up a robust sequential pre-commit execution environment
with three-layer defense against hanging processes.
EOF
    exit 0
}

# Parse command line arguments
FORCE_INSTALL=false
QUIET_MODE=false
NO_COLOR=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        -v|--version)
            echo "Sequential Pre-commit Setup v${SCRIPT_VERSION}"
            exit 0
            ;;
        -f|--force)
            FORCE_INSTALL=true
            shift
            ;;
        -q|--quiet)
            QUIET_MODE=true
            shift
            ;;
        --no-color)
            NO_COLOR=true
            shift
            ;;
        *)
            echo "Error: Unknown option $1" >&2
            echo "Use $0 --help for usage information" >&2
            exit 1
            ;;
    esac
done

# Color output functions
if [[ "$NO_COLOR" == "false" ]] && [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    NC='\033[0m' # No Color
else
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    NC=''
fi

# Output functions
info() {
    [[ "$QUIET_MODE" == "false" ]] && echo -e "${BLUE}[INFO]${NC} $*"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $*" >&2
}

error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
}

success() {
    [[ "$QUIET_MODE" == "false" ]] && echo -e "${GREEN}[OK]${NC} $*"
}

# Progress indicator
show_progress() {
    local message="$1"
    [[ "$QUIET_MODE" == "false" ]] && echo -ne "${BLUE}[*]${NC} ${message}..."
}

progress_done() {
    [[ "$QUIET_MODE" == "false" ]] && echo -e " ${GREEN}done${NC}"
}

# Interrupt handler
interrupt_handler() {
    echo
    error "Setup interrupted by user"
    exit 130
}
trap interrupt_handler INT TERM

# Detect environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$SCRIPT_DIR}"

# Validate PROJECT_ROOT
if [[ ! -d "$PROJECT_ROOT" ]]; then
    error "Project root directory does not exist: $PROJECT_ROOT"
    exit 1
fi

# Check if it's a git repository
if [[ ! -d "$PROJECT_ROOT/.git" ]]; then
    warn "Not a git repository. Some features may not work correctly."
fi

cd "$PROJECT_ROOT" || exit 1

# Platform detection with better Windows support
detect_platform() {
    case "$OSTYPE" in
        linux-gnu*) echo "linux" ;;
        darwin*) echo "macos" ;;
        msys*|cygwin*|mingw*) echo "windows" ;;
        *)
            # Fallback detection
            if [[ -f /proc/version ]] && grep -qi microsoft /proc/version; then
                echo "wsl"
            else
                echo "unknown"
            fi
            ;;
    esac
}

# Check system requirements
check_system_requirements() {
    show_progress "Checking system requirements"

    # Check disk space
    local free_disk_mb
    if [[ "$PLATFORM" == "macos" ]]; then
        free_disk_mb=$(df -m "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    else
        free_disk_mb=$(df -m "$PROJECT_ROOT" | awk 'NR==2 {print $4}')
    fi

    if [[ -n "$free_disk_mb" ]] && [[ "$free_disk_mb" -lt "$MIN_FREE_DISK_MB" ]]; then
        error "Insufficient disk space: ${free_disk_mb}MB free (need at least ${MIN_FREE_DISK_MB}MB)"
        exit 1
    fi

    # Check required commands
    local missing_commands=()
    for cmd in git curl awk sed; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_commands+=("$cmd")
        fi
    done

    if [[ ${#missing_commands[@]} -gt 0 ]]; then
        error "Missing required commands: ${missing_commands[*]}"
        error "Please install them before running this script"
        exit 1
    fi

    progress_done
}

PLATFORM=$(detect_platform)
info "Setting up sequential execution protocol"
info "Platform: $PLATFORM"
info "Project root: $PROJECT_ROOT"
info "Script version: $SCRIPT_VERSION"

# Run system checks
check_system_requirements

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
show_progress "Installing pre-commit"
if ! uv pip install pre-commit pre-commit-uv; then
    error "Failed to install pre-commit"
    exit 1
fi
progress_done

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
# Cross-platform hash function
get_project_hash() {
    if command -v md5sum &> /dev/null; then
        echo "$1" | md5sum | cut -d' ' -f1
    elif command -v md5 &> /dev/null; then
        echo "$1" | md5 -q
    else
        # Fallback: use cksum
        echo "$1" | cksum | cut -d' ' -f1
    fi
}

PROJECT_HASH=$(get_project_hash "$PROJECT_ROOT")
LOCKFILE="/tmp/pre-commit-${PROJECT_HASH}.lock"
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

# Platform detection
PLATFORM="unknown"
case "$OSTYPE" in
    linux-gnu*) PLATFORM="linux" ;;
    darwin*) PLATFORM="macos" ;;
    msys*|cygwin*|mingw*) PLATFORM="windows" ;;
esac

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
    local max_iterations=$((GLOBAL_TIMEOUT / check_interval + 1))
    local iteration=0

    while [ $iteration -lt $max_iterations ]; do
        sleep $check_interval
        iteration=$((iteration + 1))

        # Check if parent process is still alive
        if ! kill -0 $$ 2>/dev/null; then
            # Parent is gone, exit
            exit 0
        fi

        # Check if log file is being updated
        if [ -f "$LOG_FILE" ]; then
            # Cross-platform file modification time
            local last_modified
            if [[ "$PLATFORM" == "macos" ]] || [[ "$PLATFORM" == "darwin" ]]; then
                last_modified=$(stat -f %m "$LOG_FILE" 2>/dev/null || echo 0)
            else
                last_modified=$(stat -c %Y "$LOG_FILE" 2>/dev/null || echo 0)
            fi
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

    # Safety exit after max iterations
    report_status "INFO: Heartbeat monitor exiting after ${iteration} iterations"
}

# Start heartbeat monitor
heartbeat_monitor &
HEARTBEAT_PID=$!
report_status "INIT: Heartbeat monitor started (PID: $HEARTBEAT_PID)"

# Resource monitor function (simplified for robustness)
monitor_resources() {
    local parent_pid=$1
    local max_iterations=$GLOBAL_TIMEOUT
    local iteration=0

    while [ $iteration -lt $max_iterations ] && kill -0 "$parent_pid" 2>/dev/null; do
        iteration=$((iteration + 1))
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

        # Log rotation to prevent disk fill
        if [ $((iteration % 300)) -eq 0 ]; then
            # Every 5 minutes, check log size
            local log_size=$(wc -c < "$LOG_FILE" 2>/dev/null || echo 0)
            if [ "$log_size" -gt $((10 * 1024 * 1024)) ]; then
                # If log is over 10MB, rotate it
                mv "$LOG_FILE" "${LOG_FILE}.old"
                echo "[$timestamp] Log rotated at ${log_size} bytes" > "$LOG_FILE"
            fi
        fi

        sleep 1
    done

    report_status "INFO: Resource monitor exiting after ${iteration} iterations"
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

# Create version file
cat > .sequential-precommit-version << EOF
${SCRIPT_VERSION}
EOF

success "Sequential pre-commit with robust monitoring setup complete!"
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
