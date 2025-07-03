#!/usr/bin/env bash
# Run sequential pre-commit in Docker with auto-cleanup
# Version: 1.0.0
set -euo pipefail

# Script info
readonly SCRIPT_VERSION="1.0.0"

# Check Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed or not in PATH" >&2
    exit 1
fi

# Check Docker daemon is running
if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$SCRIPT_DIR}"
PROJECT_NAME=$(basename "$PROJECT_ROOT" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]-')

# Validate PROJECT_NAME
if [[ -z "$PROJECT_NAME" ]]; then
    PROJECT_NAME="sequential-precommit-default"
fi

cd "$PROJECT_ROOT" || exit 1

# Source environment if exists
if [[ -f ".sequential-precommit-env" ]]; then
    source .sequential-precommit-env
fi

# Container name with timestamp to avoid conflicts
CONTAINER_NAME="sequential-precommit-${PROJECT_NAME}-$$-$(date +%s)"

# Docker run options
DOCKER_OPTS=(
    --rm  # Auto-remove container after exit
    --name "$CONTAINER_NAME"
    --memory "${DOCKER_MEMORY_LIMIT:-4g}"
    --cpus "${DOCKER_CPU_LIMIT:-2}"
    -v "$PROJECT_ROOT:/workspace"
    -v "/workspace/.venv"  # Anonymous volume for venv
    -e "PROJECT_ROOT=/workspace"
    -e "PRE_COMMIT_MAX_WORKERS=1"
    -e "MEMORY_LIMIT_MB=${MEMORY_LIMIT_MB:-2048}"
    -w "/workspace"
)

# Add -it only if we have a TTY
if [[ -t 0 ]]; then
    DOCKER_OPTS+=(-it)
fi

# Check if Dockerfile exists
DOCKERFILE="docker/sequential-precommit/Dockerfile"
if [[ ! -f "$DOCKERFILE" ]]; then
    echo "Error: Dockerfile not found at $DOCKERFILE" >&2
    exit 1
fi

# Build image if needed
if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -qx "sequential-precommit:latest"; then
    echo "Building Docker image..."
    if ! docker build -t sequential-precommit:latest -f "$DOCKERFILE" .; then
        echo "Error: Failed to build Docker image" >&2
        exit 1
    fi
fi

# Function to cleanup on exit
cleanup() {
    local exit_code=$?
    echo "Cleaning up Docker resources..."
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
    # Also clean up any orphaned containers from previous runs
    docker ps -a --filter "name=sequential-precommit-${PROJECT_NAME}-" --format "{{.Names}}" |
        xargs -r docker rm -f 2>/dev/null || true
    exit $exit_code
}
trap cleanup EXIT INT TERM

# Run command in Docker
echo "Running in Docker container: $CONTAINER_NAME"
echo "Memory limit: ${DOCKER_MEMORY_LIMIT:-4g}, CPU limit: ${DOCKER_CPU_LIMIT:-2}"

if docker run "${DOCKER_OPTS[@]}" sequential-precommit:latest bash -c "
    set -euo pipefail

    # Setup environment if not exists
    if [[ ! -f '.venv/bin/activate' ]]; then
        echo 'Setting up environment...'
        if [[ -x './setup-sequential-precommit.sh' ]]; then
            ./setup-sequential-precommit.sh
        else
            echo 'Error: setup-sequential-precommit.sh not found or not executable' >&2
            exit 1
        fi
    fi

    # Source environment
    if [[ -f '.venv/bin/activate' ]]; then
        source .venv/bin/activate
    else
        echo 'Error: Virtual environment not found' >&2
        exit 1
    fi

    if [[ -f '.sequential-precommit-env' ]]; then
        source .sequential-precommit-env
    fi

    # Run pre-commit
    echo 'Running pre-commit checks...'
    pre-commit run --all-files --show-diff-on-failure
"; then
    echo "Docker execution completed successfully."
else
    echo "Docker execution failed." >&2
    exit 1
fi
