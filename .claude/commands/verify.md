Run full project verification suite:

1. Backend tests: `python -m pytest tests/ -q`
2. Python lint: `ruff check src/ tests/`
3. Python format check: `ruff format --check src/ tests/`
4. Frontend type check: `cd web && npm run check`
5. Frontend build: `cd web && npm run build`

Report pass/fail for each step. Stop on first failure and diagnose.
