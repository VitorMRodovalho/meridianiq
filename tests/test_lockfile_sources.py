# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""uv.lock may only point at PyPI (ADR-0033).

``uv sync --locked`` checks uv.lock against the requirements in
pyproject.toml, not where each artifact URL points. An edit that swapped a
wheel URL and its hash would install that wheel at the next deploy, and a uv
configured with a private mirror would write the mirror's URLs into this
public lock. These tests keep every package source on the PyPI registry (or
the project itself) and every artifact on files.pythonhosted.org over HTTPS.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

LOCK = Path(__file__).resolve().parent.parent / "uv.lock"
ALLOWED_SOURCES = ({"registry": "https://pypi.org/simple"}, {"editable": "."})
ARTIFACT_HOST = "files.pythonhosted.org"


def _packages() -> list[dict[str, Any]]:
    return list(tomllib.loads(LOCK.read_text(encoding="utf-8"))["package"])


def foreign_sources(packages: list[dict[str, Any]]) -> list[str]:
    """Packages whose source is neither the PyPI registry nor the project."""
    return [p["name"] for p in packages if p.get("source") not in ALLOWED_SOURCES]


def foreign_artifacts(packages: list[dict[str, Any]]) -> list[str]:
    """Artifact URLs that are not HTTPS on files.pythonhosted.org."""
    urls = [
        artifact["url"]
        for p in packages
        for artifact in [p.get("sdist", {}), *p.get("wheels", [])]
        if "url" in artifact
    ]
    return [
        url
        for url in urls
        if urlparse(url).scheme != "https" or urlparse(url).netloc != ARTIFACT_HOST
    ]


def test_the_lock_parses_into_packages() -> None:
    """An empty parse would make the two checks below pass without checking anything."""
    assert len(_packages()) > 50


def test_every_package_comes_from_pypi_or_is_the_project() -> None:
    assert foreign_sources(_packages()) == []


def test_every_artifact_is_on_files_pythonhosted_org() -> None:
    assert foreign_artifacts(_packages()) == []


def test_the_checks_flag_a_foreign_source_and_artifact() -> None:
    mirror = {
        "name": "idna",
        "source": {"registry": "https://mirror.example/simple"},
        "wheels": [{"url": "https://mirror.example/idna-3.20-py3-none-any.whl"}],
    }
    plain_http = {
        "name": "six",
        "source": {"registry": "https://pypi.org/simple"},
        "sdist": {"url": "http://files.pythonhosted.org/six-1.17.0.tar.gz"},
    }
    assert foreign_sources([mirror, plain_http]) == ["idna"]
    assert foreign_artifacts([mirror, plain_http]) == [
        "https://mirror.example/idna-3.20-py3-none-any.whl",
        "http://files.pythonhosted.org/six-1.17.0.tar.gz",
    ]
