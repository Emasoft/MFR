#!/usr/bin/env bash
#
# Run Docker-based tests for Mass Find Replace
#
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Default values
SERVICE=""
BUILD_ONLY=false
VERBOSE=false
NO_CACHE=false

# Help function
show_help() {
    echo "Usage: $0 [OPTIONS] [SERVICE]"
    echo ""
    echo "Run Docker-based tests for Mass Find Replace"
    echo ""
    echo "Services:"
    echo "  local       Run tests with local profile (default)"
    echo "  remote      Run tests with remote/CI profile"
    echo "  github      Test GitHub integration"
    echo "  lint        Run linting and code quality checks"
    echo "  security    Run security scans"
    echo "  debug       Start interactive debug container"
    echo "  all         Run all test suites"
    echo ""
    echo "Options:"
    echo "  -p, --profile PROFILE    Set test profile (local|remote) [REMOVED - not used]"
    echo "  -b, --build-only        Build images without running tests"
    echo "  -v, --verbose           Verbose output"
    echo "  -n, --no-cache          Build without cache"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                      # Run local tests"
    echo "  $0 remote               # Run CI/remote tests"
    echo "  $0 --profile remote all # Run all tests with remote profile"
    echo "  $0 github               # Test GitHub integration"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--profile)
            # Profile option kept for backward compatibility but not used
            shift 2
            ;;
        -b|--build-only)
            BUILD_ONLY=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -n|--no-cache)
            NO_CACHE=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            SERVICE="$1"
            shift
            ;;
    esac
done

# Default service
if [ -z "$SERVICE" ]; then
    SERVICE="local"
fi

# Change to project root
cd "$PROJECT_ROOT"

# Check Docker
if ! docker info &> /dev/null; then
    echo -e "${RED}❌ Docker is not running!${NC}"
    echo -e "${YELLOW}Please start Docker and try again.${NC}"
    exit 1
fi

echo -e "${BLUE}🐳 Mass Find Replace - Docker Test Runner${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Load environment file if exists
ENV_FILE="docker/test-profiles.env"
if [ -f "$ENV_FILE" ]; then
    echo -e "${CYAN}📋 Loading test profiles from $ENV_FILE${NC}"
    export "$(grep -E "^(LOCAL_|REMOTE_|PYTHON_)" "$ENV_FILE" | xargs)"
fi

# Build flags
BUILD_FLAGS=""
if [ "$NO_CACHE" = true ]; then
    BUILD_FLAGS="--no-cache"
fi

# Build the test image
echo -e "${YELLOW}🔨 Building test image...${NC}"
if [ "$VERBOSE" = true ]; then
    docker-compose -f docker-compose.test.yml build $BUILD_FLAGS test-base
else
    docker-compose -f docker-compose.test.yml build $BUILD_FLAGS test-base > /dev/null 2>&1
fi
echo -e "${GREEN}✅ Test image built successfully${NC}"

if [ "$BUILD_ONLY" = true ]; then
    echo -e "${GREEN}✅ Build complete (--build-only specified)${NC}"
    exit 0
fi

# Function to run a service
run_service() {
    local service="$1"
    local desc="$2"

    echo ""
    echo -e "${MAGENTA}▶ $desc${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if [ "$VERBOSE" = true ]; then
        docker-compose -f docker-compose.test.yml run --rm "$service"
    else
        # Run with output
        docker-compose -f docker-compose.test.yml run --rm "$service" 2>&1 | while IFS= read -r line; do
            # Color code output
            if [[ "$line" == *"PASSED"* ]] || [[ "$line" == *"passed"* ]]; then
                echo -e "${GREEN}$line${NC}"
            elif [[ "$line" == *"FAILED"* ]] || [[ "$line" == *"failed"* ]] || [[ "$line" == *"ERROR"* ]]; then
                echo -e "${RED}$line${NC}"
            elif [[ "$line" == *"SKIPPED"* ]] || [[ "$line" == *"skipped"* ]]; then
                echo -e "${YELLOW}$line${NC}"
            elif [[ "$line" == *"WARNING"* ]]; then
                echo -e "${YELLOW}$line${NC}"
            else
                echo "$line"
            fi
        done
    fi

    return ${PIPESTATUS[0]}
}

# Track overall status
OVERALL_STATUS=0

# Run requested service(s)
case "$SERVICE" in
    local)
        run_service "test-local" "Running tests with LOCAL profile" || OVERALL_STATUS=$?
        ;;
    remote)
        run_service "test-remote" "Running tests with REMOTE/CI profile" || OVERALL_STATUS=$?
        ;;
    github)
        run_service "test-github-clone" "Testing GitHub integration" || OVERALL_STATUS=$?
        ;;
    lint)
        run_service "test-lint" "Running linting and code quality checks" || OVERALL_STATUS=$?
        ;;
    security)
        run_service "test-security" "Running security scans" || OVERALL_STATUS=$?
        ;;
    debug)
        echo -e "${CYAN}🐛 Starting interactive debug container...${NC}"
        docker-compose -f docker-compose.test.yml run --rm test-debug
        ;;
    all)
        echo -e "${CYAN}🎯 Running all test suites...${NC}"

        # Run each test suite
        for suite in "test-local:Local tests" "test-lint:Linting" "test-github-clone:GitHub integration"; do
            IFS=':' read -r service desc <<< "$suite"
            if ! run_service "$service" "$desc"; then
                OVERALL_STATUS=1
            fi
        done
        ;;
    *)
        echo -e "${RED}❌ Unknown service: $SERVICE${NC}"
        echo ""
        show_help
        exit 1
        ;;
esac

# Summary
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ $OVERALL_STATUS -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
else
    echo -e "${RED}❌ Some tests failed (exit code: $OVERALL_STATUS)${NC}"
fi

# Cleanup
echo ""
echo -e "${CYAN}🧹 Cleaning up...${NC}"
docker-compose -f docker-compose.test.yml down --volumes --remove-orphans > /dev/null 2>&1

exit $OVERALL_STATUS
