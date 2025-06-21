# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in Mass Find Replace (MFR), please report it responsibly:

1. **DO NOT** open a public issue
2. Email security concerns to: 713559+Emasoft@users.noreply.github.com
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Security Measures

### Secret Scanning

This project uses [Gitleaks](https://github.com/gitleaks/gitleaks) to prevent secrets from being committed:

- **Pre-commit hook**: Scans staged files before commit
- **Pre-push hook**: Scans all commits before pushing
- **CI/CD scanning**: Automated scanning on every PR and push
- **Daily scans**: Scheduled security scans of the entire repository

### Configuration

See `.gitleaks.toml` for the complete security configuration. Key features:

- Blocks common secret patterns (API keys, tokens, passwords)
- Allows only approved email addresses
- Excludes test files and documentation from certain checks
- Prevents private keys and certificates from being committed

### Local Setup

To enable Git hooks locally:

```bash
git config core.hooksPath .githooks
```

This is already configured if you cloned the repository normally.

### Manual Scanning

To manually scan for secrets:

```bash
# Scan entire repository
gitleaks detect --source . --config .gitleaks.toml

# Scan staged changes only
gitleaks protect --staged --config .gitleaks.toml

# Scan specific commit range
gitleaks detect --source . --config .gitleaks.toml --log-opts="HEAD~10..HEAD"
```

## Dependencies

We regularly scan dependencies for known vulnerabilities using:

- **Safety**: Python dependency vulnerability scanner
- **pip-audit**: Audits Python packages for known vulnerabilities
- **Dependabot**: Automated dependency updates (if enabled)

## Best Practices

1. Never commit sensitive information (passwords, API keys, tokens)
2. Use environment variables for secrets
3. Review `.gitleaks.toml` before adding new secret patterns
4. Run security scans before pushing changes
5. Keep dependencies up to date

## Security Contact

For security-related questions or concerns:
- Email: 713559+Emasoft@users.noreply.github.com
- GitHub: [@Emasoft](https://github.com/Emasoft)
