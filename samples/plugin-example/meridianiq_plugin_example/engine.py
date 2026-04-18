"""Reference plugin — counts activities by status code.

Demonstrates the minimum viable plugin shape:

* a class with ``name``, ``version``, and ``analyze(schedule)``
* registered via ``[project.entry-points."meridianiq.engines"]``

Once installed (``pip install -e samples/plugin-example``), the host app
discovers it on next startup and exposes it through
``src.plugins.list_plugins()``. No code changes to MeridianIQ required.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


class ActivityCounterEngine:
    name = "activity-counter"
    version = "0.1.0"

    def analyze(self, schedule: Any) -> dict[str, Any]:
        """Return ``{total, by_status}`` for the given schedule."""
        statuses = Counter((a.status_code or "Unknown") for a in schedule.activities)
        return {
            "total": len(schedule.activities),
            "by_status": dict(statuses),
        }
