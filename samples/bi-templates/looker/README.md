# Looker template

Looker needs a SQL connection — it does not consume REST APIs natively. Two setups are supported:

## Option A — Postgres connection via Supabase (recommended for live data)

1. **Admin → Connections → Add connection**
   - Name: `meridianiq_pg`
   - Dialect: PostgreSQL 9.3+
   - Host: `<project-ref>.supabase.co`, Port: `6543` (pooler)
   - Database: `postgres`, Username: read-only role, Password: from vault
   - SSL: required
2. Grant the read-only role `SELECT` on the tables referenced by the views: `projects`, `activities`, `schedules`, plus any DCMA/health snapshot tables you materialise (see Option B).
3. Import [`meridianiq.model.lkml`](meridianiq.model.lkml) and [`meridianiq.view.lkml`](meridianiq.view.lkml) into your LookML project. Adjust `sql_table_name` on each view if your schema names differ.

⚠️ The default view names assume **extract tables** (`meridianiq_bi_projects`, etc.) populated from the `/bi/*` endpoints. If you prefer to derive DCMA / health / CPM in pure SQL, replace the views with native-type derived tables that call the underlying normalised P6 tables. That is more work and the methodology-parity burden sits with you.

## Option B — Extract job populating warehouse tables

Run a small ETL that snapshots each `/bi/*` surface into Postgres / BigQuery / Snowflake tables Looker reads. Schedule via cron, GitHub Actions, or Supabase Edge Function.

Example `meridianiq-bi-sync.py` pseudocode:

```python
import httpx, os, psycopg
BASE = "https://meridianiq.vitormr.dev"
TOKEN = os.environ["SUPABASE_JWT"]

def fetch_all(path: str) -> list[dict]:
    rows, offset = [], 0
    while True:
        r = httpx.get(
            f"{BASE}{path}",
            params={"limit": 500, "offset": offset},
            headers={"Authorization": f"Bearer {TOKEN}"},
        ).json()
        rows.extend(r["items"])
        if not r["pagination"]["has_next"]:
            break
        offset += 500
    return rows

with psycopg.connect(os.environ["PG_URL"]) as conn:
    conn.execute("TRUNCATE meridianiq_bi_projects")
    # upsert rows ...
```

Run nightly. Looker's `datagroup: meridianiq_daily` in the model picks up the refresh.

## 3. Recommended explores

The model exposes three explores:

| Explore | Typical question |
|---|---|
| `projects` | "Portfolio pass/fail split, avg DCMA, negative-float activity count by project" |
| `dcma_metrics` | "Which DCMA metric fails most often across projects? Where are we trending?" |
| `activities` | "Drill into one project — which activities are on the critical path? How much negative float?" |

Pass/fail share, averages, and counts are pre-defined as measures. Dimensions cover every column returned by the REST surface.

## Gotchas

- Supabase pooler is on **6543**, not 5432 — Looker's default port picker will try 5432 first. Override it.
- Do **not** use the `service_role` key as the Postgres password. It bypasses RLS and exposes every tenant. Create a dedicated read-only role with SELECT on the specific BI extract tables only.
- `value_format_name: percent_1` renders `0.854` as `85.4%`. If your extract stores percentages as `85.4`, drop the `1.0 *` scaling in the measure and switch `value_format_name` to `decimal_1`.
- `datagroup` caching defaults to 24h. Reduce for active-update portfolios.
