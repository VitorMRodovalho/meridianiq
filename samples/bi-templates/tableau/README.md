# Tableau template

Tableau's built-in Web Data Connector stack doesn't loop paginated REST APIs without custom JavaScript. The recommended pattern is **extract the JSON once, point Tableau at the file**, and refresh the extract on a schedule (cron, Supabase Edge Function, or CI).

For live dashboards over large portfolios, use the Supabase Postgres connection directly instead.

## Option A — JSON snapshot (covered by this template)

### 1. Pull the data

```bash
curl -H "Accept: application/json" \
     "https://meridianiq.vitormr.dev/api/v1/bi/projects?limit=500" \
     | jq '.items' > projects.json
```

For authenticated multi-tenant use:

```bash
curl -H "Accept: application/json" \
     -H "Authorization: Bearer $SUPABASE_JWT" \
     "https://meridianiq.vitormr.dev/api/v1/bi/projects?limit=500" \
     | jq '.items' > projects.json
```

Repeat for `/dcma-metrics` → `dcma-metrics.json` and per-project `/activities?project_id=...` → `activities-<pid>.json` if you want those sheets.

### 2. Open the .tds

Place [`meridianiq.tds`](meridianiq.tds) and `projects.json` in the same directory. Double-click the .tds — Tableau Desktop opens with the schema and two calculated fields (`DCMA Pass Rate`, `Is Green (DCMA)`) pre-defined.

### 3. Recommended sheets

| Sheet | Rows | Columns | Marks |
|---|---|---|---|
| Portfolio overview | `name` | `SUM(activity_count)` | Color: `Is Green (DCMA)` |
| DCMA scatter | `SUM(activity_count)` | `AVG(dcma_score)` | Tooltip: project name, health rating |
| Health distribution | `health_rating` | `CNT(project_id)` | Size: negative float count |

### 4. Refresh

Right-click the data source → **Extract → Refresh**. Schedule via `crontab` + the CLI pull above, or use Tableau Prep.

## Option B — Supabase Postgres live connection

1. Tableau Desktop → **Data → New data source → PostgreSQL**
2. Server: `<project-ref>.supabase.co`, Port: `6543` (pooler, not 5432), Database: `postgres`, Schema: `public`
3. Credentials: use a read-only Postgres role; do **not** use the service-role key.
4. Tables to pull: `projects`, `activities`, `schedules` (see `supabase/migrations/*.sql` for the authoritative schema).

This bypasses the `/bi/*` connector's computed fields (DCMA / health / CPM) — you'll need to replicate those in custom SQL if the dashboard needs them.

## Gotchas

- Tableau's JSON connector parses nested structures to a flat schema on import. The `/bi/*` endpoints are already flat, so no schema re-mapping is needed.
- Date fields arrive as ISO-8601 strings; the .tds casts them to `date`. If your locale surfaces parse issues, use `DATEPARSE("yyyy-MM-dd", [data_date])`.
- The `pagination.total` caps at 500 per page in the sample curl; for portfolios > 500 projects, add `offset=500, offset=1000, ...` runs and concatenate the JSON with `jq -s 'add'`.
