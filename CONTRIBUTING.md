# Contributing to MFR

First off, thank you for considering contributing to MFR! It's people like you that make MFR such a great tool.

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected
to uphold this code.

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues as you might find out that you don't need to create one.
When you are creating a bug report, please include as many details as possible:

- **Use a clear and descriptive title**
- **Describe the exact steps to reproduce the problem**
- **Provide specific examples to demonstrate the steps**
- **Describe the behavior you observed after following the steps**
- **Explain which behavior you expected to see instead and why**
- **Include details about your configuration and environment**

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, please include:

- **Use a clear and descriptive title**
- **Provide a step-by-step description of the suggested enhancement**
- **Provide specific examples to demonstrate the steps**
- **Describe the current behavior and explain which behavior you expected to see instead**
- **Explain why this enhancement would be useful**

### Pull Requests

1. Fork the repo and create your branch from `main`
2. If you've added code that should be tested, add tests
3. If you've changed APIs, update the documentation
4. Ensure the test suite passes
5. Make sure your code lints
6. Issue that pull request!

## Development Process

1. **Setup Development Environment**

   ```bash
   git clone https://github.com/YOUR_USERNAME/MFR.git
   cd MFR
   uv sync --all-extras
   uv run pre-commit install
   uv run pre-commit install --hook-type pre-push
   ```

2. **Make Your Changes**

   - Write tests first (TDD)
   - Keep changes focused and atomic
   - Follow the existing code style

3. **Test Your Changes**

   ```bash
   uv run pytest
   uv run pre-commit run --all-files
   ```

4. **Commit Your Changes**
   - Use conventional commit messages
   - Keep commits focused and atomic

## Style Guidelines

### Python Style

- Follow PEP 8
- Use type hints for all functions
- Write Google-style docstrings for all public functions
- Keep functions under 50 lines
- Use descriptive variable names
- Requires Python 3.10, 3.11, or 3.12

### Commit Messages

- Use the present tense ("Add feature" not "Added feature")
- Use the imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit the first line to 72 characters or less
- Reference issues and pull requests liberally after the first line

### Documentation Style

- Use Markdown
- Reference functions with backticks
- Include code examples where relevant
- Keep language clear and concise

## Additional Notes

### Issue and Pull Request Labels

- `bug` - Something isn't working
- `enhancement` - New feature or request
- `documentation` - Improvements or additions to documentation
- `good first issue` - Good for newcomers
- `help wanted` - Extra attention is needed

Thank you for contributing to MFR!
