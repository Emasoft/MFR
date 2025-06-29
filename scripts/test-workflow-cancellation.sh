#!/usr/bin/env bash
# Test GitHub workflow cancellation functionality

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}GitHub Workflow Cancellation Test${NC}"
echo "===================================="
echo ""

# Check if gh CLI is available
if ! command -v gh &> /dev/null; then
    echo -e "${RED}Error: GitHub CLI (gh) is not installed${NC}"
    echo "Please install it: https://cli.github.com/"
    exit 1
fi

# Check if we're in a git repository
if ! git rev-parse --is-inside-work-tree &> /dev/null; then
    echo -e "${RED}Error: Not in a git repository${NC}"
    exit 1
fi

# Function to cancel a workflow run
cancel_workflow() {
    local run_id=$1
    echo -e "${YELLOW}Attempting to cancel workflow run ID: $run_id${NC}"

    if gh run cancel "$run_id" 2>/dev/null; then
        echo -e "${GREEN}✓ Successfully cancelled workflow run $run_id${NC}"
        return 0
    else
        echo -e "${RED}✗ Failed to cancel workflow run $run_id${NC}"
        return 1
    fi
}

# Function to check workflow status
check_workflow_status() {
    local run_id=$1
    gh run view "$run_id" --json status,conclusion 2>/dev/null | jq -r '.status + " (" + (.conclusion // "in progress") + ")"'
}

# List recent workflow runs
echo -e "${GREEN}Recent workflow runs:${NC}"
echo ""

# Get last 5 workflow runs
gh run list --limit 5 --json databaseId,workflowName,status,conclusion,createdAt | \
    jq -r '.[] | "\(.databaseId) | \(.workflowName) | \(.status) | \(.conclusion // "in progress") | \(.createdAt)"' | \
    column -t -s '|'

echo ""
echo -e "${YELLOW}Testing cancellation capability...${NC}"
echo ""

# Check if any workflows are currently running or queued
RUNNING_WORKFLOWS=$(gh run list --limit 20 --json databaseId,status | \
    jq -r '.[] | select(.status == "in_progress" or .status == "queued") | .databaseId')

if [ -z "$RUNNING_WORKFLOWS" ]; then
    echo -e "${YELLOW}No workflows are currently running or queued${NC}"
    echo ""
    echo "To test cancellation:"
    echo "1. Push a commit to trigger workflows"
    echo "2. Quickly run this script again while workflows are queued/running"
    echo "3. Or use: gh run cancel <RUN_ID>"
else
    echo -e "${GREEN}Found running/queued workflows:${NC}"
    for run_id in $RUNNING_WORKFLOWS; do
        echo -n "  Run ID $run_id: "
        check_workflow_status "$run_id"
    done

    echo ""
    read -p "Do you want to cancel these workflows? (y/N) " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for run_id in $RUNNING_WORKFLOWS; do
            cancel_workflow "$run_id"
            sleep 1
            echo -n "  New status: "
            check_workflow_status "$run_id"
        done
    fi
fi

echo ""
echo -e "${GREEN}Workflow concurrency configuration summary:${NC}"
echo ""

# Check which workflows have concurrency configuration
for workflow in .github/workflows/*.yml; do
    workflow_name=$(basename "$workflow")
    if grep -q "concurrency:" "$workflow"; then
        cancel_setting=$(grep -A2 "concurrency:" "$workflow" | grep "cancel-in-progress:" | awk '{print $2}')
        echo -e "  ${GREEN}✓${NC} $workflow_name - cancel-in-progress: ${cancel_setting:-not set}"
    else
        echo -e "  ${RED}✗${NC} $workflow_name - NO concurrency configuration"
    fi
done

echo ""
echo -e "${GREEN}Done!${NC}"
