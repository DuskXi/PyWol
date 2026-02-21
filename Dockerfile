# ── Stage 1: Build Frontend ──────────────────────────
FROM node:22-slim AS frontend-builder

RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app/WolGUI

# Install dependencies first (cached layer).
# --ignore-scripts avoids running "postinstall: quasar prepare"
# which needs the full project structure to be present.
COPY WolGUI/package.json WolGUI/pnpm-lock.yaml WolGUI/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile --ignore-scripts

# Copy full project and run quasar prepare + build
COPY WolGUI/ .
RUN npx quasar prepare && pnpm build

# ── Stage 2: Python Runtime ─────────────────────────
FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install runtime dependencies:
#   iputils-ping – host online check (ping)
#   etherwake    – Layer 2 WOL magic packet sender (more reliable)
RUN apt-get update && apt-get install -y --no-install-recommends \
    iputils-ping \
    etherwake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application code
COPY app/ app/
COPY main.py .

# Copy built frontend
COPY --from=frontend-builder /app/WolGUI/dist/spa static/

# Create data directory for SQLite
RUN mkdir -p /app/data

EXPOSE 8000

# Default: auto-detect etherwake, fall back to socket
ENV WOL_METHOD=auto
ENV WOL_INTERFACE=

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
