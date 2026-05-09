# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Pre-registered calibration gates per engine.

Each gate module commits its sub-gate thresholds in code, locked against an
ADR amendment. Path-A activation per the parent ADR is the structural escape
hatch when a sub-gate fails or its corpus precondition is unmet.

Currently registered:
- ``revision_trends_w4`` — Cycle 4 W4 (ADR-0022 §"W4" + ADR-0023).
"""

from __future__ import annotations
