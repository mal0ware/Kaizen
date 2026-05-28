# Kaizen — production container image.
#
# Single-stage build kept deliberately simple. Production extras
# (anthropic, discord, db, local) are installed up front so the image
# matches the runtime topology described in docs/architecture.md.
#
# Build:
#   docker build -t kaizen:local .
#
# Run (standalone, for smoke-testing the image):
#   docker run --rm -it --env-file .env kaizen:local
#
# Normal production path uses deploy/docker-compose.box-a.yml — this
# Dockerfile is referenced by that compose file's `build:` directive.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps:
#   build-essential + libpq-dev — for any wheel that needs to compile
#   libpq5                     — runtime client lib for asyncpg
#   curl, ca-certificates       — healthchecks, TLS roots
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only what's needed to install, so layer cache survives source
# tweaks that don't touch dependencies.
COPY pyproject.toml ./
COPY kaizen ./kaizen

RUN pip install --upgrade pip wheel \
    && pip install ".[anthropic,discord,db,local]"

# Drop root.
RUN useradd -u 1000 -m kaizen \
    && chown -R kaizen:kaizen /app
USER kaizen

# Cheap healthcheck — package importable is enough; deeper liveness
# is the core's job to expose later.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import kaizen" || exit 1

ENTRYPOINT ["python", "-m", "kaizen"]
