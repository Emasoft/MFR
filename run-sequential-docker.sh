#!/usr/bin/env bash
# Run sequential pre-commit in Docker with auto-cleanup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$SCRIPT_DIR}"
PROJECT_NAME=$(basename "$PROJECT_ROOT" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]-')

cd "$PROJECT_ROOT"

# Source environment if exists
[ -f ".sequential-precommit-env" ] && source .sequential-precommit-env

# Docker run options
DOCKER_OPTS=(
    --rm  # Auto-remove container after exit
    -it   # Interactive terminal
    --name "sequential-precommit-${PROJECT_NAME}-$$"
    --memory "${DOCKER_MEMORY_LIMIT:-4g}"
    --cpus "${DOCKER_CPU_LIMIT:-2}"
    -v "$PROJECT_ROOT:/workspace"
    -v "/workspace/.venv"  # Anonymous volume for venv
    -e "PROJECT_ROOT=/workspace"
    -e "PRE_COMMIT_MAX_WORKERS=1"
    -e "MEMORY_LIMIT_MB=${MEMORY_LIMIT_MB:-2048}"
    -w "/workspace"
)

# Build image if needed
if ! docker images | grep -q "sequential-precommit"; then
    echo "Building Docker image..."
    docker build -t sequential-precommit:latest -f docker/sequential-precommit/Dockerfile .
fi

# Function to cleanup on exit
cleanup() {
    echo "Cleaning up Docker resources..."
    docker rm -f "sequential-precommit-${PROJECT_NAME}-$$" 2>/dev/null || true
}
trap cleanup EXIT

# Run command in Docker
echo "Running in Docker container (auto-cleanup enabled)..."
docker run "${DOCKER_OPTS[@]}" sequential-precommit:latest bash -c "
    # Setup environment if not exists
    if [ ! -f '.venv/bin/activate' ]; then
        ./setup-sequential-precommit.sh
    fi

    # Source environment
    source .venv/bin/activate
    source .sequential-precommit-env

    # Run pre-commit
    pre-commit run --all-files --show-diff-on-failure
"

echo "Docker container cleaned up successfully."
