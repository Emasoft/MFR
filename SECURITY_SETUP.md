# Security Setup Documentation

This document describes the security configuration for the MFR project.

## Git Configuration

All commits and pushes are configured with the following user information:
- **Name**: Emasoft
- **Email**: 713559+Emasoft@users.noreply.github.com

This is enforced through:
1. Local git configuration (`.git/config`)
2. Pre-push hook environment variables
3. GitHub Actions environment variables

## Gitleaks Configuration

### Pre-commit Hook
Gitleaks runs automatically before every commit through the pre-commit framework.

### Pre-push Hook
A custom pre-push hook (`/.git/hooks/pre-push`) prevents pushing secrets to GitHub:
- Runs Gitleaks with the project's custom configuration
- Blocks the push if any secrets are detected
- Sets proper Git author/committer environment variables

### Configuration (`.gitleaks.toml`)
The configuration:
- Extends the default Gitleaks rules
- Allows only specific patterns:
  - Emasoft user information
  - Example/placeholder secrets in documentation
  - Localhost URLs
- Adds custom rules for detecting:
  - Generic API keys
  - Passwords and secrets
  - Private keys (RSA, DSA, EC, OpenSSH, PGP)
  - GitHub personal access tokens
  - AWS access keys

## GitHub Actions Security Workflow

The `security.yml` workflow runs on every push and pull request:

### Jobs:
1. **Gitleaks Secret Scan**: Scans entire repository history for secrets
2. **Dependency Security Check**:
   - Runs `deptry` for dependency analysis
   - Runs `pip-audit` for vulnerability scanning
3. **Code Quality and Security**:
   - Runs `bandit` for Python security issues
   - Runs `safety` for known security vulnerabilities

## Pre-commit Hooks

Security-related hooks that run before every commit:
- **gitleaks**: Scan for secrets
- **deptry**: Check for dependency issues
- **detect-private-key**: Additional check for private keys

## Security Tools Installed

All security tools are included in the dev dependencies:
- **gitleaks**: Secret scanning (via pre-commit and hooks)
- **pip-audit**: Vulnerability scanning for Python packages
- **bandit**: Security linter for Python code
- **safety**: Check for known security vulnerabilities
- **deptry**: Dependency analysis (unused, missing, transitive)

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
# Check for secrets
gitleaks detect --source . --config .gitleaks.toml

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

1. The pre-push hook requires Gitleaks to be installed system-wide:
   ```bash
   brew install gitleaks
   ```

2. All commits will have the configured Git user information
3. Secrets detection runs at multiple stages:
   - Pre-commit (via pre-commit framework)
   - Pre-push (via Git hook)
   - GitHub Actions (on push/PR)

4. The only allowed "secret-like" patterns are:
   - Emasoft user information
   - Documentation examples
   - Development URLs (localhost)
