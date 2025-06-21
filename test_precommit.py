#!/usr/bin/env python3

# Test file to verify pre-commit hooks
# This file has intentional issues to test the hooks


def test_function(x, y):  # Missing type annotations
    """Test function with issues."""
    result = x + y
    return result


class TestClass:
    """Test class."""

    def method(self):
        pass


# Trailing whitespace on next line
print("test")
