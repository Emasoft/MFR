# Universal Python development container with sequential execution
# Version: 1.0.0
FROM python:3.11-slim

# Build arguments
ARG UV_VERSION="0.5.14"
ARG TRUFFLEHOG_VERSION="latest"

# Install system dependencies with specific versions where possible
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    procps \
    lsof \
    build-essential \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install uv globally with version pinning
RUN mkdir -p /tmp/uv-install && \
    cd /tmp/uv-install && \
    curl -LsSf https://astral.sh/uv/${UV_VERSION}/install.sh -o install.sh && \
    sh install.sh && \
    if [ -f /root/.local/bin/uv ]; then \
        mv /root/.local/bin/uv /usr/local/bin/; \
    elif [ -f /root/.cargo/bin/uv ]; then \
        mv /root/.cargo/bin/uv /usr/local/bin/; \
    fi && \
    cd / && \
    rm -rf /tmp/uv-install && \
    uv --version

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

# Copy only necessary files first (for better caching)
COPY --chown=developer:developer setup-sequential-precommit.sh* /workspace/
COPY --chown=developer:developer .sequential-precommit-env* /workspace/
COPY --chown=developer:developer pyproject.toml* /workspace/
COPY --chown=developer:developer requirements*.txt* /workspace/

# Make scripts executable
RUN find /workspace -name "*.sh" -type f -exec chmod +x {} \;

# Don't run setup during build - it should run at runtime
# This allows the image to be more generic

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python3 -c "print('Container is healthy')" || exit 1

# Default command
CMD ["/bin/bash"]
