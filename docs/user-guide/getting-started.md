# Getting Started

Five-minute walkthrough: upload a P6 XER, see the schedule validated (DCMA), computed (CPM), and scored (Health). Works against the hosted deployment or a local dev server.

## Prerequisites

- A Supabase account (free tier) if running locally — not needed to use the hosted deployment
- A P6 XER file. If you don't have one, use `tests/fixtures/sample.xer` from the repository
- Modern browser with cookies enabled

## 1. Sign in

Open [meridianiq.vitormr.dev](https://meridianiq.vitormr.dev) and sign in with Google, LinkedIn, or Microsoft. The backend issues a Supabase JWT that's auto-attached to all subsequent API calls.

Running locally:

```bash
# Backend
pip install -e ".[dev]"
python -m uvicorn src.api.app:app --reload --port 8080

# Frontend (separate terminal)
cd web && npm install && npm run dev -- --port 5173
```

Then open [http://localhost:5173](http://localhost:5173).

## 2. Upload an XER

Go to **Upload** in the sidebar. Drop your `.xer` file into the drop zone, or click to browse. The file uploads and is parsed immediately (streaming parser — even 10K-activity files land in <2s).

What the parser extracts:

- 17+ Pydantic models covering PROJECT, PROJWBS, TASK, TASKPRED, TASKRSRC, RSRC, CALENDAR, CALEXCEPTION, and more
- Composite keys (`proj_id.task_id`) to avoid cross-project collisions
- Automatic encoding detection (UTF-8, Windows-1252, Latin-1) — P6 schedule exports vary

After parsing you'll see a success panel with activity / relationship / WBS / calendar counts and two action buttons: **View Schedule** and **Open Scorecard**.

## 3. See your schedule on the Gantt

Click **View Schedule** (or navigate to **Schedule** in the sidebar) and pick the project you just uploaded. The Gantt renders with:

- WBS tree on the left (collapsed by default for projects > 100 activities)
- Color-coded bars (red = critical, blue = in progress, green = complete, grey = not started)
- Data date marker (amber dashed line)
- Float bars (amber extension from early finish to late finish)
- Dependency lines (toggle via the toolbar)

See [Schedule Viewer](schedule-viewer.md) for the full feature tour.

## 4. Validate against DCMA 14-Point

Back on the project, open the **DCMA** tab or hit the endpoint:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://meridianiq.vitormr.dev/api/v1/projects/$PROJECT_ID/validation
```

You'll get 14 check results (missing logic, negative float, high float, excess lags, etc.) with thresholds, pass/fail, and a composite score. Red badges indicate fails, amber warnings, green passes.

## 5. Composite Health Score

The Health Score combines DCMA structural quality, float health, logic integrity, and (if you have a baseline) trend direction into a 0–100 composite. See **Health** in the sidebar or:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://meridianiq.vitormr.dev/api/v1/projects/$PROJECT_ID/health
```

A rating of A–F plus a trend arrow lands on the dashboard.

## 6. What's next?

- Upload a second revision of the same project → triggers **Compare** (multi-layer matching + manipulation detection) and **Float Trends**.
- Upload a **CBS Excel** → triggers cost-schedule correlation. See [Cost Integration](cost-integration.md).
- Configure the **MCP server** and query your schedule from Claude Code. See [MCP + Claude Integration](mcp-integration.md).
- Ask natural-language questions: open `/ask` and type "Which activities have negative float?"

The full forensic workflow (DCMA → Compare → CPA → TIA → EVM → Risk) is walked through in [Analysis Workflow](analysis-workflow.md).
