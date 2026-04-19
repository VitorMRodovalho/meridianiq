# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""One-shot calibration harnesses gated by a cycle's ADR.

Scripts here are intentionally outside the regular `src/` package because
they read confidential local datasets (via environment variables) that
must never be referenced by path in committed code. Outputs are written
to `/tmp` and `meridianiq-private/`, never the repo.
"""
