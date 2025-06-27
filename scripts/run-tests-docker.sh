#!/usr/bin/env bash
#
# Run tests inside a Docker container
#
set -e

echo "🐳 Running tests in Docker container..."
echo "====================================="

# Create a temporary Dockerfile for testing
cat > Dockerfile.testing << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Enable uv to use system Python
ENV UV_SYSTEM_PYTHON=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy project files
COPY pyproject.toml uv.lock ./
COPY README.md ./
COPY src ./src
COPY tests ./tests
COPY replacement_mapping.json ./

# Install dependencies and run tests
RUN uv sync --frozen --extra dev

# Default to running all tests
CMD ["sh", "-c", "uv run python -m pytest tests/ -v"]
EOF

# Build the image
echo "Building test image..."
docker build -f Dockerfile.testing -t mfr-test-runner .

# Run the tests
echo "Running tests..."
docker run --rm mfr-test-runner "$@"

# Cleanup
rm -f Dockerfile.testing

echo "✅ Tests completed!"
