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

This project implements security best practices to prevent secrets from being committed:

- **Pre-commit hooks**: Validate code before commit
- **CI/CD scanning**: Automated security checks on every PR and push
- **Daily scans**: Scheduled security scans of dependencies

## Dependencies

We regularly scan dependencies for known vulnerabilities using:

- **Safety**: Python dependency vulnerability scanner
- **pip-audit**: Audits Python packages for known vulnerabilities
- **Dependabot**: Automated dependency updates (if enabled)

## Best Practices

1. Never commit sensitive information (passwords, API keys, tokens)
2. Use environment variables for secrets
3. Review security configurations before making changes
4. Run security scans before pushing changes
5. Keep dependencies up to date

## Security Contact

For security-related questions or concerns:
- Email: 713559+Emasoft@users.noreply.github.com
- GitHub: [@Emasoft](https://github.com/Emasoft)
