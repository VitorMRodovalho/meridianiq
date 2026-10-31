FROM python:3.15-slim
# uv installs the exact set in uv.lock, the same one CI tests (ADR-0033).
# Pinned by digest, as uv's Docker guide recommends: a tag can move.
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /bin/uv
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev libcairo2 && rm -rf /var/lib/apt/lists/*
# The environment lives outside /app, owned by root: the app user can read it
# but not change it, and `chown -R /app` below does not copy it into a new layer.
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_CACHE=1 UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/opt/venv
COPY pyproject.toml uv.lock README.md ./
# `--locked` fails the build if uv.lock does not match pyproject.toml.
RUN uv sync --locked --no-install-project --extra api --extra reports --extra export
COPY src/ src/
RUN uv sync --locked --no-editable --extra api --extra reports --extra export
ENV PATH="/opt/venv/bin:$PATH"
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
CMD ["python", "-m", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
