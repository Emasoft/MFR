# Security Setup Documentation

This document describes the security configuration for the MFR project.

## Git Configuration

All commits and pushes are configured with the following user information:
- **Name**: Emasoft
- **Email**: 713559+Emasoft@users.noreply.github.com

This is enforced through:
1. Local git configuration (`.git/config`)
2. GitHub Actions environment variables

## Pre-commit Hooks

Security-related hooks that run before every commit:
- **detect-private-key**: Check for private keys
- **deptry**: Check for dependency issues

## Security Tools Installed

All security tools are included in the dev dependencies:
- **pip-audit**: Vulnerability scanning for Python packages
- **bandit**: Security linter for Python code
- **safety**: Check for known security vulnerabilities
- **deptry**: Dependency analysis (unused, missing, transitive)

## GitHub Actions Security Workflow

The `security.yml` workflow runs on every push and pull request:

### Jobs:
1. **Dependency Security Check**:
   - Runs `deptry` for dependency analysis
   - Runs `pip-audit` for vulnerability scanning
2. **Code Quality and Security**:
   - Runs `bandit` for Python security issues
   - Runs `safety` for known security vulnerabilities

## GitHub Repository Setup

Use the `scripts/setup-github.sh` script to configure the GitHub repository:
- Sets branch protection rules
- Enables required status checks
- Creates issue labels
- Sets up CODEOWNERS file
- Configures GitHub Actions permissions

## Usage

### Run Security Checks Locally
```bash
# Check for vulnerable dependencies
uv run pip-audit

# Run security linter
uv run bandit -r src

# Check with safety
uv run safety check
```

### Setup GitHub Repository
```bash
# Authenticate with GitHub CLI
gh auth login

# Run setup script
./scripts/setup-github.sh
```

## Important Notes

1. All commits will have the configured Git user information
2. Security checks run at multiple stages:
   - Pre-commit (via pre-commit framework)
   - GitHub Actions (on push/PR)
