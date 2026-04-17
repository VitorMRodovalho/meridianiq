# MCP + Claude Integration

MeridianIQ exposes **22 tools** via the Model Context Protocol (MCP), letting Claude Code and Claude Desktop query and analyze your schedules in natural language. The full catalog with signatures and docstrings is in [mcp-tools.md](../mcp-tools.md); this guide walks through setup and common usage patterns.

## Install

MCP support is optional — install with the `mcp` extras:

```bash
pip install -e ".[mcp]"
```

Run the server (stdio transport, local only):

```bash
python -m src.mcp_server
```

The server reads from the same data store as the web app. If you're using `InMemoryStore` (dev default), only projects uploaded via the MCP server's `upload_xer` tool will be visible — not projects uploaded through the web UI against a separate Python process. For cross-process visibility, point `MCP_ENVIRONMENT=production` and wire it to your Supabase instance.

## Configure Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "meridianiq": {
      "command": "python",
      "args": ["-m", "src.mcp_server"],
      "cwd": "/absolute/path/to/p6-xer-analytics"
    }
  }
}
```

Restart Claude Desktop. The 22 tools appear in the MCP tools list — Claude will invoke them automatically when relevant.

## Configure Claude Code

Add the same snippet to your user-level config (typically `~/.config/claude-code/config.json`) or invoke once per project:

```bash
claude-code mcp add meridianiq -- python -m src.mcp_server
```

## Tool categories

The 22 tools fall into five groups:

### 1. Ingestion & inventory

- `upload_xer(file_path)` — parse and store an XER from the local filesystem
- `list_projects()` — all uploaded schedules with activity counts
- `get_project_summary(project_id)` — project metadata + activity status breakdown

### 2. Analysis (single schedule)

- `run_dcma(project_id)` — 14-Point Schedule Assessment
- `get_critical_path(project_id)` — CP activities + total float
- `get_health_score(project_id)` — composite 0–100
- `get_float_entropy(project_id)` — Shannon entropy of float distribution
- `get_scorecard(project_id)` — letter grades A–F across 5 dimensions
- `validate_calendars_tool(project_id)` — DCMA #13 calendar checks
- `analyze_root_cause(project_id, activity_id)` — backwards network trace
- `compute_delay_attribution_tool(project_id, baseline_id)` — party breakdown

### 3. Cross-schedule analysis

- `compare_schedules(baseline_id, update_id)` — change detection + manipulation flags
- `run_half_step(baseline_id, update_id)` — MIP 3.4 bifurcation

### 4. Predictive & what-if

- `predict_delays(project_id, baseline_id)` — activity-level risk scoring (RF+GB)
- `run_what_if(...)` — deterministic / probabilistic scenario
- `extract_benchmarks(project_id)` — anonymized cross-project metrics

### 5. Generation & export

- `generate_schedule(...)` — template-based with stochastic durations
- `build_schedule_from_description(description)` — NLP-driven generation via Claude API
- `level_resources(...)` — RCPSP via Serial SGS
- `optimize_schedule_es(...)` — Evolution Strategies RCPSP
- `export_xer(project_id)` — round-trip write-back to P6 format
- `get_schedule_view_tool(project_id, baseline_id)` — Gantt layout data

## Example prompts

Once the MCP server is connected, you can phrase requests naturally:

- *"Upload the XER at `/tmp/mps-up04.xer` and tell me if it passes DCMA."* → Claude calls `upload_xer`, then `run_dcma`, summarizes the failing checks.
- *"Compare the two most recent uploads in project PROG-0003 and highlight any manipulation flags."* → `list_projects` → `compare_schedules` → reports flags.
- *"Which activity is the root cause for activity A1450 being delayed?"* → `analyze_root_cause` with the activity ID.
- *"Simulate a 30-day delay to activity FOUNDATIONS-03 and tell me the project-level impact."* → `run_what_if`.

## Why "summary-based, no raw data egress"

Tools return **JSON summaries**, not the full ParsedSchedule. This limits the token footprint and prevents accidental exposure of sensitive project data to Claude's API. For the natural-language `/ask` endpoint in the web app (also Claude-backed) the same principle applies: the backend builds a schedule summary (`_build_schedule_summary` in `nlp_query.py`) and ships that + the question, not the raw tables.

If you need raw access, use the full API (see [API Reference](../api-reference.md)).

## Security

- MCP runs stdio-only — no network port is opened
- The server inherits the filesystem access of the Python process, so `upload_xer` can read any file that user can read. Don't run it as root.
- Tools write through the same store as the REST API, subject to the same RLS policies when using `SupabaseStore`.

## Troubleshooting

- **Claude doesn't see the tools** — restart Claude Desktop / Claude Code after editing config. Check the config path is correct for your OS.
- **`ImportError: mcp`** — you didn't install the `mcp` extras. Run `pip install -e ".[mcp]"`.
- **"Project not found"** — the MCP server and web app are running against different Python processes / stores. Either point both at Supabase, or upload via the MCP tool itself.

## Related

- [MCP Tools Catalog](../mcp-tools.md) — full signatures and docstrings for all 22 tools
- [Analysis Workflow](analysis-workflow.md) — which tool maps to which forensic stage
- [/ask page](../../web/src/routes/ask/+page.svelte) — web-based natural-language query that uses the same summary approach
