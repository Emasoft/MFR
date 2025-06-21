#!/usr/bin/env bash
# Script to set up GitHub repository configuration using GitHub CLI

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up GitHub repository configuration...${NC}"

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI (gh) is not installed!${NC}"
    echo -e "${YELLOW}Install with: brew install gh${NC}"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${YELLOW}GitHub CLI not authenticated. Running 'gh auth login'...${NC}"
    gh auth login
fi

# Get repository information
REPO_OWNER=$(gh repo view --json owner -q .owner.login 2>/dev/null || echo "")
REPO_NAME=$(gh repo view --json name -q .name 2>/dev/null || echo "")

if [ -z "$REPO_OWNER" ] || [ -z "$REPO_NAME" ]; then
    echo -e "${RED}❌ Could not determine repository information.${NC}"
    echo -e "${YELLOW}Make sure you're in a Git repository with a GitHub remote.${NC}"
    exit 1
fi

echo -e "${GREEN}Repository: ${REPO_OWNER}/${REPO_NAME}${NC}"

# Configure Git locally
echo -e "\n${BLUE}Configuring Git...${NC}"
git config --local user.name "Emasoft"
git config --local user.email "713559+Emasoft@users.noreply.github.com"
echo -e "${GREEN}✅ Git configuration set${NC}"

# Set up branch protection for main branch
echo -e "\n${BLUE}Setting up branch protection...${NC}"
if gh api repos/${REPO_OWNER}/${REPO_NAME}/branches/main/protection \
    --method PUT \
    --field required_status_checks='{"strict":true,"contexts":["test","security","pre-commit"]}' \
    --field enforce_admins=false \
    --field required_pull_request_reviews='{"dismiss_stale_reviews":true,"require_code_owner_reviews":false,"required_approving_review_count":1}' \
    --field restrictions=null \
    --field allow_force_pushes=false \
    --field allow_deletions=false \
    --silent; then
    echo -e "${GREEN}✅ Branch protection configured for main${NC}"
else
    echo -e "${YELLOW}⚠️  Could not set branch protection (may require admin permissions)${NC}"
fi

# Add repository secrets (if needed)
echo -e "\n${BLUE}Checking repository secrets...${NC}"
if ! gh secret list | grep -q CODECOV_TOKEN; then
    echo -e "${YELLOW}CODECOV_TOKEN not found. You may want to add it for coverage reports.${NC}"
    echo -e "${YELLOW}Visit https://codecov.io to get your token, then run:${NC}"
    echo -e "${YELLOW}gh secret set CODECOV_TOKEN${NC}"
fi

# Enable GitHub Actions if not already enabled
echo -e "\n${BLUE}Enabling GitHub Actions...${NC}"
if gh api repos/${REPO_OWNER}/${REPO_NAME}/actions/permissions \
    --method PUT \
    --field enabled=true \
    --field allowed_actions=all \
    --silent; then
    echo -e "${GREEN}✅ GitHub Actions enabled${NC}"
else
    echo -e "${YELLOW}⚠️  Could not enable GitHub Actions (may already be enabled)${NC}"
fi

# Set up GitHub Pages (optional)
echo -e "\n${BLUE}Setting up GitHub Pages for documentation...${NC}"
if gh api repos/${REPO_OWNER}/${REPO_NAME}/pages \
    --method POST \
    --field source='{"branch":"main","path":"/docs"}' \
    --silent 2>/dev/null; then
    echo -e "${GREEN}✅ GitHub Pages configured${NC}"
else
    echo -e "${YELLOW}⚠️  GitHub Pages may already be configured or not available${NC}"
fi

# Create common labels for issues
echo -e "\n${BLUE}Creating issue labels...${NC}"
labels=(
    "bug:d73a4a:Something isn't working"
    "enhancement:a2eeef:New feature or request"
    "documentation:0075ca:Improvements or additions to documentation"
    "security:ee0701:Security vulnerability or concern"
    "dependencies:0366d6:Pull requests that update a dependency file"
    "ci/cd:000000:Continuous Integration/Deployment"
)

for label in "${labels[@]}"; do
    IFS=':' read -r name color description <<< "$label"
    if gh label create "$name" --color "$color" --description "$description" --force &>/dev/null; then
        echo -e "${GREEN}✅ Created label: $name${NC}"
    fi
done

# Create .github/CODEOWNERS file
echo -e "\n${BLUE}Creating CODEOWNERS file...${NC}"
mkdir -p .github
echo "# Code owners for automatic review requests
# These owners will be requested for review when someone opens a pull request

* @Emasoft
*.py @Emasoft
*.yml @Emasoft
*.yaml @Emasoft
.github/ @Emasoft
" > .github/CODEOWNERS

if [ -f .github/CODEOWNERS ]; then
    echo -e "${GREEN}✅ CODEOWNERS file created${NC}"
fi

# Summary
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}GitHub repository setup complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\nRepository: ${BLUE}https://github.com/${REPO_OWNER}/${REPO_NAME}${NC}"
echo -e "\nNext steps:"
echo -e "1. ${YELLOW}Add CODECOV_TOKEN secret if using Codecov${NC}"
echo -e "2. ${YELLOW}Review and adjust branch protection rules as needed${NC}"
echo -e "3. ${YELLOW}Commit and push the CODEOWNERS file${NC}"
echo -e "\nGit configuration:"
echo -e "  User: ${BLUE}Emasoft${NC}"
echo -e "  Email: ${BLUE}713559+Emasoft@users.noreply.github.com${NC}"
