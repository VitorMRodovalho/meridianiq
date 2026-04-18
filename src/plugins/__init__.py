# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Plugin architecture for third-party analysis engines.

A plugin is a callable that takes a :class:`ParsedSchedule` and returns a
JSON-serialisable result. Plugins are discovered via Python entry-points
under the ``meridianiq.engines`` group, so any pip-installed package can
register its own analysis without modifying MeridianIQ::

    # In your plugin's pyproject.toml
    [project.entry-points."meridianiq.engines"]
    my-engine = "my_package.engine:MyEngine"

The referenced object must be either:

* a class implementing the :class:`AnalysisEngine` Protocol, or
* an instance of one (singleton plugin).

At application startup, call :func:`discover_plugins` to populate the
in-memory registry. Use :func:`get_plugin` / :func:`list_plugins` to
introspect or invoke them. ``samples/plugin-example/`` is a working
reference plugin you can copy.

Reference: PEP 660 (entry-points), Python ``importlib.metadata``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from typing import Any, Protocol, runtime_checkable

from src.parser.models import ParsedSchedule

logger = logging.getLogger(__name__)

PLUGIN_GROUP = "meridianiq.engines"


@runtime_checkable
class AnalysisEngine(Protocol):
    """Protocol any plugin must satisfy.

    The Protocol is ``runtime_checkable`` so we can validate registered
    plugins via ``isinstance(obj, AnalysisEngine)`` at discovery time. Both
    classes and instances work — the registry normalises instances out of
    classes by calling ``cls()``.
    """

    name: str
    """Human-readable plugin name. Must be unique across registered plugins."""

    version: str
    """SemVer string. Surfaced in /api responses and logs."""

    def analyze(self, schedule: ParsedSchedule) -> dict[str, Any]:
        """Run the plugin against a parsed schedule. Return JSON-serialisable dict."""
        ...


@dataclass
class PluginRecord:
    """One entry in the plugin registry."""

    name: str
    version: str
    entry_point: str
    instance: AnalysisEngine
    error: str | None = None  # populated when load failed


_registry: dict[str, PluginRecord] = {}


def _load_one(ep: EntryPoint) -> PluginRecord | None:
    """Materialise one entry-point into a :class:`PluginRecord`.

    Returns ``None`` when the entry-point can't be loaded or doesn't satisfy
    the protocol — these are logged but never raise, so a single broken
    plugin can't take down startup.
    """
    try:
        target = ep.load()
    except Exception as exc:  # pragma: no cover — log path
        logger.warning("Failed to load plugin %s: %s", ep.value, exc)
        return None

    instance = target() if isinstance(target, type) else target

    if not isinstance(instance, AnalysisEngine):
        logger.warning(
            "Plugin %s does not satisfy AnalysisEngine protocol (missing name/version/analyze)",
            ep.value,
        )
        return None

    return PluginRecord(
        name=instance.name,
        version=instance.version,
        entry_point=ep.value,
        instance=instance,
    )


def discover_plugins() -> dict[str, PluginRecord]:
    """Walk the entry-point group and (re)populate the registry.

    Idempotent — repeated calls re-discover and replace the registry. Useful
    in tests that install/uninstall plugins between cases.
    """
    _registry.clear()
    eps = entry_points(group=PLUGIN_GROUP)
    for ep in eps:
        record = _load_one(ep)
        if record is None:
            continue
        if record.name in _registry:
            logger.warning(
                "Duplicate plugin name %r — keeping first registration (%s)",
                record.name,
                _registry[record.name].entry_point,
            )
            continue
        _registry[record.name] = record
    return dict(_registry)


def list_plugins() -> list[PluginRecord]:
    """Return a snapshot of the current registry, sorted by name."""
    return sorted(_registry.values(), key=lambda r: r.name)


def get_plugin(name: str) -> PluginRecord | None:
    """Look up one plugin by name. ``None`` if not registered."""
    return _registry.get(name)


def register_plugin(instance: AnalysisEngine, *, entry_point: str = "<programmatic>") -> None:
    """Register a plugin instance directly, bypassing entry-point discovery.

    Mainly for tests and for embedded use where the host process wants to
    inject a plugin without going through ``pip install`` + entry-points.
    """
    if not isinstance(instance, AnalysisEngine):
        raise TypeError(
            "Object does not satisfy AnalysisEngine protocol — needs name, version, analyze()"
        )
    _registry[instance.name] = PluginRecord(
        name=instance.name,
        version=instance.version,
        entry_point=entry_point,
        instance=instance,
    )
