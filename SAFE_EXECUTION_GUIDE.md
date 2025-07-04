# Safe Execution Guide - TRUE SEQUENTIAL EXECUTION

## ⚠️ CRITICAL: Only ONE Process at a Time

This project now enforces **TRUE SEQUENTIAL EXECUTION**:
- Only ONE operation can run at any time
- All commands wait INDEFINITELY for their turn
- Orphan processes are automatically detected and killed
- **YOU MUST FOLLOW THESE GUIDELINES**

## 🚨 What NOT to Do

**NEVER run these commands:**
```bash
# ❌ DANGEROUS - Parallel execution
pytest & pytest & pytest &

# ❌ DANGEROUS - No resource limits  
uv run pytest tests/

# ❌ DANGEROUS - Multiple git operations
git commit & git commit &

# ❌ DANGEROUS - Uncontrolled parallelism
pytest -n auto
```

## ✅ Safe Execution Patterns

### 1. Always Use the Makefile
```bash
# ✅ SAFE - Resource limited
make test

# ✅ SAFE - Sequential execution  
make test-file FILE=tests/test_foo.py

# ✅ SAFE - Controlled linting
make lint
```

### 2. Or Use safe-run.sh Wrapper
```bash
# ✅ SAFE - Monitored execution
./scripts/safe-run.sh uv run pytest tests/test_one.py

# ✅ SAFE - Resource limits enforced
./scripts/safe-run.sh uv run mypy src/
```

### 3. Set Environment First
```bash
# ✅ SAFE - Load resource limits
source .env.development
uv run pytest  # Now limited by environment
```

## 🔍 Monitor Execution Queue

**NEW**: See what's running and what's waiting:
```bash
# Start the queue monitor
make monitor

# Shows:
# - Current executing process
# - Queue of waiting processes  
# - Orphan processes detected
# - System resources
```

## 🛠️ Quick Reference

| Task | Safe Command | Unsafe Command |
|------|--------------|----------------|
| Run all tests | `make test` | `pytest` |
| Run one test | `make test-file FILE=...` | `pytest file &` |
| Format code | `make format` | `ruff format & black &` |
| Lint code | `make lint` | `ruff check & mypy &` |
| Install deps | `make install` | `uv sync &` |
| Commit code | `make safe-commit` then `git commit` | `git commit & git commit` |
| Monitor queue | `make monitor` | N/A |

## 🚑 Emergency Commands

If processes get out of control:

```bash
# Kill everything
make kill-all

# Monitor resources
make monitor

# Check what's running
make check-env
```

## 📊 Resource Limits

The following limits are enforced:

- **Memory**: 8GB max per operation
- **Processes**: 50 max subprocesses  
- **Timeout**: 30 minutes max runtime
- **Parallelism**: Sequential execution only

## 🔍 Pre-flight Checklist

Before running ANY command:

1. Check system resources: `make check-env`
2. Ensure no other operations running: `ps aux | grep python`
3. Use the safe wrappers: `make` or `./scripts/safe-run.sh`
4. Monitor if unsure: `make monitor` (in another terminal)

## 📝 For CI/CD

GitHub Actions are already configured with resource limits. No changes needed.

## 🎓 Why This Matters

- Running tests in parallel can spawn 100+ processes
- Each process can consume 1-2GB of memory  
- Git hooks can cascade and create more processes
- System can exhaust 64GB RAM in minutes

**Prevention is the only cure. There is no recovery from a memory-exhausted system.**

## 📚 Further Reading

- [PIPELINE_SAFETY_REDESIGN.md](./PIPELINE_SAFETY_REDESIGN.md) - Full technical details
- [pytest.ini](./pytest.ini) - Test execution limits
- [.env.development](./.env.development) - Environment configuration