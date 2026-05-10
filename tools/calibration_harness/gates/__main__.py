# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""CLI entry point for ``python -m tools.calibration_harness.gates``.

Currently dispatches to the ``revision_trends_w4`` gate (the only registered
gate at Cycle 4 close). Future gates register their CLI here.
"""

from __future__ import annotations

import sys

from tools.calibration_harness.gates.revision_trends_w4 import cli


if __name__ == "__main__":
    sys.exit(cli())
