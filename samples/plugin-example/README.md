# MeridianIQ plugin example

Minimum viable plugin showing how to extend MeridianIQ with a third-party
analysis engine. Counts activities by status code.

## Install

```bash
pip install -e samples/plugin-example
```

After install, the plugin is discoverable on next startup of the
MeridianIQ API or MCP server. No changes needed in MeridianIQ itself.

## Use it

```python
from src.plugins import discover_plugins, get_plugin
from src.parser.xer_reader import XERReader

discover_plugins()
plugin = get_plugin("activity-counter")
schedule = XERReader().read("path/to/file.xer")
result = plugin.instance.analyze(schedule)
print(result)
# {"total": 142, "by_status": {"Complete": 30, "In Progress": 50, ...}}
```

## Build your own

The protocol is in `src/plugins/__init__.py`. Three rules:

1. Class with `name`, `version`, `analyze(schedule)` (or an instance).
2. Register via `[project.entry-points."meridianiq.engines"]` in
   your `pyproject.toml`.
3. `analyze()` returns a JSON-serialisable `dict`.

That's it. Plugin failures during discovery are logged, never raised — a
broken plugin can't take down the host process.
