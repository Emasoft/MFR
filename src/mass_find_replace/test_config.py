#!/usr/bin/env python3

# HERE IS THE CHANGELOG FOR THIS VERSION OF THE FILE:
# - Initial implementation of test configuration module
# - Handles local vs remote/CI environment detection
# - Provides profile-specific settings for tests
#

"""Test configuration module for environment-aware testing."""

import os
from typing import Any


class TestConfig:
    """Configuration for tests based on environment profile."""

    @staticmethod
    def is_ci_environment() -> bool:
        """Check if running in CI/remote environment."""
        return os.environ.get("CI", "").lower() == "true" or os.environ.get("GITHUB_ACTIONS", "").lower() == "true" or os.environ.get("TEST_PROFILE", "").lower() == "remote"

    @staticmethod
    def get_profile() -> str:
        """Get current test profile."""
        if TestConfig.is_ci_environment():
            return "remote"
        return os.environ.get("TEST_PROFILE", "local").lower()

    @staticmethod
    def get_max_retries() -> int:
        """Get maximum retry count for current profile."""
        if TestConfig.is_ci_environment():
            return int(os.environ.get("REMOTE_MAX_RETRIES", "2"))
        return int(os.environ.get("LOCAL_MAX_RETRIES", "10"))

    @staticmethod
    def get_timeout_seconds() -> int:
        """Get timeout in seconds for current profile."""
        if TestConfig.is_ci_environment():
            return int(os.environ.get("REMOTE_TIMEOUT_SECONDS", "5"))
        return int(os.environ.get("LOCAL_TIMEOUT_SECONDS", "60"))

    @staticmethod
    def get_api_endpoint() -> str:
        """Get API endpoint for current profile."""
        if TestConfig.is_ci_environment():
            return os.environ.get("REMOTE_API_ENDPOINT", "https://api.example.com")
        return os.environ.get("LOCAL_API_ENDPOINT", "http://localhost:8080")

    @staticmethod
    def should_enable_coverage() -> bool:
        """Check if coverage should be enabled."""
        if TestConfig.is_ci_environment():
            return os.environ.get("REMOTE_ENABLE_COVERAGE", "false").lower() == "true"
        return os.environ.get("LOCAL_ENABLE_COVERAGE", "true").lower() == "true"

    @staticmethod
    def should_enable_verbose_logging() -> bool:
        """Check if verbose logging should be enabled."""
        if TestConfig.is_ci_environment():
            return os.environ.get("REMOTE_VERBOSE_LOGGING", "false").lower() == "true"
        return os.environ.get("LOCAL_VERBOSE_LOGGING", "true").lower() == "true"

    @staticmethod
    def get_config() -> dict[str, Any]:
        """Get full configuration for current profile."""
        return {
            "profile": TestConfig.get_profile(),
            "is_ci": TestConfig.is_ci_environment(),
            "max_retries": TestConfig.get_max_retries(),
            "timeout_seconds": TestConfig.get_timeout_seconds(),
            "api_endpoint": TestConfig.get_api_endpoint(),
            "enable_coverage": TestConfig.should_enable_coverage(),
            "verbose_logging": TestConfig.should_enable_verbose_logging(),
        }


# Convenience instance
test_config = TestConfig()
