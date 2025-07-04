#!/usr/bin/env bash
# sequential-executor.sh - TRUE sequential execution with orphan management
# 
# GUARANTEES:
# 1. Only ONE process runs at a time - NO exceptions
# 2. Waits INDEFINITELY for previous process to complete
# 3. Detects and kills orphaned processes
# 4. Maintains process genealogy for cleanup

set -euo pipefail

# Global configuration
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PROJECT_NAME="$(basename "$PROJECT_ROOT")"
PROJECT_HASH=$(echo "$PROJECT_ROOT" | shasum | cut -d' ' -f1 | head -c 8)

# Lock and state files
LOCK_DIR="/tmp/mfr-sequential-${PROJECT_HASH}"
LOCKFILE="${LOCK_DIR}/executor.lock"
QUEUE_FILE="${LOCK_DIR}/queue.txt"
CURRENT_PID_FILE="${LOCK_DIR}/current.pid"
PROCESS_TREE_FILE="${LOCK_DIR}/process_tree.txt"
ORPHAN_LOG="${LOCK_DIR}/orphans.log"

# Ensure lock directory exists
mkdir -p "$LOCK_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log_info() {
    echo -e "${GREEN}[SEQUENTIAL]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2
}

log_queue() {
    echo -e "${BLUE}[QUEUE]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*"
}

# Get all child processes recursively
get_process_tree() {
    local pid=$1
    local children=""
    
    # Get direct children
    if command -v pgrep >/dev/null 2>&1; then
        children=$(pgrep -P "$pid" 2>/dev/null || true)
    else
        children=$(ps --ppid "$pid" -o pid= 2>/dev/null || true)
    fi
    
    # Output current PID
    echo "$pid"
    
    # Recursively get children
    for child in $children; do
        get_process_tree "$child"
    done
}

# Kill entire process tree
kill_process_tree() {
    local pid=$1
    local signal=${2:-TERM}
    
    log_info "Killing process tree for PID $pid with signal $signal"
    
    # Get all PIDs in tree
    local all_pids=$(get_process_tree "$pid" | sort -u)
    
    # Kill in reverse order (children first)
    for p in $(echo "$all_pids" | tac); do
        if kill -0 "$p" 2>/dev/null; then
            log_info "  Killing PID $p"
            kill -"$signal" "$p" 2>/dev/null || true
        fi
    done
}

# Detect and kill orphaned processes
kill_orphans() {
    log_info "Checking for orphaned processes..."
    
    # Known patterns for our processes
    local patterns=(
        "pytest"
        "python.*test"
        "uv run"
        "pre-commit"
        "ruff"
        "mypy"
        "git.*commit"
        "mass_find_replace"
    )
    
    local found_orphans=0
    
    for pattern in "${patterns[@]}"; do
        # Find processes matching pattern
        local pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        
        for pid in $pids; do
            # Skip if it's us or our parent
            [ "$pid" -eq "$$" ] && continue
            [ "$pid" -eq "$PPID" ] && continue
            
            # Check if this process belongs to our project
            local cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || lsof -p "$pid" 2>/dev/null | grep cwd | awk '{print $NF}' || true)
            
            if [[ "$cwd" == *"$PROJECT_NAME"* ]] || [[ "$cwd" == "$PROJECT_ROOT"* ]]; then
                # Check if it has a living parent that we're tracking
                local ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | xargs || echo 1)
                
                if [ "$ppid" -eq 1 ] || ! kill -0 "$ppid" 2>/dev/null; then
                    # It's an orphan!
                    log_warn "Found orphan process: PID=$pid CMD=$(ps -p "$pid" -o comm= 2>/dev/null || echo unknown)"
                    echo "$(date) PID=$pid PATTERN=$pattern" >> "$ORPHAN_LOG"
                    
                    # Kill the orphan and its children
                    kill_process_tree "$pid" TERM
                    sleep 1
                    kill_process_tree "$pid" KILL
                    
                    found_orphans=$((found_orphans + 1))
                fi
            fi
        done
    done
    
    if [ "$found_orphans" -gt 0 ]; then
        log_warn "Killed $found_orphans orphaned process(es)"
    else
        log_info "No orphaned processes found"
    fi
}

# Check if a PID is still alive and belongs to us
is_our_process_alive() {
    local pid=$1
    
    # Check if process exists
    if ! kill -0 "$pid" 2>/dev/null; then
        return 1
    fi
    
    # Verify it's still our command (not PID reuse)
    local cmd=$(ps -p "$pid" -o comm= 2>/dev/null || true)
    if [[ "$cmd" != *"bash"* ]] && [[ "$cmd" != *"python"* ]] && [[ "$cmd" != *"uv"* ]]; then
        return 1
    fi
    
    return 0
}

# Cleanup function
cleanup() {
    local exit_code=$?
    
    # Remove our PID from current if it's us
    if [ -f "$CURRENT_PID_FILE" ]; then
        local current_pid=$(cat "$CURRENT_PID_FILE" 2>/dev/null || echo 0)
        if [ "$current_pid" -eq "$$" ]; then
            rm -f "$CURRENT_PID_FILE"
        fi
    fi
    
    # Remove ourselves from queue
    if [ -f "$QUEUE_FILE" ]; then
        grep -v "^$$:" "$QUEUE_FILE" > "${QUEUE_FILE}.tmp" 2>/dev/null || true
        mv -f "${QUEUE_FILE}.tmp" "$QUEUE_FILE" 2>/dev/null || true
    fi
    
    # Final orphan check on exit
    kill_orphans
    
    exit $exit_code
}

trap cleanup EXIT INT TERM

# Main execution starts here
log_info "Sequential executor starting for: $*"

# Step 1: Kill any orphans before we start
kill_orphans

# Step 2: Add ourselves to the queue
QUEUE_ENTRY="$$:$(date '+%s'):$*"
echo "$QUEUE_ENTRY" >> "$QUEUE_FILE"
log_queue "Added to queue: PID=$$ CMD=$*"

# Step 3: Wait for our turn (INDEFINITELY)
log_info "Waiting for exclusive lock..."
WAIT_COUNT=0

while true; do
    # Try to acquire lock
    if mkdir "$LOCKFILE" 2>/dev/null; then
        # We got the lock!
        echo $$ > "$CURRENT_PID_FILE"
        log_info "Lock acquired, starting execution"
        break
    fi
    
    # Check if current process is still alive
    if [ -f "$CURRENT_PID_FILE" ]; then
        CURRENT_PID=$(cat "$CURRENT_PID_FILE" 2>/dev/null || echo 0)
        
        if [ "$CURRENT_PID" -gt 0 ]; then
            if is_our_process_alive "$CURRENT_PID"; then
                # Still running, keep waiting
                if [ $((WAIT_COUNT % 30)) -eq 0 ]; then
                    local cmd=$(ps -p "$CURRENT_PID" -o args= 2>/dev/null | head -1 || echo "unknown")
                    log_queue "Still waiting... Current process: PID=$CURRENT_PID CMD=$cmd"
                fi
            else
                # Current process is dead but didn't clean up
                log_warn "Current process (PID=$CURRENT_PID) is dead, cleaning up"
                rm -f "$CURRENT_PID_FILE"
                rmdir "$LOCKFILE" 2>/dev/null || true
                
                # Kill any orphans it may have left
                kill_orphans
            fi
        else
            # No current PID but lock exists - stale lock
            log_warn "Stale lock detected, cleaning up"
            rmdir "$LOCKFILE" 2>/dev/null || true
        fi
    fi
    
    # Check queue position
    if [ -f "$QUEUE_FILE" ] && [ $((WAIT_COUNT % 60)) -eq 0 ]; then
        local position=$(grep -n "^$$:" "$QUEUE_FILE" 2>/dev/null | cut -d: -f1 || echo "?")
        local total=$(wc -l < "$QUEUE_FILE" 2>/dev/null || echo "?")
        log_queue "Queue position: $position of $total"
    fi
    
    # Periodic orphan cleanup (every 5 minutes)
    if [ $((WAIT_COUNT % 300)) -eq 0 ] && [ $WAIT_COUNT -gt 0 ]; then
        kill_orphans
    fi
    
    sleep 1
    WAIT_COUNT=$((WAIT_COUNT + 1))
done

# Step 4: Execute the command with process tree tracking
log_info "Executing: $*"

# Record process tree before execution
echo "=== Process tree before execution ===" > "$PROCESS_TREE_FILE"
get_process_tree $$ >> "$PROCESS_TREE_FILE"

# Execute the command
"$@" &
CMD_PID=$!

# Record command PID
echo "=== Command PID: $CMD_PID ===" >> "$PROCESS_TREE_FILE"

# Monitor the command
while kill -0 "$CMD_PID" 2>/dev/null; do
    # Periodic process tree update
    if [ $((SECONDS % 10)) -eq 0 ]; then
        echo "=== Process tree at ${SECONDS}s ===" >> "$PROCESS_TREE_FILE"
        get_process_tree $$ >> "$PROCESS_TREE_FILE"
    fi
    
    sleep 1
done

# Get exit code
wait "$CMD_PID"
EXIT_CODE=$?

# Step 5: Cleanup our execution
log_info "Command completed with exit code: $EXIT_CODE"

# Kill any remaining children
log_info "Cleaning up child processes..."
for pid in $(get_process_tree $$ | grep -v "^$$\$"); do
    if kill -0 "$pid" 2>/dev/null; then
        log_info "Killing remaining child: PID=$pid"
        kill -TERM "$pid" 2>/dev/null || true
    fi
done

# Wait a moment for graceful termination
sleep 2

# Force kill any stubborn processes
for pid in $(get_process_tree $$ | grep -v "^$$\$"); do
    if kill -0 "$pid" 2>/dev/null; then
        log_warn "Force killing stubborn child: PID=$pid"
        kill -KILL "$pid" 2>/dev/null || true
    fi
done

# Step 6: Release lock and clean up
rm -f "$CURRENT_PID_FILE"
rmdir "$LOCKFILE" 2>/dev/null || true

# Remove ourselves from queue
grep -v "^$$:" "$QUEUE_FILE" > "${QUEUE_FILE}.tmp" 2>/dev/null || true
mv -f "${QUEUE_FILE}.tmp" "$QUEUE_FILE" 2>/dev/null || true

# Final orphan check
kill_orphans

log_info "Execution complete"
exit $EXIT_CODE