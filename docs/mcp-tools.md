# MCP Tools Catalog

MeridianIQ exposes **22 tools** via the Model Context Protocol so AI assistants (Claude Code, Claude Desktop) can query and analyze uploaded P6 XER schedules.

## Installation

Install the MCP extras and run the server:

```bash
pip install -e ".[mcp]"
python -m src.mcp_server
```

### Claude Code / Claude Desktop configuration

Add to your MCP servers config (e.g. `~/.config/claude-code/config.json`):

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

## Tool index

| Tool | One-line summary |
|---|---|
| [`upload_xer`](#upload-xer) | Upload and parse a P6 XER file from the local filesystem. |
| [`list_projects`](#list-projects) | List all uploaded schedules with summary info. |
| [`get_project_summary`](#get-project-summary) | Get detailed summary of a project including activity status breakdown. |
| [`run_dcma`](#run-dcma) | Run DCMA 14-Point schedule assessment. |
| [`get_critical_path`](#get-critical-path) | Compute critical path using the CPM engine. |
| [`get_health_score`](#get-health-score) | Compute composite schedule health score (0-100). |
| [`get_float_entropy`](#get-float-entropy) | Compute Shannon entropy of float distribution. |
| [`analyze_root_cause`](#analyze-root-cause) | Trace backwards through the dependency network to find delay root cause. |
| [`compare_schedules`](#compare-schedules) | Compare two schedule versions to detect changes and manipulation. |
| [`predict_delays`](#predict-delays) | Predict delay risk for all non-complete activities in a schedule. |
| [`extract_benchmarks`](#extract-benchmarks) | Extract anonymized benchmark metrics from a schedule. |
| [`run_half_step`](#run-half-step) | Run half-step bifurcation analysis per AACE RP 29R-03 MIP 3.4. |
| [`run_what_if`](#run-what-if) | Run a what-if scenario on a schedule. |
| [`get_scorecard`](#get-scorecard) | Get a comprehensive schedule scorecard with letter grades. |
| [`level_resources`](#level-resources) | Run resource-constrained scheduling via Serial SGS. |
| [`generate_schedule`](#generate-schedule) | Generate a complete schedule from project parameters. |
| [`build_schedule_from_description`](#build-schedule-from-description) | Build a schedule from a natural language project description. |
| [`export_xer`](#export-xer) | Export a project schedule to XER format. |
| [`optimize_schedule_es`](#optimize-schedule-es) | Optimize a resource-constrained schedule using Evolution Strategies. |
| [`validate_calendars_tool`](#validate-calendars-tool) | Validate work calendar definitions for integrity and best practices. |
| [`compute_delay_attribution_tool`](#compute-delay-attribution-tool) | Compute delay attribution breakdown by responsible party. |
| [`get_schedule_view_tool`](#get-schedule-view-tool) | Get schedule layout data for Gantt visualization. |

## Tools

### `upload_xer`

**Upload and parse a P6 XER file from the local filesystem.**

```python
upload_xer(file_path: str) -> str
```

**Arguments:**

```
file_path: Absolute path to the .xer file.
```

**Returns:**

Project summary with ID, name, activity/relationship counts.

---

### `list_projects`

**List all uploaded schedules with summary info.**

```python
list_projects() -> str
```

**Returns:**

JSON array of projects with name, activity count, relationship count.

---

### `get_project_summary`

**Get detailed summary of a project including activity status breakdown.**

```python
get_project_summary(project_id: str) -> str
```

**Arguments:**

```
project_id: The project identifier from list_projects.
```

**Returns:**

Project metadata, activity counts by status, relationship types.

---

### `run_dcma`

**Run DCMA 14-Point schedule assessment.**

```python
run_dcma(project_id: str) -> str
```

Evaluates schedule quality across 14 standardized checks including
logic density, leads/lags, float distribution, constraints, and more.

**Arguments:**

```
project_id: The project identifier.
```

**Returns:**

Overall score (0-100), pass/fail count, and each metric's result.

---

### `get_critical_path`

**Compute critical path using the CPM engine.**

```python
get_critical_path(project_id: str) -> str
```

Returns the ordered list of activities on the longest path through
the schedule network, with duration and float for each activity.

**Arguments:**

```
project_id: The project identifier.
```

**Returns:**

Critical path activities with ES, EF, LS, LF, TF, FF.

---

### `get_health_score`

**Compute composite schedule health score (0-100).**

```python
get_health_score(project_id: str) -> str
```

Combines DCMA quality (40%), float health (25%), logic integrity (20%),
and trend direction (15%) per GAO Schedule Assessment Guide.

**Arguments:**

```
project_id: The project identifier.
```

**Returns:**

Overall score, rating (excellent/good/fair/poor), component breakdown.

---

### `get_float_entropy`

**Compute Shannon entropy of float distribution.**

```python
get_float_entropy(project_id: str) -> str
```

Measures how uniformly total float is distributed across activities.
Low entropy = concentrated, high entropy = spread evenly.

**Arguments:**

```
project_id: The project identifier.
```

**Returns:**

Entropy value, normalised entropy (0-1), distribution, interpretation.

---

### `analyze_root_cause`

**Trace backwards through the dependency network to find delay root cause.**

```python
analyze_root_cause(project_id: str, activity_id: str = '') -> str
```

Starting from a target activity (or project completion if not specified),
walks backwards through driving predecessors to identify the originating
delay event.

**Arguments:**

```
project_id: The project identifier.
activity_id: Optional target activity. If empty, uses project completion.
```

**Returns:**

Ordered chain from target to root cause with driving reason at each step.

---

### `compare_schedules`

**Compare two schedule versions to detect changes and manipulation.**

```python
compare_schedules(baseline_id: str, update_id: str) -> str
```

Identifies added/deleted/modified activities, relationship changes,
float changes, and potential manipulation indicators.

**Arguments:**

```
baseline_id: The baseline project identifier.
update_id: The update project identifier.
```

**Returns:**

Comparison results with change counts, manipulation flags, and details.

---

### `predict_delays`

**Predict delay risk for all non-complete activities in a schedule.**

```python
predict_delays(project_id: str, baseline_id: str = '') -> str
```

Uses weighted multi-factor risk scoring with explainable risk factors
per DCMA 14-Point and AACE RP 49R-06 criteria. Optionally enhanced
with trend features when a baseline is provided.

**Arguments:**

```
project_id: The project identifier to analyze.
baseline_id: Optional earlier project for trend-based enhancement.
```

**Returns:**

Per-activity risk scores, risk levels, predicted delay days,
top risk factors, and project-level aggregates.

---

### `extract_benchmarks`

**Extract anonymized benchmark metrics from a schedule.**

```python
extract_benchmarks(project_id: str) -> str
```

Produces aggregate metrics (DCMA scores, float distribution, network
density) with no identifying information (no activity names, WBS text,
or project identifiers).

**Arguments:**

```
project_id: The project identifier.
```

**Returns:**

Anonymized BenchmarkMetrics as JSON.

---

### `run_half_step`

**Run half-step bifurcation analysis per AACE RP 29R-03 MIP 3.4.**

```python
run_half_step(baseline_id: str, update_id: str) -> str
```

Separates schedule delay into progress effect (actual work performance)
and revision effect (logic/plan changes) by creating an intermediate
half-step schedule with only progress applied.

**Arguments:**

```
baseline_id: The earlier (baseline) project identifier.
update_id: The later (update) project identifier.
```

**Returns:**

JSON with progress_effect, revision_effect, total_delay, critical
paths, change classification, and invariant check.

---

### `run_what_if`

**Run a what-if scenario on a schedule.**

```python
run_what_if(project_id: str, adjustments: str = '', iterations: int = 1) -> str
```

Applies percentage-based duration adjustments and re-runs CPM to show
impact on project duration and critical path.  Supports deterministic
(iterations=1) and probabilistic (iterations>1) modes.

**Arguments:**

```
project_id: The project identifier.
adjustments: JSON array of adjustments, e.g.
    '[{"target": "B", "pct_change": 0.20}]' or
    '[{"target": "*", "min_pct": -0.10, "max_pct": 0.30}]'.
iterations: Number of iterations (1=deterministic, >1=probabilistic).
```

**Returns:**

JSON with base/adjusted duration, delta, P-values (if probabilistic),
and per-activity impacts.

---

### `get_scorecard`

**Get a comprehensive schedule scorecard with letter grades.**

```python
get_scorecard(project_id: str) -> str
```

Aggregates DCMA 14-Point, Health Score, Risk Assessment, Logic
Integrity, and Data Completeness into a weighted overall grade (A-F).

**Arguments:**

```
project_id: The project identifier.
```

**Returns:**

JSON with overall_grade, overall_score, dimension scores/grades,
and actionable recommendations.

---

### `level_resources`

**Run resource-constrained scheduling via Serial SGS.**

```python
level_resources(project_id: str, resource_limits: str = '', priority_rule: str = 'late_start') -> str
```

Levels resources by scheduling activities at their earliest feasible
start, respecting both precedence and resource capacity constraints.

**Arguments:**

```
project_id: The project identifier.
resource_limits: JSON array of limits, e.g.
    '[{"rsrc_id": "R1", "max_units": 2.0}]'.
priority_rule: Priority rule (late_start, early_start, float, duration).
```

**Returns:**

JSON with original/leveled duration, extension, activity shifts,
and resource profiles.

---

### `generate_schedule`

**Generate a complete schedule from project parameters.**

```python
generate_schedule(project_type: str = 'commercial', size_category: str = 'medium', project_name: str = 'Generated Project', target_duration_days: float = 0) -> str
```

Creates activities, durations, and logical relationships based on
project type, size category, and optional target duration.

**Arguments:**

```
project_type: commercial, industrial, infrastructure, or residential.
size_category: small, medium, large, or mega.
project_name: Name for the generated project.
target_duration_days: Target duration (0 = auto).
```

**Returns:**

JSON with generated activities, relationships, predicted duration,
and full schedule summary.

---

### `build_schedule_from_description`

**Build a schedule from a natural language project description.**

```python
build_schedule_from_description(description: str) -> str
```

Interprets the description to extract project type, size, and
complexity, then generates a complete schedule.

**Arguments:**

```
description: Natural language project description, e.g.
    "3-story office building, 18 months, steel frame".
```

**Returns:**

JSON with interpreted parameters, generated activity count,
and predicted duration.

---

### `export_xer`

**Export a project schedule to XER format.**

```python
export_xer(project_id: str) -> str
```

Writes the schedule back to Oracle P6 XER format for import into
Primavera P6. Supports round-trip fidelity.

**Arguments:**

```
project_id: The project identifier.
```

**Returns:**

XER file content as a string (first 5000 chars for preview).

---

### `optimize_schedule_es`

**Optimize a resource-constrained schedule using Evolution Strategies.**

```python
optimize_schedule_es(project_id: str, resource_limits: str = '', generations: int = 20) -> str
```

Uses (mu, lambda) ES to find better priority orderings for the
Serial SGS, minimizing project makespan.

**Arguments:**

```
project_id: The project identifier.
resource_limits: JSON array of limits, e.g.
    '[{"rsrc_id": "R1", "max_units": 2.0}]'.
generations: Number of ES generations to run.
```

**Returns:**

JSON with best/greedy duration, improvement, convergence history.

---

### `validate_calendars_tool`

**Validate work calendar definitions for integrity and best practices.**

```python
validate_calendars_tool(project_id: str) -> str
```

Checks default calendar existence, task coverage, hour consistency,
non-standard calendars, and orphaned definitions. Returns a score
(0-100) with letter grade (A-F) and detailed findings.

**Arguments:**

```
project_id: The project identifier.
```

**Returns:**

JSON with score, grade, calendar details, and validation issues.

---

### `compute_delay_attribution_tool`

**Compute delay attribution breakdown by responsible party.**

```python
compute_delay_attribution_tool(project_id: str, baseline_id: str = '') -> str
```

Aggregates delay by Owner, Contractor, Shared, Third Party, and
Force Majeure.  Returns excusable vs non-excusable totals and
per-party driving activities.

**Arguments:**

```
project_id: The current/update schedule identifier.
baseline_id: Optional baseline schedule for comparison.
```

**Returns:**

JSON with per-party breakdown and excusable/non-excusable totals.

---

### `get_schedule_view_tool`

**Get schedule layout data for Gantt visualization.**

```python
get_schedule_view_tool(project_id: str, baseline_id: str = '') -> str
```

Returns WBS tree, flattened activities with dates/float/status,
relationships, and summary metrics.  Optionally includes baseline
dates for comparison when baseline_id is provided.

**Arguments:**

```
project_id: The schedule identifier.
baseline_id: Optional baseline schedule for comparison.
```

**Returns:**

JSON with project metadata, WBS tree, activities, relationships, summary.

---

Regenerate this catalog with: `python3 scripts/generate_mcp_catalog.py`
