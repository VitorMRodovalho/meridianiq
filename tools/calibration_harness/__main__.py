# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""CLI entry point for ``python -m tools.calibration_harness``.

Preserved as a separate module after the W3-C conversion of
``tools.calibration_harness`` from a single .py file to a package so
the fixture tree (``fixtures/optimism_synth/``) could live under it.
"""

from __future__ import annotations

import sys

from tools.calibration_harness import cli


if __name__ == "__main__":
    sys.exit(cli())
