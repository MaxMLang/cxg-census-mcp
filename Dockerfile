# syntax=docker/dockerfile:1.7
# Multi-stage build for cxg-census-mcp.
#
# Layers, in order:
#  1. builder       — install runtime deps with uv into a virtualenv we copy out
#  2. cache-warmer  — optionally pre-warm the OLS cache from data/ols_seed_terms.json
#  3. runtime       — slim image, non-root user, stdio entrypoint

ARG PYTHON_VERSION=3.11

# ---------- builder ----------
FROM python:${PYTHON_VERSION}-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /build

# Install uv from its official image; faster than pip-installing it.
COPY --from=ghcr.io/astral-sh/uv:0.5.0 /uv /uvx /usr/local/bin/

COPY pyproject.toml README.md uv.lock* ./
COPY src/ ./src/

# Install into a virtualenv we can ship in the runtime stage.
RUN uv venv /opt/venv \
 && VIRTUAL_ENV=/opt/venv uv pip install . --no-cache

# ---------- cache-warmer (optional) ----------
FROM builder AS cache-warmer

ARG WITH_DAG=false
ENV CXG_CENSUS_MCP_CACHE_DIR=/cache \
    CXG_CENSUS_MCP_LOG_LEVEL=WARNING \
    PATH=/opt/venv/bin:$PATH

COPY scripts/ ./scripts/

# Tolerate offline builds: the prewarm script swallows OLS outages.
RUN mkdir -p /cache \
 && (python scripts/prewarm_ols_cache.py $( [ "$WITH_DAG" = "true" ] && echo "--with-dag" ) || true)

# ---------- runtime ----------
FROM python:${PYTHON_VERSION}-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CXG_CENSUS_MCP_CACHE_DIR=/var/cache/cxg-census-mcp \
    CXG_CENSUS_MCP_LOG_LEVEL=WARNING \
    PATH=/opt/venv/bin:$PATH

LABEL org.opencontainers.image.title="cxg-census-mcp" \
      org.opencontainers.image.source="https://github.com/MaxMLang/cxg-census-mcp" \
      org.opencontainers.image.licenses="MIT"

RUN useradd --create-home --uid 1000 census \
 && mkdir -p /var/cache/cxg-census-mcp \
 && chown -R census:census /var/cache/cxg-census-mcp

COPY --from=builder /opt/venv /opt/venv
COPY --from=cache-warmer /cache /var/cache/cxg-census-mcp/
RUN chown -R census:census /var/cache/cxg-census-mcp

USER census
WORKDIR /home/census

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import cxg_census_mcp; print(cxg_census_mcp.__version__)" || exit 1

ENTRYPOINT ["python", "-m", "cxg_census_mcp"]
