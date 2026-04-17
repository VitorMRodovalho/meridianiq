# BI Dashboards

Connect Power BI, Tableau, or Looker to MeridianIQ's portfolio data via the `/api/v1/bi/*` connector (shipped in v3.7.0). Ready-to-use templates live in [`samples/bi-templates/`](../../samples/bi-templates/README.md).

## When to use this

Pick BI when you need:

- Cross-project portfolio rollups beyond the built-in `/programs/{id}/rollup` 8-KPI dashboard
- Custom drill-down hierarchies (business unit → portfolio → project → activity)
- Integration with existing corporate BI stack (e.g. governance, row-level security managed in your BI tenant)
- Non-MeridianIQ data joined with schedule KPIs (cost actuals from ERP, safety KPIs, weather overlays)

For standard analyses built in, use the MeridianIQ UI directly — the BI surface is for custom aggregation and blending.

## What the connector exposes

| Endpoint | Purpose | Cardinality |
|---|---|---|
| `/api/v1/bi/projects` | Portfolio KPIs (DCMA, health, CPM length, negative float count) | 1 row / project |
| `/api/v1/bi/dcma-metrics` | DCMA 14-point breakdown | 14 rows / project |
| `/api/v1/bi/activities?project_id=…` | Activity-level detail with CPM float + criticality | 1 row / activity |

All responses are flat (no nested objects), paginated with `limit` / `offset` (default 100, max 500), and return a `pagination.has_next` flag so your BI tool can loop.

## Pick your tool

### Power BI (recommended)

Native REST pagination via Power Query M. Templates: [`samples/bi-templates/powerbi/`](../../samples/bi-templates/powerbi/README.md)

- Copy [`meridianiq.pq`](../../samples/bi-templates/powerbi/meridianiq.pq) into a blank query
- Set `BaseUrl` and `ApiToken` parameters
- Load three tables (Projects, DCMAMetrics, Activities)
- Paste [`measures.dax`](../../samples/bi-templates/powerbi/measures.dax) for portfolio-level KPIs
- **Setup time**: ~10 min

### Tableau

JSON snapshot workflow. Templates: [`samples/bi-templates/tableau/`](../../samples/bi-templates/tableau/README.md)

- `curl` + `jq` pull each endpoint to local JSON files
- Open [`meridianiq.tds`](../../samples/bi-templates/tableau/meridianiq.tds); Tableau parses the schema with two calc fields pre-wired
- Schedule the curl as a cron for refresh
- **Setup time**: ~15 min (plus 5 min to configure refresh)

### Looker

SQL connection required — Looker does not read REST directly. Two setups:

- **Live** — Postgres connection to Supabase (read-only role, port 6543)
- **Extract** — cron-run Python script lands `/bi/*` into warehouse tables Looker reads

Templates: [`samples/bi-templates/looker/`](../../samples/bi-templates/looker/README.md). Includes `meridianiq.model.lkml` with three explores and `meridianiq.view.lkml` with measures.

## Authentication

The `/bi/*` endpoints use `optional_auth`:

- **Anonymous**: returns the anonymous-scoped store contents (useful for demos or single-tenant self-host)
- **Authenticated**: pass `Authorization: Bearer <supabase-jwt>` — scopes to the user

For multi-tenant BI deployments, mint a long-lived JWT with a read-only role and rotate on a schedule. Do **not** use the Supabase `service_role` key in BI — it bypasses RLS.

## Refresh cadence

DCMA, health, and CPM values are computed on-request from stored XER state — there is no staleness window on the server. Pick a refresh interval in your BI tool that matches your workflow:

| Scenario | Recommended refresh |
|---|---|
| Daily project status meeting | Daily, early morning |
| Weekly portfolio review | Weekly, Sunday night |
| Forensic / claim analysis | On-demand (manual) |

## Limitations

- The BI connector recomputes CPM / DCMA / health per project per request. Portfolios of 500+ projects with authenticated pagination may take 30-60s to fully load. Extract to warehouse for dashboards over large fleets.
- No authentication scoping across teams beyond user-owned projects. For team-level BI, either use the Postgres read replica with your own access policies or stand up a dedicated service account per team with JWT issuance.
- Schema is stable within a release but may evolve across majors. Version-pin your BI template against the MeridianIQ version you deployed.

## Related

- [Analysis Workflow](analysis-workflow.md) — forensic pipeline against a single project
- [Cost Integration](cost-integration.md) — CBS + S-Curve narratives (separate surface from `/bi/*`)
- [API Reference](../api-reference.md) — full endpoint catalog
