#!/usr/bin/env bash
#
# Copyright (c) 2024 Emasoft
#
# This software is licensed under the MIT License.
# Refer to the LICENSE file for more details.
#
# Test GitHub workflows locally with act and Docker

set -e

echo "🐳 Testing GitHub workflows with act and Docker"
echo "=============================================="

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Check prerequisites
check_prerequisites() {
    echo "Checking prerequisites..."

    # Check Docker
    if ! docker info &> /dev/null; then
        echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
        exit 1
    else
        echo -e "${GREEN}✅ Docker is running${NC}"
    fi

    # Check act
    if ! command -v act &> /dev/null; then
        echo -e "${RED}❌ act is not installed. Install with: brew install act${NC}"
        exit 1
    else
        echo -e "${GREEN}✅ act is installed ($(act --version))${NC}"
    fi
}

# Test specific workflow
test_workflow() {
    local workflow=$1
    local job=$2
    local event=${3:-push}

    echo -e "\n${YELLOW}Testing workflow: $workflow${NC}"
    echo "Job: ${job:-all}"
    echo "Event: $event"

    # Create act command
    local cmd="act $event -W .github/workflows/$workflow"
    if [ -n "$job" ]; then
        cmd="$cmd -j $job"
    fi

    # Add common flags
    cmd="$cmd --container-architecture linux/amd64"

    # Run with timeout
    echo -e "\nRunning: $cmd"
    if timeout 300 $cmd; then
        echo -e "${GREEN}✅ Workflow test passed!${NC}"
        return 0
    else
        echo -e "${RED}❌ Workflow test failed!${NC}"
        return 1
    fi
}

# Test pre-commit locally
test_precommit_local() {
    echo -e "\n${YELLOW}Testing pre-commit locally${NC}"

    if uv run pre-commit run --all-files; then
        echo -e "${GREEN}✅ Pre-commit checks passed!${NC}"
    else
        echo -e "${RED}❌ Pre-commit checks failed!${NC}"
        return 1
    fi
}

# Main menu
main() {
    check_prerequisites

    echo -e "\n${YELLOW}What would you like to test?${NC}"
    echo "1. Pre-commit checks (local)"
    echo "2. Pre-commit workflow (act)"
    echo "3. Test suite (act)"
    echo "4. Security scan (act)"
    echo "5. Build workflow (act)"
    echo "6. All workflows"
    echo ""
    read -p "Enter your choice (1-6): " choice

    case $choice in
        1)
            test_precommit_local
            ;;
        2)
            test_workflow "pre-commit.yml" "pre-commit" "push"
            ;;
        3)
            test_workflow "ci.yml" "test" "push"
            ;;
        4)
            test_workflow "security-scan.yml" "gitleaks" "workflow_dispatch"
            ;;
        5)
            test_workflow "ci.yml" "build" "push"
            ;;
        6)
            echo "Running all tests..."
            test_precommit_local
            test_workflow "pre-commit.yml" "pre-commit" "push"
            test_workflow "ci.yml" "test" "push"
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
