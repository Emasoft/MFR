# Universal Python development container with sequential execution
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    procps \
    lsof \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv globally
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    mv /root/.local/bin/uv /usr/local/bin/

# Set sequential execution environment
ENV PRE_COMMIT_MAX_WORKERS=1 \
    PRE_COMMIT_NO_CONCURRENCY=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1 \
    MEMORY_LIMIT_MB=2048 \
    TIMEOUT_SECONDS=600 \
    DOCKER_CONTAINER=1

# Create non-root user for security
RUN useradd -m -s /bin/bash developer && \
    mkdir -p /workspace && \
    chown -R developer:developer /workspace

USER developer
WORKDIR /workspace

# Copy project files (if building with context)
COPY --chown=developer:developer . /workspace/

# Run setup if script exists
RUN if [ -f "setup-sequential-precommit.sh" ]; then \
        chmod +x setup-sequential-precommit.sh && \
        ./setup-sequential-precommit.sh; \
    fi

# Default command
CMD ["/bin/bash"]
