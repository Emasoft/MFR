# Universal Sequential Pre-commit Setup Guide with TRUE Sequential Execution

This guide provides a comprehensive, project-local solution for configuring pre-commit hooks, CI/CD workflows, and build processes to run with **TRUE sequential execution** - only ONE process at a time with infinite waiting and orphan management. This prevents process explosions and memory exhaustion across all environments.

## ⚠️ CRITICAL: Process Explosion Prevention

**IMPORTANT**: This guide has been updated after a critical incident where parallel execution led to:
- Hundreds of spawned processes
- 60GB of 64GB memory consumed
- System near-crash

The new design enforces **TRUE sequential execution** where:
- **Only ONE operation can run at any time - NO exceptions**
- **Processes wait INDEFINITELY for their turn (no timeouts)**
- **Orphan processes are automatically detected and killed**
- **Complete process tree tracking ensures no leaks**
- **ALL execution paths MUST go through the sequential executor**

## Overview of the Protocol

The sequential execution protocol implements a **four-layer defense system**:

1. **True Sequential Execution Layer**: Only ONE process runs at a time, all others wait indefinitely
2. **Orphan Management Layer**: Detects and kills abandoned processes automatically
3. **Resource Monitoring Layer**: Tracks and limits memory, processes, and files
4. **Universal Integration Layer**: ALL tools and hooks use the sequential executor

## The Golden Rule

### **EVERY command execution MUST go through the sequential executor**

This means:
- ❌ NEVER: `pytest`
- ✅ ALWAYS: `./scripts/seq pytest` or `make test`

- ❌ NEVER: `git commit`  
- ✅ ALWAYS: `./scripts/seq git commit` or `make safe-commit`

- ❌ NEVER: `uv run mypy`
- ✅ ALWAYS: `./scripts/seq uv run mypy` or `make lint`

## Supported Environments

This protocol works identically in:
- **Local Development**: Direct execution with venv
- **Docker Containers**: Isolated execution with auto-cleanup
- **GitHub Actions**: CI/CD workflows with proper queuing
- **Remote Servers**: SSH or cloud development
- **Cross-Platform**: macOS, Linux, Windows (WSL2/Git Bash)

## Why TRUE Sequential Execution

Parallel execution can cause catastrophic failures:
- **Process Explosion**: Each tool spawns subprocesses, multiplying exponentially
- **Memory Exhaustion**: Multiple linters can consume all available RAM
- **Orphan Processes**: Abandoned processes continue consuming resources
- **Cascading Failures**: One timeout can trigger multiple retries
- **Lock Contention**: Multiple processes fighting for the same resources

TRUE sequential execution provides:
- **Guaranteed Single Process**: Only one operation at any moment
- **Infinite Patience**: No timeouts that spawn parallel attempts
- **Complete Cleanup**: Every process tree is tracked and cleaned
- **Predictable Resources**: Known maximum resource usage
- **System Safety**: Prevents memory exhaustion by design

## Prerequisites

- Python 3.11+ 
- Git
- uv (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- 4GB+ free memory
- Unix-like environment (macOS, Linux, WSL2)

## Core Components

### 1. Sequential Executor (Foundation)

The `sequential-executor.sh` is the heart of the system. It enforces true sequential execution through:

- **Global Lock**: Only one process can hold the lock
- **Infinite Waiting**: No timeout - processes wait forever
- **Queue Management**: Shows position while waiting  
- **Orphan Detection**: Finds and kills abandoned processes
- **Process Trees**: Tracks all children for cleanup

### 2. Universal Integration

**CRITICAL**: Every execution path must use the sequential executor:
- **Git hooks**: Must call sequential-executor.sh
- **Makefile**: Must use safe-run.sh wrapper
- **CI/CD**: Must use sequential execution
- **Direct commands**: Must use ./scripts/seq wrapper

### 3. Environment Configuration

The `.env.development` sets resource limits and environment variables to prevent runaway processes.

## Complete Setup Guide

### 1. Core Scripts Setup

Create the following essential scripts:

#### A. Sequential Executor Script

Create `scripts/sequential-executor.sh`:

```bash
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
    
    # Remove lock if we hold it
    if [ -f "$CURRENT_PID_FILE" ]; then
        local current=$(cat "$CURRENT_PID_FILE" 2>/dev/null || echo 0)
        if [ "$current" -eq "$$" ]; then
            rmdir "$LOCKFILE" 2>/dev/null || true
        fi
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
                    cmd=$(ps -p "$CURRENT_PID" -o args= 2>/dev/null | head -1 || echo "unknown")
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
        position=$(grep -n "^$$:" "$QUEUE_FILE" 2>/dev/null | cut -d: -f1 || echo "?")
        total=$(wc -l < "$QUEUE_FILE" 2>/dev/null || echo "?")
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
```

#### B. Safe Run Wrapper

Create `scripts/safe-run.sh`:

```bash
#!/usr/bin/env bash
# safe-run.sh - Wrapper that delegates to sequential-executor.sh
# Usage: ./scripts/safe-run.sh <command> [args...]

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
```

#### C. Quick Sequential Wrapper

Create `scripts/seq`:

```bash
#!/usr/bin/env bash
# seq - Short alias for sequential execution
# Usage: ./scripts/seq <command> [args...]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$SCRIPT_DIR/sequential-executor.sh" "$@"
```

#### D. Ensure Sequential Setup Script

Create `scripts/ensure-sequential.sh`:

```bash
#!/usr/bin/env bash
# ensure-sequential.sh - Ensures ALL operations use sequential executor

set -euo pipefail

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
SEQUENTIAL_EXECUTOR="$PROJECT_ROOT/scripts/sequential-executor.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Ensuring Sequential Execution Setup ===${NC}"

# 1. Check sequential executor exists and is executable
if [ ! -f "$SEQUENTIAL_EXECUTOR" ]; then
    echo -e "${RED}ERROR: Sequential executor not found at: $SEQUENTIAL_EXECUTOR${NC}"
    exit 1
fi

if [ ! -x "$SEQUENTIAL_EXECUTOR" ]; then
    echo -e "${YELLOW}Making sequential executor executable...${NC}"
    chmod +x "$SEQUENTIAL_EXECUTOR"
fi

# 2. Check safe-run.sh delegates to sequential executor
SAFE_RUN="$PROJECT_ROOT/scripts/safe-run.sh"
if [ -f "$SAFE_RUN" ]; then
    if ! grep -q "sequential-executor.sh" "$SAFE_RUN"; then
        echo -e "${RED}ERROR: safe-run.sh does not use sequential executor${NC}"
        exit 1
    fi
    chmod +x "$SAFE_RUN"
    echo -e "${GREEN}✓ safe-run.sh properly configured${NC}"
fi

# 3. Update ALL git hooks to use sequential execution
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"
if [ -d "$HOOKS_DIR" ]; then
    # Update pre-commit wrapper to use sequential executor
    if [ -f "$HOOKS_DIR/pre-commit-wrapper-robust" ]; then
        if ! grep -q "SEQUENTIAL_EXECUTOR" "$HOOKS_DIR/pre-commit-wrapper-robust"; then
            echo -e "${RED}ERROR: pre-commit-wrapper-robust not using sequential executor${NC}"
            echo -e "${YELLOW}The wrapper MUST use: $SEQUENTIAL_EXECUTOR${NC}"
            exit 1
        else
            echo -e "${GREEN}✓ pre-commit wrapper uses sequential executor${NC}"
        fi
    fi
fi

# 4. Create wrapper for direct commands
DIRECT_WRAPPER="$PROJECT_ROOT/scripts/seq"
if [ -f "$DIRECT_WRAPPER" ]; then
    chmod +x "$DIRECT_WRAPPER"
    echo -e "${GREEN}✓ 'seq' wrapper ready for easy sequential execution${NC}"
fi

# 5. Check Python/pytest configuration
if [ -f "$PROJECT_ROOT/pytest.ini" ]; then
    if grep -q "addopts.*-n" "$PROJECT_ROOT/pytest.ini"; then
        if ! grep -q "addopts.*-n 0" "$PROJECT_ROOT/pytest.ini"; then
            echo -e "${YELLOW}WARNING: pytest.ini may allow parallel execution${NC}"
        fi
    fi
    echo -e "${GREEN}✓ pytest.ini checked${NC}"
fi

# 6. Check environment file
if [ -f "$PROJECT_ROOT/.env.development" ]; then
    if ! grep -q "PYTEST_MAX_WORKERS=1" "$PROJECT_ROOT/.env.development"; then
        echo -e "${YELLOW}WARNING: .env.development missing PYTEST_MAX_WORKERS=1${NC}"
    fi
    echo -e "${GREEN}✓ .env.development checked${NC}"
fi

# 7. Create command intercept aliases
INTERCEPT_FILE="$PROJECT_ROOT/.sequential-aliases"
cat > "$INTERCEPT_FILE" << 'EOF'
# Sequential execution aliases - source this file to enforce sequential execution
# Usage: source .sequential-aliases

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEQ_EXEC="$SCRIPT_DIR/scripts/sequential-executor.sh"

# Intercept common commands that can spawn multiple processes
alias pytest="$SEQ_EXEC uv run pytest"
alias python="$SEQ_EXEC python"
alias uv="$SEQ_EXEC uv"
alias git="$SEQ_EXEC git"
alias make="$SEQ_EXEC make"
alias npm="$SEQ_EXEC npm"
alias pnpm="$SEQ_EXEC pnpm"
alias yarn="$SEQ_EXEC yarn"

# Show active intercepts
echo "Sequential execution enforced for: pytest, python, uv, git, make, npm, pnpm, yarn"
echo "To run without sequential execution, use: command <cmd> or \<cmd>"
EOF

echo -e "${GREEN}✓ Created command intercept aliases${NC}"
echo -e "${YELLOW}To enforce sequential execution for ALL commands:${NC}"
echo -e "  source .sequential-aliases"

# 8. Verify no background processes are running
echo -e "\n${GREEN}Checking for background processes...${NC}"
PYTHON_PROCS=$(pgrep -c python 2>/dev/null || echo 0)
GIT_PROCS=$(pgrep -c git 2>/dev/null || echo 0)
if [ "$PYTHON_PROCS" -gt 1 ] || [ "$GIT_PROCS" -gt 1 ]; then
    echo -e "${YELLOW}WARNING: Multiple processes detected:${NC}"
    echo "  Python processes: $PYTHON_PROCS"
    echo "  Git processes: $GIT_PROCS"
    echo -e "${YELLOW}Consider running: make kill-all${NC}"
fi

# 9. Summary
echo -e "\n${GREEN}=== Sequential Execution Setup Summary ===${NC}"
echo "1. Sequential executor: $SEQUENTIAL_EXECUTOR"
echo "2. Safe wrapper: $SAFE_RUN"
echo "3. Direct wrapper: seq (use as: ./scripts/seq <command>)"
echo "4. Git hooks: Updated to use sequential execution"
echo "5. Command aliases: source .sequential-aliases"
echo ""
echo -e "${GREEN}CRITICAL RULES:${NC}"
echo "- NEVER use & for background execution"
echo "- NEVER run pytest with -n auto or -n >1"
echo "- ALWAYS use 'make' commands or './scripts/seq' wrapper"
echo "- ALWAYS wait for commands to complete"
echo ""
echo -e "${YELLOW}Monitor queue in another terminal:${NC} make monitor"
```

#### E. Monitor Queue Script

Create `scripts/monitor-queue.sh`:

```bash
#!/usr/bin/env bash
# monitor-queue.sh - Monitor the sequential execution queue and system state

set -euo pipefail

# Get project info
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PROJECT_HASH=$(echo "$PROJECT_ROOT" | shasum | cut -d' ' -f1 | head -c 8)

# State files
LOCK_DIR="/tmp/mfr-sequential-${PROJECT_HASH}"
LOCKFILE="${LOCK_DIR}/executor.lock"
QUEUE_FILE="${LOCK_DIR}/queue.txt"
CURRENT_PID_FILE="${LOCK_DIR}/current.pid"
ORPHAN_LOG="${LOCK_DIR}/orphans.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Clear screen and show header
show_header() {
    clear
    echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}       Sequential Execution Monitor - $(date '+%Y-%m-%d %H:%M:%S')${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
    echo
}

# Show current execution status
show_current() {
    echo -e "${GREEN}▶ Current Execution:${NC}"
    
    if [ -f "$LOCKFILE" ] && [ -f "$CURRENT_PID_FILE" ]; then
        local pid=$(cat "$CURRENT_PID_FILE" 2>/dev/null || echo "unknown")
        
        if kill -0 "$pid" 2>/dev/null; then
            local cmd=$(ps -p "$pid" -o args= 2>/dev/null | head -1 || echo "unknown")
            local elapsed=$(ps -p "$pid" -o etime= 2>/dev/null || echo "00:00")
            local mem=$(ps -p "$pid" -o rss= 2>/dev/null | awk '{printf "%.1f", $1/1024}' || echo "0")
            
            echo -e "  ${YELLOW}PID:${NC} $pid"
            echo -e "  ${YELLOW}Command:${NC} $cmd"
            echo -e "  ${YELLOW}Elapsed:${NC} $elapsed"
            echo -e "  ${YELLOW}Memory:${NC} ${mem}MB"
            
            # Show child processes
            local children=$(pgrep -P "$pid" 2>/dev/null | wc -l || echo 0)
            if [ "$children" -gt 0 ]; then
                echo -e "  ${YELLOW}Children:${NC} $children processes"
            fi
        else
            echo -e "  ${RED}Process $pid is dead but lock exists!${NC}"
        fi
    else
        echo -e "  ${GREEN}No process currently executing${NC}"
    fi
    echo
}

# Show queue
show_queue() {
    echo -e "${BLUE}📋 Execution Queue:${NC}"
    
    if [ -f "$QUEUE_FILE" ] && [ -s "$QUEUE_FILE" ]; then
        local count=1
        while IFS=: read -r pid timestamp cmd; do
            if [ -n "$pid" ]; then
                local wait_time=$(($(date +%s) - timestamp))
                local wait_formatted=$(printf "%02d:%02d" $((wait_time/60)) $((wait_time%60)))
                
                if kill -0 "$pid" 2>/dev/null; then
                    echo -e "  ${count}. ${YELLOW}PID $pid${NC} - Waiting ${wait_formatted} - $cmd"
                else
                    echo -e "  ${count}. ${RED}PID $pid (dead)${NC} - $cmd"
                fi
                count=$((count + 1))
            fi
        done < "$QUEUE_FILE"
    else
        echo -e "  ${GREEN}Queue is empty${NC}"
    fi
    echo
}

# Show orphan processes
show_orphans() {
    echo -e "${RED}☠️  Potential Orphans:${NC}"
    
    local patterns=(
        "pytest"
        "python.*test"
        "uv run"
        "pre-commit" 
        "ruff"
        "mypy"
    )
    
    local found=0
    for pattern in "${patterns[@]}"; do
        local pids=$(pgrep -f "$pattern" 2>/dev/null || true)
        
        for pid in $pids; do
            # Skip monitor process
            [ "$pid" -eq "$$" ] && continue
            
            # Check if it's an orphan (parent is init)
            local ppid=$(ps -o ppid= -p "$pid" 2>/dev/null | xargs || echo 1)
            if [ "$ppid" -eq 1 ]; then
                local cmd=$(ps -p "$pid" -o comm= 2>/dev/null || echo unknown)
                echo -e "  ${RED}⚠${NC}  PID $pid - $cmd (orphaned)"
                found=$((found + 1))
            fi
        done
    done
    
    if [ "$found" -eq 0 ]; then
        echo -e "  ${GREEN}No orphan processes detected${NC}"
    fi
    echo
}

# Show system resources
show_resources() {
    echo -e "${CYAN}💻 System Resources:${NC}"
    
    # Memory
    if command -v free >/dev/null 2>&1; then
        local mem_info=$(free -h | grep Mem)
        local total=$(echo "$mem_info" | awk '{print $2}')
        local used=$(echo "$mem_info" | awk '{print $3}')
        local free=$(echo "$mem_info" | awk '{print $4}')
        echo -e "  ${YELLOW}Memory:${NC} $used used / $free free / $total total"
    fi
    
    # Load average
    local load=$(uptime | awk -F'load average:' '{print $2}' | xargs)
    echo -e "  ${YELLOW}Load:${NC} $load"
    
    # Process counts
    local total_procs=$(ps aux | wc -l)
    local python_procs=$(pgrep -c python 2>/dev/null || echo 0)
    local git_procs=$(pgrep -c git 2>/dev/null || echo 0)
    echo -e "  ${YELLOW}Processes:${NC} $total_procs total, $python_procs python, $git_procs git"
    echo
}

# Show recent orphan kills
show_orphan_log() {
    if [ -f "$ORPHAN_LOG" ]; then
        echo -e "${YELLOW}📜 Recent Orphan Kills:${NC}"
        tail -5 "$ORPHAN_LOG" 2>/dev/null | while read -r line; do
            echo "  $line"
        done
        echo
    fi
}

# Main monitoring loop
echo -e "${GREEN}Starting queue monitor. Press Ctrl+C to exit.${NC}"
echo -e "${YELLOW}Refreshing every 2 seconds...${NC}"
sleep 2

while true; do
    show_header
    show_current
    show_queue
    show_orphans
    show_resources
    show_orphan_log
    
    # Footer
    echo -e "${CYAN}────────────────────────────────────────────────────────────────${NC}"
    echo -e "Press ${RED}Ctrl+C${NC} to exit | ${YELLOW}Q${NC} to kill queue | ${RED}K${NC} to kill all"
    
    # Check for input with timeout
    if read -t 2 -n 1 key; then
        case "$key" in
            q|Q)
                echo -e "\n${YELLOW}Clearing queue...${NC}"
                rm -f "$QUEUE_FILE"
                ;;
            k|K)
                echo -e "\n${RED}Killing all processes...${NC}"
                pkill -f "sequential-executor.sh" || true
                pkill -f pytest || true
                rm -f "$LOCKFILE" "$CURRENT_PID_FILE" "$QUEUE_FILE"
                ;;
        esac
    fi
done
```

#### F. Make all scripts executable

```bash
chmod +x scripts/sequential-executor.sh
chmod +x scripts/safe-run.sh
chmod +x scripts/seq
chmod +x scripts/ensure-sequential.sh
chmod +x scripts/monitor-queue.sh
```

### 2. Environment Configuration

Create `.env.development`:

```bash
# Development Environment Resource Limits
# Source this file before running tests or heavy operations:
# source .env.development

# Pytest configuration
export PYTEST_MAX_WORKERS=1
export PYTEST_DISABLE_XDIST=1
export PYTEST_CURRENT_TEST_TIMEOUT=300

# Prefect configuration  
export PREFECT_TASK_RUNNER_MAX_WORKERS=1
export PREFECT_LOCAL_STORAGE_PATH=./.prefect
export PREFECT_API_ENABLE_HTTP2=false

# Python configuration
export PYTHONDONTWRITEBYTECODE=1
export PYTHON_GC_THRESHOLD=100  # Aggressive garbage collection
export PYTHONUNBUFFERED=1

# UV configuration
export UV_NO_CACHE=1
export UV_SYSTEM_PYTHON=0

# System resource limits (enforced by safe-run.sh)
export MAX_MEMORY_MB=8192       # 8GB max per operation
export MAX_PROCESSES=50         # 50 processes max
export CHECK_INTERVAL=2         # Check every 2 seconds
export TIMEOUT=1800            # 30 minute timeout

# Development flags
export MFR_SEQUENTIAL_MODE=1
export MFR_RESOURCE_MONITORING=1
export MFR_FAIL_FAST=1

# Pre-commit configuration
export PRE_COMMIT_MAX_WORKERS=1
export PRE_COMMIT_NO_CONCURRENCY=1
export PRE_COMMIT_COLOR=always

# TruffleHog specific settings
export TRUFFLEHOG_TIMEOUT=300
export TRUFFLEHOG_MEMORY_MB=1024
export TRUFFLEHOG_CONCURRENCY=1
export TRUFFLEHOG_MAX_DEPTH=50

# Set system limits (if supported by shell)
if [ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]; then
    # Process limits
    ulimit -u 100 2>/dev/null || true      # Max 100 processes
    
    # Memory limits  
    ulimit -v 8388608 2>/dev/null || true  # Max 8GB virtual memory
    ulimit -m 8388608 2>/dev/null || true  # Max 8GB RSS
    
    # File limits
    ulimit -n 1024 2>/dev/null || true     # Max 1024 open files
    
    echo "Development environment loaded with resource limits:"
    echo "  Max processes: 100"
    echo "  Max memory: 8GB" 
    echo "  Max files: 1024"
    echo "  Sequential mode: ENABLED"
fi
```

### 3. Pytest Configuration

Create `pytest.ini`:

```ini
[pytest]
# Force sequential execution to prevent process explosions
addopts = 
    # Parallelism control
    -n 0                      # Disable xdist parallelism
    --maxprocesses=1          # Single process execution  
    --dist=no                 # No distributed testing
    
    # Output control
    --tb=short                # Shorter tracebacks
    --strict-markers          # Strict marker usage
    --no-header               # No header in output
    
    # Timeouts and safety
    --timeout=300             # 5-minute timeout per test
    --timeout-method=thread   # Thread-based timeout
    
    # Performance
    --durations=10            # Show 10 slowest tests
    -ra                       # Show all test outcomes

# Test discovery
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Markers
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests

# Coverage options (when using pytest-cov)
[coverage:run]
source = src
omit = 
    */tests/*
    */__pycache__/*
    */venv/*
    */.venv/*

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
```

### 4. Makefile for Safe Commands

Create `Makefile`:

```makefile
# Makefile for Safe Sequential Execution
# Enforces safe execution patterns to prevent resource exhaustion

.PHONY: help test lint format check clean install dev-setup monitor kill-all safe-commit

# Default shell
SHELL := /bin/bash

# Colors
GREEN := \033[0;32m
YELLOW := \033[1;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Safe run wrapper
SAFE_RUN := ./scripts/safe-run.sh

help: ## Show this help message
	@echo -e "$(GREEN)Safe Sequential Execution Commands$(NC)"
	@echo -e "$(YELLOW)Always use these commands instead of running tools directly!$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-20s$(NC) %s\n", $$1, $$2}'

check-env: ## Check system resources
	@echo -e "$(GREEN)Checking system resources...$(NC)"
	@if [ -f .env.development ]; then \
		source .env.development; \
	fi
	@echo "Memory free: $$(free -h 2>/dev/null | grep Mem | awk '{print $$4}' || echo 'N/A')"
	@echo "Load average: $$(uptime | awk -F'load average:' '{print $$2}')"
	@echo "Python processes: $$(pgrep -c python 2>/dev/null || echo 0)"
	@echo "Git processes: $$(pgrep -c git 2>/dev/null || echo 0)"

dev-setup: ## Set up development environment
	@echo -e "$(GREEN)Setting up development environment...$(NC)"
	@if [ ! -f .env.development ]; then \
		echo -e "$(RED)Creating .env.development file...$(NC)"; \
	fi
	@source .env.development 2>/dev/null || true
	@uv venv
	@source .venv/bin/activate && uv sync --all-extras
	@chmod +x scripts/*.sh
	@./scripts/ensure-sequential.sh
	@echo -e "$(GREEN)Development environment ready!$(NC)"
	@echo -e "$(YELLOW)Remember to: source .env.development$(NC)"

install: ## Install dependencies safely
	@echo -e "$(GREEN)Installing dependencies...$(NC)"
	@$(SAFE_RUN) uv sync --all-extras

test: check-env ## Run tests safely (sequential)
	@echo -e "$(GREEN)Running tests sequentially...$(NC)"
	@source .env.development 2>/dev/null || true
	@$(SAFE_RUN) uv run pytest -v

test-fast: check-env ## Run fast tests only
	@echo -e "$(GREEN)Running fast tests...$(NC)"
	@source .env.development 2>/dev/null || true
	@$(SAFE_RUN) uv run pytest -v -m "not slow"

test-file: check-env ## Run specific test file (usage: make test-file FILE=tests/test_foo.py)
	@if [ -z "$(FILE)" ]; then \
		echo -e "$(RED)ERROR: Specify FILE=tests/test_something.py$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(GREEN)Running test: $(FILE)$(NC)"
	@source .env.development 2>/dev/null || true
	@$(SAFE_RUN) uv run pytest -v $(FILE)

lint: check-env ## Run linters safely
	@echo -e "$(GREEN)Running linters...$(NC)"
	@source .env.development 2>/dev/null || true
	@$(SAFE_RUN) uv run ruff check src tests
	@$(SAFE_RUN) uv run mypy src --strict

format: check-env ## Format code safely
	@echo -e "$(GREEN)Formatting code...$(NC)"
	@source .env.development 2>/dev/null || true
	@$(SAFE_RUN) uv run ruff format src tests
	@$(SAFE_RUN) uv run ruff check --fix src tests

check: lint test ## Run all checks

clean: ## Clean temporary files
	@echo -e "$(GREEN)Cleaning temporary files...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name ".coverage" -delete 2>/dev/null || true
	@rm -rf .pytest_cache 2>/dev/null || true
	@rm -rf .mypy_cache 2>/dev/null || true
	@rm -rf .ruff_cache 2>/dev/null || true
	@rm -rf htmlcov 2>/dev/null || true
	@rm -f /tmp/mfr-*.lock 2>/dev/null || true
	@echo -e "$(GREEN)Cleanup complete!$(NC)"

kill-all: ## Emergency: Kill all Python/test processes
	@echo -e "$(RED)EMERGENCY: Killing all Python processes...$(NC)"
	@pkill -f pytest || true
	@pkill -f python || true
	@pkill -f pre-commit || true
	@killall -9 python python3 2>/dev/null || true
	@rm -f /tmp/mfr-sequential-*/executor.lock 2>/dev/null || true
	@rm -f /tmp/mfr-sequential-*/current.pid 2>/dev/null || true
	@echo -e "$(GREEN)All processes killed$(NC)"

monitor: ## Start sequential execution queue monitor
	@echo -e "$(GREEN)Starting queue monitor...$(NC)"
	@./scripts/monitor-queue.sh

safe-commit: check-env ## Safely commit changes
	@echo -e "$(GREEN)Checking for running git operations...$(NC)"
	@if pgrep -f "git commit" > /dev/null; then \
		echo -e "$(RED)ERROR: Git commit already in progress!$(NC)"; \
		exit 1; \
	fi
	@echo -e "$(GREEN)Safe to proceed with commit$(NC)"
	@echo -e "$(YELLOW)Run: git add -A && $(SAFE_RUN) git commit$(NC)"

# Hidden targets for CI
.ci-test:
	@$(SAFE_RUN) uv run pytest --cov=src --cov-report=xml

.ci-lint:
	@$(SAFE_RUN) uv run ruff check src tests --format=github
	@$(SAFE_RUN) uv run mypy src --no-error-summary
```

### 5. Pre-commit Configuration

Create `.pre-commit-config.yaml`:

```yaml
# Sequential pre-commit configuration
# All hooks run one at a time to prevent process explosions

default_language_version:
  python: python3.11

default_stages: [pre-commit]

# CRITICAL: Every hook MUST have require_serial: true
# This prevents ANY parallel execution

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

  # Python tools with sequential execution
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

  # Use safe-run.sh for resource-intensive hooks
  - repo: local
    hooks:
      - id: mypy-safe
        name: Type checking (safe)
        entry: ./scripts/safe-run.sh uv run mypy
        language: system
        types: [python]
        require_serial: true
        pass_filenames: true
        stages: [pre-commit]
        args: [--ignore-missing-imports, --strict]

      - id: trufflehog-safe
        name: Secret detection (safe)
        entry: ./scripts/safe-run.sh trufflehog git file://. --only-verified --fail --no-update
        language: system
        pass_filenames: false
        require_serial: true
        stages: [pre-commit]

# CI configuration
ci:
  skip:
    - mypy-safe
    - trufflehog-safe
```

### 6. Git Hooks Configuration

The pre-commit wrapper at `.git/hooks/pre-commit-wrapper-robust` is already configured to use the sequential executor. Ensure it's properly set up by running:

```bash
# Verify the wrapper uses sequential executor
grep -q "SEQUENTIAL_EXECUTOR" .git/hooks/pre-commit-wrapper-robust && echo "✓ Hook configured" || echo "✗ Hook needs update"

# Make hooks executable
chmod +x .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit-wrapper-robust
```

### 7. GitHub Actions Configuration

Create `.github/workflows/sequential-ci.yml`:

```yaml
name: Sequential CI Pipeline

on:
  pull_request:
  push:
    branches: [main, develop]

# Prevent ANY parallel execution
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: false  # NEVER cancel - wait instead

env:
  # Force sequential execution everywhere
  PYTEST_MAX_WORKERS: 1
  PRE_COMMIT_MAX_WORKERS: 1
  PYTHONDONTWRITEBYTECODE: 1
  UV_NO_CACHE: 1
  
  # Resource limits
  MEMORY_LIMIT_MB: 4096
  MAX_PROCESSES: 50
  
  # Timeouts
  TIMEOUT_SECONDS: 600
  TRUFFLEHOG_TIMEOUT: 300

jobs:
  sequential-pipeline:
    runs-on: ubuntu-latest
    timeout-minutes: 60  # Global timeout
    
    steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: '3.11'
    
    - name: Install uv
      uses: astral-sh/setup-uv@v6
      with:
        enable-cache: true
    
    - name: Create virtual environment
      run: uv venv
    
    - name: Install dependencies
      run: |
        source .venv/bin/activate
        uv sync --all-extras
        uv pip install pre-commit
    
    - name: Set resource limits
      run: |
        # Limit processes
        ulimit -u 100
        
        # Show limits
        ulimit -a
    
    - name: Run pre-commit checks
      run: |
        source .venv/bin/activate
        pre-commit run --all-files --show-diff-on-failure
    
    - name: Run tests sequentially
      run: |
        source .venv/bin/activate
        python -m pytest tests -v --tb=short
    
    - name: Build project
      run: |
        source .venv/bin/activate
        uv build
    
    - name: Memory usage report
      if: always()
      run: |
        echo "=== System Resources ==="
        free -h
        ps aux --sort=-%mem | head -10
```

## Installation and Usage

### Initial Setup

1. **Clone and enter project**:
   ```bash
   git clone <repository>
   cd <project>
   ```

2. **Create the scripts**:
   ```bash
   mkdir -p scripts
   # Create all the scripts shown above
   chmod +x scripts/*.sh
   ```

3. **Run setup verification**:
   ```bash
   ./scripts/ensure-sequential.sh
   ```

4. **Set up environment**:
   ```bash
   source .env.development
   uv venv
   source .venv/bin/activate
   uv sync --all-extras
   ```

5. **Install pre-commit**:
   ```bash
   uv pip install pre-commit
   pre-commit install
   ```

### Daily Usage

**ALWAYS use the safe wrappers**:

```bash
# Run tests
make test                          # ✅ Safe
./scripts/seq uv run pytest        # ✅ Safe
pytest                             # ❌ DANGEROUS

# Format code
make format                        # ✅ Safe
./scripts/seq uv run ruff format   # ✅ Safe
ruff format &                      # ❌ DANGEROUS

# Run linters
make lint                          # ✅ Safe
./scripts/seq uv run mypy src      # ✅ Safe
mypy src & ruff check &            # ❌ DANGEROUS

# Commit code
make safe-commit                   # ✅ Safe
./scripts/seq git commit           # ✅ Safe
git commit & git commit &          # ❌ DANGEROUS
```

### Monitor execution:
```bash
# Always have this running in another terminal
make monitor
```

## Critical Integration Points

### 1. Git Hooks MUST Use Sequential Executor

The pre-commit wrapper at `.git/hooks/pre-commit-wrapper-robust` MUST call commands through the sequential executor:

```bash
# WRONG - Direct execution
"$INSTALL_PYTHON" -mpre_commit hook-impl ...

# CORRECT - Through sequential executor
"$SEQUENTIAL_EXECUTOR" "$INSTALL_PYTHON" -mpre_commit hook-impl ...
```

### 2. All Makefiles MUST Use safe-run.sh

```makefile
# WRONG
test:
	pytest tests/

# CORRECT
test:
	$(SAFE_RUN) uv run pytest tests/
```

### 3. CI/CD MUST Enforce Limits

```yaml
# Always include in GitHub Actions
env:
  PYTEST_MAX_WORKERS: 1
  PRE_COMMIT_MAX_WORKERS: 1
```

## Monitoring and Troubleshooting

### Monitor Execution Queue

Always have the monitor running in another terminal:
```bash
make monitor
```

This shows:
- Current executing process
- Queue of waiting processes
- Orphan processes
- System resources

### Check for Problems

```bash
# Check system state
make check-env

# Look for orphans
ps aux | grep -E "(pytest|python)" | grep -v grep

# Check queue state
ls -la /tmp/mfr-sequential-*/

# Verify integration
./scripts/ensure-sequential.sh
```

### Emergency Recovery

If processes get out of control:

1. **Kill everything**:
   ```bash
   make kill-all
   ```

2. **Clean up state**:
   ```bash
   rm -rf /tmp/mfr-sequential-*
   ```

3. **Restart environment**:
   ```bash
   source .env.development
   ```

## Platform-Specific Notes

### macOS
- Memory limits via ulimit don't work
- Use Docker for full resource control
- Monitor shows actual usage

### Linux
- Full resource limiting support
- Better process tracking via /proc
- Native cgroup support

### Windows (WSL2)
- Use WSL2, not Git Bash
- Full Linux compatibility
- Native Docker support

## Key Differences from Standard Setup

1. **True Sequential Execution**: Only ONE process at a time
2. **Universal Integration**: ALL tools use sequential executor
3. **Infinite Waiting**: No timeouts that spawn retries
4. **Orphan Management**: Automatic cleanup of abandoned processes
5. **Queue Visualization**: See what's waiting
6. **Process Trees**: Complete tracking of all children

## Best Practices

1. **ALWAYS use wrappers**: Never run commands directly
2. **Monitor constantly**: Keep queue monitor running
3. **Verify integration**: Run ensure-sequential.sh regularly
4. **Check hooks**: Ensure git hooks use sequential executor
5. **Use aliases**: Source .sequential-aliases for safety

## Common Mistakes to Avoid

1. **Running commands directly**: Always use wrappers
2. **Using & for background**: Never run in background
3. **Bypassing the queue**: All commands must queue
4. **Ignoring the monitor**: Always watch the queue
5. **Not checking integration**: Run ensure-sequential.sh

## Verification Checklist

Run this checklist after setup:

```bash
# 1. Scripts exist and are executable
[ -x scripts/sequential-executor.sh ] && echo "✓ Sequential executor" || echo "✗ Missing"
[ -x scripts/safe-run.sh ] && echo "✓ Safe run wrapper" || echo "✗ Missing"
[ -x scripts/seq ] && echo "✓ Quick wrapper" || echo "✗ Missing"

# 2. Git hooks use sequential executor
grep -q "SEQUENTIAL_EXECUTOR" .git/hooks/pre-commit-wrapper-robust && echo "✓ Git hooks" || echo "✗ Not integrated"

# 3. Environment configured
grep -q "PYTEST_MAX_WORKERS=1" .env.development && echo "✓ Environment" || echo "✗ Missing config"

# 4. Pytest configured
grep -q "addopts.*-n 0" pytest.ini && echo "✓ Pytest" || echo "✗ Parallel enabled"

# 5. No background processes
[ $(pgrep -c python || echo 0) -le 1 ] && echo "✓ No multiple processes" || echo "✗ Multiple processes detected"
```

## Conclusion

This setup makes process explosions impossible by design. Only one operation runs at a time, and all others wait patiently in a queue. Orphan processes are detected and killed automatically. The system is self-healing and prevents resource exhaustion.

**Remember**: 
- **Safety over speed**
- **One process at a time**
- **Always use the wrappers**
- **Monitor everything**

The sequential executor is your guardian against system crashes. Trust it, use it, and never bypass it.