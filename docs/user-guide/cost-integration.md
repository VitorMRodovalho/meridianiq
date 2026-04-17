# Cost Integration

Upload a CBS (Cost Breakdown Structure) Excel, correlate it with the schedule WBS, persist snapshots over time, and generate budget-vs-schedule narratives. Shipped in v3.5 (parse + UI) and v3.6 (persistence + snapshots API).

## Data model

MeridianIQ persists CBS data in an ERP-ready schema (migration 019, AACE RP 10S-90 terminology):

- `erp_sources` — one row per upload, tracks origin (manual / Unifier / SAP PS / Kahua / eBuilder / InEight / Procore)
- `cbs_elements` — the CBS hierarchy with self-referential parent links
- `cost_snapshots` — point-in-time financials per CBS element (original budget, current budget, committed, actual, EAC, BCWS / BCWP / ACWP for EVM)
- `cost_time_phased` — monthly period buckets for S-curve generation
- `cbs_wbs_mappings` — splits one CBS element across multiple WBS elements with `allocation_pct`
- `change_orders` — pending / approved / rejected change tracking
- `obs_elements` + `obs_cbs_assignments` — who is responsible for each cost element

All monetary fields use `NUMERIC(18,2)` to avoid float-precision drift.

## Excel format expected

`parse_cbs_excel` recognises three sheet patterns:

1. **"Summary by CBS"** — CBS hierarchy with estimate, contingency, escalation, WBS code mapping. Header row must contain `CBS-Lvl1`, `CBS-Lvl2`, `Scope`, `WBSE L1`, `DJV Estimate`, `DJV Contingency (25%)`, `Escalation`, `Design Package`. A row with `CBS-Lvl1 = "Total"` sets program totals.
2. **"Summary by WBSE"** — WBS budget totals, two-column rows starting at row 4 (`wbs_code`, `total_budget`).
3. **Mapping sheet** (`Sheet1` / `Mapping` / `CBS-WBS`) — free-form rows containing CBS codes matching `C.XX.XXXXXX`. The parser detects these and reads the cost category from the preceding cell and the WBS Level 1 from the following cell.

If your Excel doesn't match this pattern, either rename your sheets or adapt `_parse_cbs_summary` / `_parse_wbs_summary` in `src/analytics/cost_integration.py`.

## Upload & persist

Via the UI: open **Cost** in the sidebar, pick a schedule project, and drop your CBS Excel.

Via API:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@q2-budget.xlsx" \
  "https://meridianiq.vitormr.dev/api/v1/cost/upload?project_id=$PROJECT_ID"
```

Response (abridged):

```json
{
  "filename": "q2-budget.xlsx",
  "snapshot_id": "cost-0003",
  "project_id": "proj-...",
  "budget_date": "2026-06-30",
  "total_budget": 4250000000.00,
  "total_contingency": 1062500000.00,
  "total_escalation": 212500000.00,
  "program_total": 5525000000.00,
  "cbs_element_count": 142,
  "wbs_budget_count": 38,
  "mapping_count": 87,
  "insights": [
    "Total estimate: $4.25B (construction: $3.12B = 73%)",
    "WBS 100123: $1,730M budget",
    "Contingency: 25% of estimate",
    "CBS-WBS mappings: 87 cost categories mapped"
  ],
  "cbs_elements": [...],
  "wbs_budgets": [...],
  "cbs_wbs_mappings": [...]
}
```

Pass `project_id=` to persist the snapshot; omit it to receive a parse-only response (useful for dry-running a new Excel format).

## List prior snapshots

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "https://meridianiq.vitormr.dev/api/v1/projects/$PROJECT_ID/cost/snapshots"
```

Returns the newest-first list of snapshots with totals, element counts, and the auto-generated `budget_date`. Useful when you want to pick a prior snapshot to compare against in v3.7 (compare endpoint is on the roadmap).

## Insights emitted by the parser

`_generate_insights` in `src/analytics/cost_integration.py` produces human-readable one-liners:

- Total estimate with construction % (e.g. `Total estimate: $4.25B (construction: $3.12B = 73%)`)
- Top 3 WBS elements by budget
- Contingency as % of estimate
- Mapping coverage count

These also land in the dashboard KPI tiles.

## Narrative PDF

After a CBS upload you can generate a narrative PDF that weaves schedule performance together with cost context:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"project_id": "'$PROJECT_ID'", "report_type": "narrative", "baseline_id": "'$BASELINE_ID'"}' \
  https://meridianiq.vitormr.dev/api/v1/reports/generate
```

The response contains a `report_id`; download with:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  -o narrative.pdf \
  https://meridianiq.vitormr.dev/api/v1/reports/$REPORT_ID/download
```

The narrative combines schedule view summary, scorecard, and optional comparison into severity-tagged sections (info / warning / critical) rendered via WeasyPrint. See [Analysis Workflow §8](analysis-workflow.md#8-narrative-report--claim-ready-write-up) for the full flow.

## EVM from CBS data

Once CBS data is persisted, you can run EVM on the schedule to get SPI / CPI / EAC. EVM reads resource assignment cost data from the schedule itself; CBS is used for budget context (BAC, management reserve, approved change orders from `change_orders`).

See [Analysis Workflow §6](analysis-workflow.md#6-evm--how-does-cost-compare-to-schedule-progress) for the EVM pipeline.

## Troubleshooting

- **Parse returns 0 CBS elements** — your Excel sheet names don't match. Open a bug with a sanitized fixture; we'll extend the parser patterns.
- **`snapshot_id` is empty** — the `project_id` query parameter was not provided, or the Supabase write failed silently. Check server logs (`save_cost_upload` is best-effort and logs on failure).
- **Supabase RLS denies the insert** — make sure the project is owned by the authenticated user. CBS tables inherit project ownership via `user_id` check.
- **Excel bytes > 50 MB** — the endpoint caps payloads at 50 MB. Split the workbook or strip unused sheets.

## Related

- [Methodology: cost_integration](../methodologies.md#cost-integration--cost-integration)
- [Migration 019 schema](../../supabase/migrations/019_erp_cost_tables.sql)
- [Analysis Workflow §8 — Narrative report](analysis-workflow.md#8-narrative-report--claim-ready-write-up)
