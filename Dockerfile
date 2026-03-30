FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libffi-dev libcairo2 && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml README.md .
COPY src/ src/
RUN pip install --no-cache-dir .
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
CMD ["python", "-m", "uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
