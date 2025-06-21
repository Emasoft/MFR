#!/bin/bash
# Script to test GitHub workflows locally using act

set -e

echo "🚀 Testing GitHub workflows locally with act"
echo "==========================================="

# Check if act is installed
if ! command -v act &> /dev/null; then
    echo "❌ act is not installed. Please install it with: brew install act"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

# Function to run a specific workflow
run_workflow() {
    local workflow=$1
    local job=$2
    local event=${3:-push}

    echo ""
    echo "🔧 Running workflow: $workflow"
    echo "   Job: ${job:-all jobs}"
    echo "   Event: $event"
    echo ""

    if [ -n "$job" ]; then
        act $event -W .github/workflows/$workflow -j $job
    else
        act $event -W .github/workflows/$workflow
    fi
}

# Menu
echo "Which workflow would you like to test?"
echo "1. Pre-commit checks"
echo "2. CI/CD Pipeline (tests)"
echo "3. Security scan"
echo "4. All workflows"
echo ""
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        run_workflow "pre-commit.yml" "pre-commit" "push"
        ;;
    2)
        echo "Select a job to run:"
        echo "a. Test suite"
        echo "b. Security scan"
        echo "c. Build distribution"
        read -p "Enter your choice (a-c): " job_choice

        case $job_choice in
            a) run_workflow "ci.yml" "test" "push" ;;
            b) run_workflow "ci.yml" "security" "push" ;;
            c) run_workflow "ci.yml" "build" "push" ;;
            *) echo "Invalid choice" ;;
        esac
        ;;
    3)
        run_workflow "security-scan.yml" "" "workflow_dispatch"
        ;;
    4)
        echo "Running all workflows..."
        run_workflow "pre-commit.yml" "pre-commit" "push"
        run_workflow "ci.yml" "test" "push"
        run_workflow "security-scan.yml" "" "workflow_dispatch"
        ;;
    *)
        echo "Invalid choice"
        exit 1
        ;;
esac

echo ""
echo "✅ Workflow testing complete!"
