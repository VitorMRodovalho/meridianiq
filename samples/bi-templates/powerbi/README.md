# Power BI template

Build a portfolio dashboard from MeridianIQ in under ten minutes. No custom connector needed — Power BI consumes `/api/v1/bi/*` through the built-in Web.Contents M function.

## 1. Set up parameters

Power BI Desktop → **Home → Transform data → Manage Parameters → New Parameter**. Create two:

| Name | Type | Required | Current value |
|---|---|---|---|
| `BaseUrl` | Text | Yes | `https://meridianiq.vitormr.dev` (or your self-hosted URL) |
| `ApiToken` | Text | Yes | Supabase JWT, or empty string `""` for anonymous |

## 2. Paste the M script

**Home → Get data → Blank query**. Right-click the new query → **Advanced Editor**. Replace the stub with the full contents of [`meridianiq.pq`](meridianiq.pq). Done → Close.

You'll see a query with a record output containing `Projects`, `DCMAMetrics`, and `ActivitiesFn`.

## 3. Expose the tables

Right-click the record query → **Reference** → rename the reference to `Projects`, then click the Record cell → **Into Table**. Repeat for `DCMAMetrics`. Each becomes a loadable table.

For `Activities`, create a blank query and write:

```m
let
    result = MeridianIQ[ActivitiesFn]("<project_id>")
in
    result
```

Replace `<project_id>` with the target project. For multi-project activity loads, duplicate the query per project or use a driver table + Table.Combine.

## 4. Load and set relationships

**Home → Close & Apply**. Once loaded, **Model view**:

- `Projects[project_id]` → `DCMAMetrics[project_id]` (one-to-many, single direction)
- `Projects[project_id]` → `Activities[project_id]` (one-to-many, single direction)

## 5. Paste measures

Open [`measures.dax`](measures.dax). For each block, in the report view → right-click the table noted → **New measure** → paste (without the leading `// label` line) → Enter. Apply the format hinted in the comment.

## 6. Recommended visuals

| Page | Visuals | Uses |
|---|---|---|
| Portfolio | KPI cards (`Avg DCMA Score`, `DCMA Green Share`, `Health Green Share`), bar chart of `dcma_score` by project, scatter of `activity_count` vs `critical_path_length_days` | Projects |
| DCMA | Matrix (metric_name × project_name) with `passed` heatmap coloring, `DCMA Pass Rate` card | DCMAMetrics |
| Detail | Drill-through page: table of Activities filtered by `project_id`, column `cpm_total_float` with conditional formatting (red if < 0) | Activities |

## 7. Refresh cadence

Web.Contents respects Power BI refresh settings — configure on publish. Daily refresh is usually enough; computation on the server side is deterministic from stored XER state.

## Gotchas

- Web.Contents + dynamic URLs hit Power BI Service's "dynamic data source" error on refresh. The M script avoids this by using a static base URL + relative path construction. If you fork the script, keep the call signature of `Web.Contents(_BaseUrl, [ RelativePath = path, Query = qs ])`-compatible patterns.
- Anonymous access will land on the default/anonymous project scope in your deployment. For per-user data, the `ApiToken` parameter must hold a valid Supabase JWT. Refresh tokens are not supported — long-lived service-role keys are discouraged for BI service. Prefer extract jobs + scheduled token rotation.
- Pagination defaults to 500 per page, 200-page ceiling (100 000 rows). Raise `MaxPages` in the M script if you have a larger portfolio.
