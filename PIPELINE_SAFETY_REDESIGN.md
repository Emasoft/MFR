# Pipeline Safety Redesign - TRUE Sequential Execution

## Executive Summary

This document addresses the critical process explosion incident where the system spawned hundreds of processes, consuming nearly 60GB of 64GB available memory. It provides a comprehensive redesign with **TRUE SEQUENTIAL EXECUTION** where only ONE process runs at a time, with infinite waiting and orphan management.

## Root Cause Analysis

### What Happened
1. Multiple pytest commands were run in parallel using shell background execution (`&`)
2. Each pytest instance spawned its own process tree
3. Multiple git commit attempts triggered overlapping pre-commit hooks
4. No global resource limits were enforced
5. No monitoring alerted to the growing resource usage

### Why It Happened
1. **Human Error**: Violated sequential execution principles
2. **Missing Safeguards**: No system-wide process limits
3. **Insufficient Monitoring**: No real-time resource alerts
4. **Default Behaviors**: Tools defaulted to parallel execution

## Redesigned Safety Architecture - TRUE Sequential Execution

### Core Principle: ONE Process at a Time

The new design enforces absolute sequential execution:
- **Only ONE operation can run at any time** - no exceptions
- **Infinite waiting** - no timeouts that allow parallel execution
- **Orphan detection and cleanup** - no zombie processes
- **Process genealogy tracking** - complete process tree management

### Layer 0: Sequential Executor (NEW)

The `sequential-executor.sh` is the foundation of the new safety system:

```bash
# Features:
1. Global lock with NO timeout - waits forever
2. Process queue management - tracks all waiting processes
3. Orphan detection - finds and kills abandoned processes
4. Process tree tracking - monitors all children
5. Automatic cleanup - ensures no process leakage
```

#### How It Works:

1. **Lock Acquisition**:
   - Tries to acquire exclusive lock
   - If locked, waits INDEFINITELY (no 30s timeout)
   - Monitors if current process is still alive
   - Cleans up stale locks from dead processes

2. **Queue Management**:
   - Every process adds itself to queue
   - Shows position in queue while waiting
   - Removes completed processes from queue

3. **Orphan Management**:
   - Checks for orphans before starting
   - Periodic checks during execution
   - Kills entire process trees of orphans
   - Logs all orphan kills for audit

4. **Process Tree Tracking**:
   - Records all child processes
   - Monitors process genealogy
   - Ensures complete cleanup on exit

### Layer 1: Command Execution Safety

#### 1.1 Create a Safe Command Runner
```bash
#!/usr/bin/env bash
# safe-run.sh - Prevents parallel execution and monitors resources

LOCKFILE="/tmp/mfr-command.lock"
MAX_MEMORY_MB=8192  # 8GB max per command
MAX_PROCESSES=20    # Max processes per command

# Acquire exclusive lock
exec 200>"$LOCKFILE"
if ! flock -n 200; then
    echo "ERROR: Another command is already running. Please wait."
    exit 1
fi

# Monitor and limit resources
ulimit -v $((MAX_MEMORY_MB * 1024))  # Virtual memory limit
ulimit -u $MAX_PROCESSES              # Process limit

# Execute command with monitoring
"$@" &
PID=$!

# Monitor loop
while kill -0 $PID 2>/dev/null; do
    MEM_KB=$(ps -o vsz= -p $PID | awk '{sum+=$1} END {print sum}')
    MEM_MB=$((MEM_KB / 1024))
    
    if [ $MEM_MB -gt $MAX_MEMORY_MB ]; then
        echo "ERROR: Memory limit exceeded (${MEM_MB}MB > ${MAX_MEMORY_MB}MB)"
        kill -TERM $PID
        exit 137
    fi
    
    sleep 1
done

wait $PID
```

#### 1.2 Pytest Configuration
Create `pytest.ini`:
```ini
[pytest]
# Force sequential execution
addopts = 
    -n 0                    # Disable xdist parallelism
    --maxprocesses=1        # Single process execution
    --dist=no               # No distributed testing
    --tb=short              # Shorter tracebacks
    --strict-markers        # Strict marker usage
    --timeout=300           # 5-minute timeout per test
    --timeout-method=thread # Use thread-based timeout

# Resource limits
max-worker-restart = 1      # Restart workers after 1 test
```

#### 1.3 Git Hooks Enhancement
Update `.git/hooks/pre-commit-wrapper-robust`:
```bash
# Add at the beginning
# Check system resources before starting
TOTAL_MEM_MB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2/1024}' || sysctl -n hw.memsize 2>/dev/null | awk '{print $1/1024/1024}' || echo 65536)
FREE_MEM_MB=$(grep MemAvailable /proc/meminfo 2>/dev/null | awk '{print $2/1024}' || vm_stat 2>/dev/null | grep free | awk '{print $3 * 4 / 1024}' || echo 8192)
LOAD_AVG=$(uptime | awk -F'load average:' '{print $2}' | awk -F, '{print $1}' | xargs)

if (( $(echo "$FREE_MEM_MB < 4096" | bc -l) )); then
    echo "ERROR: Insufficient memory (${FREE_MEM_MB}MB free, need 4096MB)"
    exit 1
fi

if (( $(echo "$LOAD_AVG > 8.0" | bc -l) )); then
    echo "ERROR: System load too high ($LOAD_AVG, max 8.0)"
    exit 1
fi
```

### Layer 2: System-Wide Protection

#### 2.1 Create System Resource Monitor
```bash
#!/usr/bin/env bash
# system-monitor.sh - Monitors and kills runaway processes

THRESHOLD_MEM_PERCENT=80
THRESHOLD_PROCESSES=100
CHECK_INTERVAL=5

while true; do
    # Check memory usage
    MEM_PERCENT=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}' 2>/dev/null || echo 0)
    
    if [ $MEM_PERCENT -gt $THRESHOLD_MEM_PERCENT ]; then
        echo "WARNING: Memory usage at ${MEM_PERCENT}%"
        
        # Find and kill largest processes
        ps aux --sort=-%mem | head -20 | grep -E "(pytest|python|node)" | while read -r line; do
            PID=$(echo "$line" | awk '{print $2}')
            MEM=$(echo "$line" | awk '{print $4}')
            CMD=$(echo "$line" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i}')
            
            if (( $(echo "$MEM > 10.0" | bc -l) )); then
                echo "Killing high-memory process: PID=$PID MEM=$MEM% CMD=$CMD"
                kill -TERM $PID 2>/dev/null
            fi
        done
    fi
    
    # Check process count
    PROC_COUNT=$(ps aux | wc -l)
    if [ $PROC_COUNT -gt $THRESHOLD_PROCESSES ]; then
        echo "WARNING: Too many processes ($PROC_COUNT)"
    fi
    
    sleep $CHECK_INTERVAL
done
```

#### 2.2 Development Environment Configuration
Create `.env.development`:
```bash
# Resource limits for development
export PYTEST_MAX_WORKERS=1
export PYTEST_DISABLE_XDIST=1
export PREFECT_TASK_RUNNER_MAX_WORKERS=1
export PREFECT_LOCAL_STORAGE_PATH=./.prefect
export UV_NO_CACHE=1
export PYTHON_GC_THRESHOLD=100  # Aggressive garbage collection

# System limits
ulimit -u 100     # Max 100 processes
ulimit -v 8388608 # Max 8GB virtual memory per process
ulimit -n 1024    # Max 1024 open files
```

### Layer 3: CI/CD Integration

#### 3.1 GitHub Actions Resource Control
Update workflows to include:
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    
    env:
      PYTEST_MAX_WORKERS: 1
      PYTHONDONTWRITEBYTECODE: 1
      
    steps:
    - name: Set Resource Limits
      run: |
        # Limit memory to 4GB
        sudo sh -c "echo '$USER hard as 4194304' >> /etc/security/limits.conf"
        
        # Limit processes
        ulimit -u 50
        
        # Show limits
        ulimit -a
```

### Layer 4: Developer Guidelines

#### 4.1 Command Execution Rules
1. **NEVER** run multiple test commands in parallel
2. **NEVER** use `&` for background execution without process management
3. **ALWAYS** wait for commands to complete before starting new ones
4. **ALWAYS** use the `safe-run.sh` wrapper for long-running commands

#### 4.2 Testing Best Practices
```bash
# Good - Sequential execution
safe-run.sh uv run pytest tests/test_one.py
safe-run.sh uv run pytest tests/test_two.py

# Bad - Parallel execution
uv run pytest tests/test_one.py &
uv run pytest tests/test_two.py &

# Good - Limited parallelism
safe-run.sh uv run pytest -n 2 tests/  # Max 2 workers

# Bad - Unlimited parallelism
uv run pytest -n auto tests/  # Uses all CPU cores
```

#### 4.3 Git Operations
```bash
# Good - Check for running operations
if pgrep -f "git commit" > /dev/null; then
    echo "Git operation in progress, waiting..."
    sleep 5
fi
git commit -m "message"

# Bad - Multiple commits
git commit -m "one" &
git commit -m "two" &
```

### Layer 5: Monitoring and Alerts

#### 5.1 Real-time Dashboard
Create `monitor-dashboard.sh`:
```bash
#!/usr/bin/env bash
# Shows real-time resource usage

while true; do
    clear
    echo "=== MFR Resource Monitor ==="
    echo "Time: $(date)"
    echo ""
    
    # Memory
    echo "MEMORY:"
    free -h | grep -E "^(Mem|Swap):"
    echo ""
    
    # Processes
    echo "PROCESSES:"
    echo "Total: $(ps aux | wc -l)"
    echo "Python: $(pgrep -c python)"
    echo "Pytest: $(pgrep -c pytest)"
    echo "Git: $(pgrep -c git)"
    echo ""
    
    # Top consumers
    echo "TOP MEMORY CONSUMERS:"
    ps aux --sort=-%mem | head -5
    
    sleep 2
done
```

### Implementation Checklist

- [x] Create `sequential-executor.sh` for TRUE sequential execution
- [x] Update `safe-run.sh` to delegate to sequential executor  
- [x] Add `pytest.ini` with resource limits
- [x] Create `monitor-queue.sh` for queue visualization
- [x] Add `.env.development` with limits
- [x] Update Makefile with safe commands
- [x] Create `SAFE_EXECUTION_GUIDE.md` documentation
- [ ] Update pre-commit wrapper to use sequential executor
- [ ] Update all CI/CD workflows
- [ ] Add orphan cleanup to cron
- [ ] Train team on new procedures

### Incident Prevention Matrix

| Risk | Mitigation | Monitoring | Response |
|------|------------|------------|----------|
| Parallel pytest | pytest.ini limits | Process count | Kill extras |
| Memory explosion | ulimit controls | Memory monitor | Kill high-mem |
| Git hook cascade | Exclusive locks | Lock monitoring | Queue waits |
| Zombie processes | Process groups | Stall detection | Group kill |
| Resource leaks | GC settings | Growth trends | Force GC |

### Lessons Learned

1. **Trust No Defaults**: Every tool must be explicitly configured for resource limits
2. **Defense in Depth**: Multiple layers of protection are essential
3. **Fail Fast**: Better to reject operations than exhaust resources
4. **Monitor Everything**: Can't manage what you don't measure
5. **Automate Safety**: Human discipline alone is insufficient

### Emergency Response

If process explosion occurs again:

1. **Immediate**: 
   ```bash
   killall -9 pytest python git
   ```

2. **Cleanup**:
   ```bash
   rm -f /tmp/*lock /tmp/*pipe
   pkill -f pre-commit
   ```

3. **Recovery**:
   ```bash
   git reset --hard HEAD
   git clean -fd
   ```

4. **Investigation**:
   ```bash
   dmesg | grep -i "out of memory"
   journalctl -u system --since "1 hour ago"
   ```

### Conclusion

This redesign implements a comprehensive defense-in-depth strategy against process explosions. By combining technical controls, monitoring, and procedural changes, we can prevent future incidents while maintaining developer productivity.

The key is to make the safe path the easy path - tools should default to resource-conscious behavior, and unsafe operations should require explicit override.