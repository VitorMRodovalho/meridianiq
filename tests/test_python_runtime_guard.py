# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Python-runtime guard for the rate limiter (issue #333).

``slowapi`` calls ``asyncio.iscoroutinefunction`` when it decorates a route
(``slowapi/extension.py``). Python deprecates that function and slates it for
removal in 3.16, where the decorator, and every rate-limited router with it,
would fail at import. slowapi 0.1.10 (2026-06) is the latest release and still
calls it; two upstream pull requests with the fix were closed without merge.

A 3.16 runner would fail the suite anyway, after the bump. This guard fails on
the change that points CI (``python-version`` or ``UV_PYTHON``), the image,
mypy or the classifiers at 3.16 while the installed slowapi still makes the
call, and says why. Once a slowapi release drops the call, the guard passes on
its own and can be deleted.
"""

from __future__ import annotations

import ast
import importlib.util
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: First Python release without ``asyncio.iscoroutinefunction``.
REMOVED_IN = (3, 16)


def removed_call_sites(source: str) -> list[int]:
    """Line numbers where ``source`` reads ``asyncio.iscoroutinefunction``."""
    return sorted(
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute)
        and node.attr == "iscoroutinefunction"
        and isinstance(node.value, ast.Name)
        and node.value.id == "asyncio"
    )


def _slowapi_call_sites() -> list[str]:
    spec = importlib.util.find_spec("slowapi")
    assert spec is not None and spec.submodule_search_locations, (
        "slowapi is not installed; it is in the [dev] extra"
    )
    package = Path(next(iter(spec.submodule_search_locations)))
    return [
        f"{path.relative_to(package.parent)}:{line}"
        for path in sorted(package.rglob("*.py"))
        for line in removed_call_sites(path.read_text(encoding="utf-8"))
    ]


def _version(text: str) -> tuple[int, int]:
    major, minor = text.split(".")[:2]
    return int(major), int(minor)


def _targeted_versions() -> dict[str, list[tuple[int, int]]]:
    """Every place that picks the Python CI, the image or the type checker runs on."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    # `python-version` for setup-python, `UV_PYTHON` for the uv-managed install.
    workflow = re.compile(r"""(?:python-version|UV_PYTHON):\s*["']?(\d+\.\d+)""")
    return {
        "Dockerfile": [
            _version(v)
            for v in re.findall(
                r"^FROM\s+python:(\d+\.\d+)",
                (ROOT / "Dockerfile").read_text(encoding="utf-8"),
                re.MULTILINE,
            )
        ],
        **{
            f".github/workflows/{name}": [
                _version(v)
                for v in workflow.findall(
                    (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
                )
            ]
            for name in ("ci.yml", "doc-sync-check.yml")
        },
        "pyproject.toml [tool.mypy] python_version": [
            _version(pyproject["tool"]["mypy"]["python_version"])
        ],
        "pyproject.toml classifiers": [
            _version(c.rsplit("::", 1)[1].strip())
            for c in pyproject["project"]["classifiers"]
            if re.fullmatch(r"Programming Language :: Python :: \d+\.\d+", c)
        ],
    }


def test_the_detector_tells_the_removed_call_from_its_replacement() -> None:
    assert removed_call_sites("import asyncio\nasyncio.iscoroutinefunction(f)\n") == [2]
    assert removed_call_sites("import inspect\ninspect.iscoroutinefunction(f)\n") == []
    assert removed_call_sites("# asyncio.iscoroutinefunction(f)\n") == []


def test_every_version_source_is_read() -> None:
    """An empty source would make the guard below pass without checking anything."""
    unread = [source for source, versions in _targeted_versions().items() if not versions]
    assert not unread, f"no Python version found in: {unread}"


def test_no_python_target_reaches_3_16_while_slowapi_makes_the_removed_call() -> None:
    sites = _slowapi_call_sites()
    if not sites:
        return
    too_new = {
        source: [f"{major}.{minor}" for major, minor in versions if (major, minor) >= REMOVED_IN]
        for source, versions in _targeted_versions().items()
    }
    too_new = {source: versions for source, versions in too_new.items() if versions}
    assert not too_new, (
        f"Python {REMOVED_IN[0]}.{REMOVED_IN[1]} removes asyncio.iscoroutinefunction, which "
        f"the installed slowapi still calls at {sites}; rate limiting would fail at import. "
        f"Targets at or past it: {too_new}. Wait for a slowapi release without the call, "
        "or decide otherwise in #333."
    )
