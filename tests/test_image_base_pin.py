# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""The API image's Python base is pinned by digest, the same in both stages.

CI builds the image for its smoke test, and Fly's remote builder builds it
again at the deploy (``flyctl deploy --remote-only``), minutes later. With a
bare tag each build resolves ``python:3.15-slim`` on its own, so a base
republished in between would ship without the smoke. A digest makes both
builds pull the same base, and Dependabot's ``docker`` ecosystem proposes the
next digest as a pull request (ADR-0033, Amendment 2).

The runtime stage must use the build stage's base: ``/opt/venv`` comes from
the build stage, and its ``python`` points at the runtime image's interpreter.
An update applied to one ``FROM`` line only fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_FROM_PYTHON = re.compile(r"^FROM\s+(python:\S+)", re.MULTILINE)
_PINNED = re.compile(r"python:[^@\s]+@sha256:[0-9a-f]{64}")

_DIGEST = "sha256:" + "a" * 64
_OTHER_DIGEST = "sha256:" + "b" * 64


def base_pin_problems(dockerfile: str) -> list[str]:
    """Why the Dockerfile's Python bases are not one image pinned by digest."""
    bases: list[str] = _FROM_PYTHON.findall(dockerfile)
    problems = []
    if len(bases) != 2:
        problems.append(f"expected 2 `FROM python` lines (build, runtime), found {len(bases)}")
    problems += [f"not pinned by digest: {base}" for base in bases if not _PINNED.fullmatch(base)]
    if len(set(bases)) > 1:
        problems.append(f"the stages use different bases: {sorted(set(bases))}")
    return problems


def test_the_check_can_say_no() -> None:
    pinned = (
        f"FROM python:3.15-slim@{_DIGEST} AS build\nRUN true\nFROM python:3.15-slim@{_DIGEST}\n"
    )
    assert base_pin_problems(pinned) == []
    # A bare tag, in both stages or in one.
    assert base_pin_problems("FROM python:3.15-slim AS build\nFROM python:3.15-slim\n")
    assert base_pin_problems(f"FROM python:3.15-slim@{_DIGEST} AS build\nFROM python:3.15-slim\n")
    # A digest update applied to one stage only.
    assert base_pin_problems(
        f"FROM python:3.15-slim@{_DIGEST} AS build\nFROM python:3.15-slim@{_OTHER_DIGEST}\n"
    )
    # A stage that no longer starts from python, and a truncated digest.
    assert base_pin_problems(f"FROM python:3.15-slim@{_DIGEST} AS build\nFROM debian:stable\n")
    assert base_pin_problems(
        "FROM python:3.15-slim@sha256:abc AS build\nFROM python:3.15-slim@sha256:abc\n"
    )


def test_the_image_pins_one_python_base_by_digest() -> None:
    problems = base_pin_problems((ROOT / "Dockerfile").read_text(encoding="utf-8"))
    assert problems == [], "; ".join(problems)
