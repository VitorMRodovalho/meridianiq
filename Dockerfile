# Build stage: uv installs the exact set in uv.lock, the same one CI tests
# (ADR-0033). Nothing from this stage reaches the runtime image except
# /opt/venv and /app: not uv, and no compiler. pyyaml is the only dependency
# built from source here (no cp315 wheel), and it builds as pure Python, as
# it did when the image carried gcc (no libyaml headers either way).
FROM python:3.15-slim AS build
# Pinned by digest, as uv's Docker guide recommends: a tag can move.
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /bin/uv
WORKDIR /app
# The environment lives outside /app, owned by root: the app user can read it
# but not change it. UV_NO_DEV keeps any default `dev` dependency group out.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_CACHE=1 UV_NO_DEV=1 UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv
COPY pyproject.toml uv.lock ./
# `--locked` fails the build if uv.lock does not match pyproject.toml.
RUN uv sync --locked --no-install-project --extra api --extra reports --extra export --extra ml
COPY README.md ./
COPY src/ src/
RUN uv sync --locked --no-editable --extra api --extra reports --extra export --extra ml

# Runtime stage: the same base, so /opt/venv/bin/python still points at this
# image's /usr/local/bin/python3.15. Only WeasyPrint's system libraries.
FROM python:3.15-slim
RUN apt-get update && apt-get install -y --no-install-recommends libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libcairo2 && rm -rf /var/lib/apt/lists/*
COPY --from=build /opt/venv /opt/venv
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/opt/venv/bin:$PATH"
# The base image ships the standard library without bytecode, and appuser
# cannot write it, so without this every start compiles the stdlib again
# (measured: `import src.api.app` 3.4 s for three runs against 2.6 s).
RUN python -m compileall -q -j 0 /usr/local/lib/python3.15
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
CMD ["python", "-m", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
