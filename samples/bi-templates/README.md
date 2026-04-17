# BI Templates

Reference templates for connecting Power BI, Tableau, and Looker to the MeridianIQ BI connector (`/api/v1/bi/*`, shipped in v3.7.0). Each template wraps existing endpoints — no server-side changes are required.

## Endpoints consumed

| Endpoint | Cardinality | Use |
|---|---|---|
| `GET /api/v1/bi/projects` | 1 row per project | Portfolio KPIs (DCMA, health, CPM duration, negative float count) |
| `GET /api/v1/bi/dcma-metrics` | 14 rows per project | DCMA 14-point breakdown for benchmarking |
| `GET /api/v1/bi/activities?project_id=...` | 1 row per activity | Schedule detail with CPM-derived float / criticality |

All responses follow the shape `{items: [...], pagination: {limit, offset, total, returned, has_next}}`. Default `limit=100`, max `limit=500`. Pagination loops should keep requesting while `has_next == true`.

## Authentication

The `/bi/*` endpoints use `optional_auth`: unauthenticated requests return projects owned by the anonymous/default store, authenticated requests scope to the user. For multi-tenant deployments, pass the JWT as a bearer token:

```
Authorization: Bearer <supabase-jwt>
```

Each template exposes an `ApiToken` parameter — leave it blank for anonymous use.

## Base URL

- Hosted: `https://meridianiq.vitormr.dev`
- Self-hosted default: `http://localhost:8080`

Templates use a `BaseUrl` parameter; swap it once per file.

## Tool matrices

| Template | File | What it produces |
|---|---|---|
| Power BI | [powerbi/meridianiq.pq](powerbi/meridianiq.pq) | Three named M queries with pagination loop |
| Power BI | [powerbi/measures.dax](powerbi/measures.dax) | DAX measures (pass rate, critical ratio, portfolio score) |
| Tableau | [tableau/meridianiq.tds](tableau/meridianiq.tds) | Tableau Data Source (JSON connector) |
| Looker | [looker/meridianiq.model.lkml](looker/meridianiq.model.lkml) | Model with three explores |
| Looker | [looker/meridianiq.view.lkml](looker/meridianiq.view.lkml) | Views with dimensions + measures |

See each subdirectory's `README.md` for setup steps.

## Refresh cadence

DCMA, health, and CPM fields are computed on-request from stored XER data — no staleness window. Pick a refresh interval in the BI tool that matches how often new schedules are uploaded (typical: daily for active projects, weekly for portfolio views).

## Limitations

- Looker requires a SQL connection; the `.lkml` here assumes you expose the BI endpoints via a CSV/JSON extract job or point Looker at the Supabase Postgres read replica. See `looker/README.md`.
- Tableau's JSON connector works best for snapshots; for live dashboards consider the Supabase Postgres connection.
- Power BI's REST connector handles pagination natively once the M function is imported.

## License

Templates are MIT-licensed, same as MeridianIQ. Copy, modify, redistribute freely.
