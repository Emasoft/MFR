# GitHub Workflows Concurrency Fix

## Problem
GitHub workflows are not interruptible/cancellable because they lack `concurrency` configuration. This causes:
- Wasted CI resources when multiple pushes happen quickly
- Unable to cancel stuck or queued jobs
- Longer wait times for CI feedback

## Solution
Add `concurrency` configuration to all workflows with:
1. Smart grouping to prevent conflicts
2. `cancel-in-progress` for PR workflows (save resources)
3. Queue production/release workflows (never cancel important deployments)

## Implementation Pattern

### For CI/Test Workflows (Cancel Previous Runs on PRs)
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: ${{ startsWith(github.ref, 'refs/pull/') }}
```

### For Production/Release Workflows (Never Cancel)
```yaml
concurrency:
  group: ${{ github.workflow }}-production
  cancel-in-progress: false
```

### For Branch-Specific Workflows
```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

## Files to Update
1. `.github/workflows/ci.yml` - Main CI pipeline
2. `.github/workflows/pre-commit.yml` - Pre-commit checks
3. `.github/workflows/lint.yml` - Linting workflow
4. `.github/workflows/security.yml` - Security checks
5. `.github/workflows/release.yml` - Release workflow (never cancel)
6. `.github/workflows/pr-checks.yml` - PR specific checks
7. `.github/workflows/prfix.yml` - PR fix workflow
8. `.github/workflows/nightly.yml` - Nightly builds
9. `.github/workflows/security-scan.yml` - Security scanning
10. `.github/workflows/uv-lock-check.yml` - Dependency lock check

## Key Benefits
- **Resource Efficiency**: Cancel outdated PR checks when new commits are pushed
- **Faster Feedback**: New commits don't wait for old checks to complete
- **Control**: Can manually cancel stuck workflows
- **Safety**: Production deployments never get cancelled
