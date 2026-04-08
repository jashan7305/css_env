ARG BASE_IMAGE=python:3.10-slim
FROM ${BASE_IMAGE} AS builder

WORKDIR /app

# Ensure git is available (required for installing dependencies from VCS)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Build argument to control whether we're building standalone or in-repo
ARG BUILD_MODE=in-repo
ARG ENV_NAME=css_env

# Copy environment code (always at root of build context)
COPY . /app/env

# For in-repo builds, openenv is already vendored in the build context
# For standalone builds, openenv will be installed via pyproject.toml
WORKDIR /app/env

# Ensure uv is available (for local builds where base image lacks it)
RUN if ! command -v uv >/dev/null 2>&1; then \
        curl -LsSf https://astral.sh/uv/install.sh | sh && \
        mv /root/.local/bin/uv /usr/local/bin/uv && \
        mv /root/.local/bin/uvx /usr/local/bin/uvx; \
    fi

# Install dependencies using uv sync
# If uv.lock exists, use it; otherwise resolve on the fly
RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f uv.lock ]; then \
        uv sync --frozen --no-install-project --no-editable; \
    else \
        uv sync --no-install-project --no-editable; \
    fi

RUN --mount=type=cache,target=/root/.cache/uv \
    if [ -f uv.lock ]; then \
        uv sync --frozen --no-editable; \
    else \
        uv sync --no-editable; \
    fi

# Ensure OpenEnv runtime is present in the environment venv.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --python /app/env/.venv/bin/python "openenv-core[core]>=0.2.1" && \
    /app/env/.venv/bin/python -c "import openenv; print(openenv.__version__)"

# Final runtime stage
FROM ${BASE_IMAGE}

WORKDIR /app

# Install curl for health checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from builder
COPY --from=builder /app/env/.venv /app/env/.venv

# Copy only runtime source files (avoid duplicating .venv inside /app/env)
COPY --from=builder /app/env/__init__.py /app/env/__init__.py
COPY --from=builder /app/env/client.py /app/env/client.py
COPY --from=builder /app/env/models.py /app/env/models.py
COPY --from=builder /app/env/reward.py /app/env/reward.py
COPY --from=builder /app/env/openenv.yaml /app/env/openenv.yaml
COPY --from=builder /app/env/server /app/env/server
COPY --from=builder /app/env/graders /app/env/graders
COPY --from=builder /app/env/tasks /app/env/tasks

# Set PATH to use the virtual environment
ENV PATH="/app/env/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Set PYTHONPATH so imports work correctly
ENV PYTHONPATH="/app/env"

# API port required by the runtime platform
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Run the FastAPI server
# The module path is constructed to work with the /app/env structure
CMD ["sh", "-c", "cd /app/env && /app/env/.venv/bin/uvicorn server.app:app --host 0.0.0.0 --port 7860"]
