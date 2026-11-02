#!/usr/bin/env python3
# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Drive the API image the way production runs it (#349).

The deploy job builds the image remotely after the tests pass, so before
this check nothing exercised the image itself: it shipped without openpyxl
from 2026-03-29 to 2026-10-31 (#348). This script runs INSIDE a container
built from the Dockerfile and talks to its uvicorn server over HTTP, so a
package the image lacks, or a system library WeasyPrint cannot load, fails
here instead of in production:

- upload the bundled synthetic sample (``src/api/demo_data/sample.xer``);
- generate and download the health report PDF (WeasyPrint);
- export the project to Excel (openpyxl);
- upload a synthetic CBS workbook, then export it as AIA G703 (openpyxl).

The container has no Supabase credentials, so the app uses its in-memory
store; the script refuses to run if the opt-in for a remote store is set.

Usage (as CI runs it, with the server already healthy in container ``api``)::

    docker exec api python /tmp/image_smoke.py

Exit status 0 when every check passes, 1 otherwise (the failures are listed).
"""

from __future__ import annotations

import io
import os
import sys
from collections.abc import Callable

import httpx

BASE = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:8080")
SAMPLE_XER = "src/api/demo_data/sample.xer"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _cbs_workbook() -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary by CBS"
    ws.append(["Synthetic program budget"])
    ws.append(
        [
            "CBS-Lvl1",
            "CBS-Lvl2",
            "Scope",
            "WBSE L1",
            "Design Package",
            "DJV Estimate",
            "DJV Contingency (25%)",
            "Escalation",
        ]
    )
    ws.append(["Construction", "01", "Earthwork", "W1", "DP-1", 1000.0, 250.0, 50.0])
    ws.append(["Design", "02", "Engineering", "W2", "DP-2", 400.0, 100.0, 20.0])
    ws.append(["Total", "", "", "", "", 1400.0, 350.0, 70.0])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main() -> int:
    if os.environ.get("ALLOW_REMOTE_SUPABASE") == "1":
        print("refusing to run: ALLOW_REMOTE_SUPABASE=1 would point the app at a real store")
        return 1

    failures: list[str] = []
    state: dict[str, str] = {}
    client = httpx.Client(base_url=BASE, timeout=120)

    def check(name: str, step: Callable[[], str]) -> None:
        try:
            print(f"ok    {name}: {step()}")
        except Exception as exc:  # report every failed check, not just the first
            failures.append(name)
            print(f"FAIL  {name}: {type(exc).__name__}: {exc}")

    def upload() -> str:
        with open(SAMPLE_XER, "rb") as f:
            r = client.post("/api/v1/upload", files={"file": ("sample.xer", f)})
        assert r.status_code == 200, f"HTTP {r.status_code} {r.text[:200]}"
        state["project_id"] = r.json()["project_id"]
        return "project created"

    def health_pdf() -> str:
        r = client.post(
            "/api/v1/reports/generate",
            json={"project_id": state["project_id"], "report_type": "health"},
        )
        assert r.status_code == 200, f"generate: HTTP {r.status_code} {r.text[:200]}"
        r = client.get(f"/api/v1/reports/{r.json()['report_id']}/download")
        assert r.status_code == 200, f"download: HTTP {r.status_code} {r.text[:200]}"
        assert r.content[:5] == b"%PDF-", f"not a PDF: {r.content[:20]!r}"
        return f"{len(r.content)} bytes"

    def excel_export() -> str:
        r = client.get(f"/api/v1/projects/{state['project_id']}/export/excel")
        assert r.status_code == 200, f"HTTP {r.status_code} {r.text[:200]}"
        assert r.headers["content-type"].startswith(XLSX), r.headers["content-type"]
        assert r.content[:2] == b"PK", "not a zip container"
        return f"{len(r.content)} bytes"

    def cbs_upload() -> str:
        r = client.post(
            "/api/v1/cost/upload",
            params={"project_id": state["project_id"]},
            files={"file": ("budget.xlsx", _cbs_workbook())},
        )
        assert r.status_code == 200, f"HTTP {r.status_code} {r.text[:200]}"
        body = r.json()
        assert body["cbs_element_count"] == 2, f"{body['cbs_element_count']} elements"
        state["snapshot_id"] = body["snapshot_id"]
        return "2 CBS elements stored"

    def aia_export() -> str:
        r = client.get(
            f"/api/v1/projects/{state['project_id']}/export/aia-g703",
            params={"snapshot_id": state["snapshot_id"]},
        )
        assert r.status_code == 200, f"HTTP {r.status_code} {r.text[:200]}"
        assert r.content[:2] == b"PK", "not a zip container"
        return f"{len(r.content)} bytes"

    check("upload the bundled sample", upload)
    if "project_id" in state:
        check("health report PDF", health_pdf)
        check("Excel export", excel_export)
        check("CBS cost upload", cbs_upload)
        if "snapshot_id" in state:
            check("AIA G703 export", aia_export)

    if failures:
        print(f"{len(failures)} check(s) failed: {', '.join(failures)}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
