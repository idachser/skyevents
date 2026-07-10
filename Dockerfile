# Ephemeris lives in the image layer (SKYEVENTS_DATA); the SQLite
# event cache goes to the /data volume via SKYEVENTS_CACHE, so
# mounting the volume does not shadow the baked-in ephemeris.

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app
ENV UV_LINK_MODE=copy \
    SKYEVENTS_DATA=/app/data \
    SKYEVENTS_CACHE=/data/cache.db

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY skyevents ./skyevents
RUN uv sync --frozen --no-dev

# warm the DE440s download (~32 MB) at build time, not first start
RUN uv run --no-sync python -c \
    "from skyevents.ephemeris import load_ephemeris; load_ephemeris()"

VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD \
    ["/app/.venv/bin/python", "-c", \
     "import urllib.request; \
      urllib.request.urlopen('http://localhost:8000/health')"]

CMD ["uv", "run", "--no-sync", "uvicorn", "skyevents.api:app", \
     "--host", "0.0.0.0", "--port", "8000"]
