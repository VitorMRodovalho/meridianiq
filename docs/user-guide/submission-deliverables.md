# Submission Deliverables

Step-by-step guide for producing the four submission-ready artefacts MeridianIQ generates: two forensic PDFs (SCL Protocol and AACE RP 29R-03 §5.3), one billing continuation-sheet Excel (AIA G703), and one payment-certificate PDF (AIA G702).

These are the artefacts most commonly requested by owners, architects, dispute-resolution tribunals, and construction lawyers. Each section covers the standard being implemented, prerequisites, UI path, API example, and common customisations.

## Which deliverable, when

| Situation | Deliverable | Standard |
|---|---|---|
| UK / Commonwealth contractual claim | SCL Protocol PDF | SCL D&D Protocol 2nd ed. (2017), Appendix B |
| US forensic submission (TCC / litigation) | AACE §5.3 PDF | AACE RP 29R-03, §5.3 |
| Monthly / milestone progress billing — schedule of values | AIA G703 Excel | AIA Document G703™ |
| Monthly / milestone progress billing — cover certificate | AIA G702 PDF | AIA Document G702™ |

The two billing artefacts are usually produced together — G702 is the cover sheet that sums up a paired G703. The two forensic PDFs are typically chosen based on the forum (SCL for UK-aligned adjudication; AACE for US contract-standard forensic analysis).

## Common prerequisites

1. **Upload at least one XER file** via `/upload` (UI) or `POST /api/v1/upload` (API). Note the `project_id`.
2. For forensic PDFs, **upload a baseline XER** as well and note its `project_id` — submissions without a baseline render a subset of sections (factual narrative only for SCL; executive summary + scorecard for AACE §5.3).
3. For billing artefacts, **upload a CBS Excel** via the `/cost` page and note the returned `snapshot_id` from `/api/v1/projects/{id}/cost/snapshots`.
4. For G702 specifically, have these contractual numbers ready: **original contract sum**, cumulative **previous certificates for payment**, and any **change order additions / deductions** (broken into prior-months and this-month).

## 1. SCL Protocol Delay Analysis PDF

**Standard:** Society of Construction Law Delay and Disruption Protocol, 2nd ed. (2017), Appendix B — Records. Methodology aligned with AACE RP 29R-03 MIP 3.3 for contemporaneous period analysis.

**When to use:** Claim preparation under English / Commonwealth contract law, or any forum that expects SCL-style reasoning (critical path evolution, responsibility attribution, concurrency analysis).

**Prerequisites:** One current schedule (`project_id`). Optionally a baseline (`baseline_id`) — without it, forensic timeline and concurrency sections render but are shallower.

**UI:** **Reports → select project → generate `scl_protocol`** once the card shows as ready.

**API:**

```bash
curl -X POST "$BASE/api/v1/reports/generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "project_id": "<current-id>",
    "report_type": "scl_protocol",
    "baseline_id": "<baseline-id>"
  }'
# → { "report_id": "...", "report_type": "scl_protocol", ... }

curl -OJ "$BASE/api/v1/reports/$REPORT_ID/download" \
  -H "Authorization: Bearer $JWT"
```

**Output sections:** Factual narrative → contractual milestone status → critical path evolution → contemporaneous period analysis (windows) → responsibility attribution → concurrency assessment → records appendix.

**Common customisations:** Pass `baseline_id` to populate the forensic timeline; otherwise the Windows and Concurrency sections degrade to placeholders explaining the missing baseline.

## 2. AACE RP 29R-03 §5.3 Forensic Report PDF

**Standard:** AACE International Recommended Practice 29R-03 — Forensic Schedule Analysis. §5.3 prescribes the documentation structure for forensic-analysis submissions.

**When to use:** US forensic submissions, TCC-style tribunals, or any contract requiring AACE-aligned methodology documentation. Good when the contract or specification names AACE RP 29R-03 explicitly.

**Prerequisites:** One current schedule. Optional baseline (unlocks timeline + comparison sections). Pass `options.bifurcated: true` to run MIP 3.4 half-step analysis and include progress-vs-revision delay separation.

**UI:** **Reports → select project → generate `aace_29r03`**.

**API:**

```bash
curl -X POST "$BASE/api/v1/reports/generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "project_id": "<current-id>",
    "report_type": "aace_29r03",
    "baseline_id": "<baseline-id>",
    "options": { "bifurcated": true }
  }'
```

**Output sections:** Executive summary → project background → methodology detail (with MIP 3.3 or 3.4 cross-reference) → schedule updates → contemporaneous period analysis → half-step bifurcation (if `bifurcated: true`) → scorecard → responsibility attribution → concurrency → supporting records.

**Common customisations:** `options.bifurcated` toggles the MIP 3.4 split. Pair this report with a contractor-signed narrative as an appendix when submitting.

## 3. AIA G703 Continuation Sheet (Excel)

**Standard:** AIA Document G703™ — Continuation Sheet that accompanies a G702 Application for Payment. One row per schedule-of-values line item.

**When to use:** Monthly or milestone progress billing under an AIA contract (A101, A102, A103, A201). Always paired with a G702 — the G703 is the line-item breakdown; the G702 is the cover summary.

**Prerequisites:** A CBS snapshot — upload your CBS Excel via the `/cost` page, then note the `snapshot_id`.

**UI:** Currently exposed via the paired G702 page (**Cost Integration → AIA G702 Certificate**). The G703 Excel is also downloadable directly via the API endpoint below.

**API:**

```bash
curl -OJ "$BASE/api/v1/projects/$PROJECT_ID/export/aia-g703?snapshot_id=$SNAP&retainage_pct=0.10&application_number=3&period_to=2026-04-30" \
  -H "Authorization: Bearer $JWT"
```

**Output columns:** A (Item No.), B (Description of Work), C (Scheduled Value), D (From Previous Application), E (This Period), F (Materials Presently Stored), G = D+E+F (Total Completed & Stored), H = G/C (% Complete), I = C−G (Balance to Finish), J (Retainage).

**Common customisations:**

- `retainage_pct` — fractional retainage applied uniformly to all lines (default `0.10` = 10 %).
- `application_number` — billing sequence (1, 2, 3, …). Embedded in the filename.
- `period_to` — end-of-period date string (e.g. `2026-04-30`) shown in the header.
- To inject per-line completion percentages, use the paired G702 page which derives the G703 internally and surfaces the form fields.

## 4. AIA G702 Application and Certificate for Payment (PDF)

**Standard:** AIA Document G702™ — Application and Certificate for Payment. Cover certificate paired with a G703 continuation sheet.

**When to use:** Alongside every G703 — the G702 is the one-page summary with the payment request, contractor's certification, and architect's certification.

**Prerequisites:** CBS snapshot (same as G703), plus contractual inputs: `original_contract_sum`, `previous_certificates_total`, and a `change_order` summary block (prior and current period additions / deductions).

**UI:** **Cost Integration → AIA G702 Certificate →** pick project and snapshot, fill contract fields → **Generate G702 PDF**. All G702-specific inputs are exposed on the form.

**API:**

```bash
curl -X POST "$BASE/api/v1/reports/generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $JWT" \
  -d '{
    "project_id": "<current-id>",
    "report_type": "aia_g702",
    "options": {
      "snapshot_id": "<cbs-snapshot-id>",
      "original_contract_sum": 10000000,
      "previous_certificates_total": 2500000,
      "application_number": 3,
      "period_to": "2026-04-30",
      "retainage_pct": 0.10,
      "retainage_stored_fraction": 0.0,
      "change_order": {
        "prior_additions": 50000,
        "prior_deductions": 0,
        "this_period_additions": 25000,
        "this_period_deductions": 0
      },
      "owner": "Acme Owner LLC",
      "contractor": "BuildCo",
      "architect": "DesignStudio"
    }
  }'
```

**Output lines:** 1 Original Contract Sum → 2 Net change by Change Orders → 3 Contract Sum To Date → 4 Total Completed & Stored → 5a/5b Retainage split → 6 Total Earned Less Retainage → 7 Less Previous Certificates → 8 Current Payment Due → 9 Balance to Finish. Plus contractor and architect certification blocks (blank for manual signature) and an appendix summary of the paired G703.

**Common customisations:**

- `retainage_stored_fraction` — fraction of total retainage allocated to stored materials (5b vs. 5a). Default `0.0` sends all retainage to Completed Work.
- `previous_certificates_total` — cumulative amount paid on prior applications. For the first application, pass `0`.
- `change_order` — summary block, not per-CO detail. If you need per-CO audit, attach a separate schedule.

## Recommended submission sequence

1. **Prepare:** Upload baseline and current schedules; upload CBS Excel if billing is in scope.
2. **Validate:** Run DCMA 14-Point (`/validation`) and review — schedules with score below 80 weaken any forensic submission.
3. **Generate:** For claims, pick one of SCL Protocol or AACE §5.3. For billing, generate the G702 + G703 pair.
4. **Review:** Download, open in reader / Excel, check per-line figures, attribution labels, and signature blocks.
5. **Sign & deliver:** PDFs are generated with empty signature lines for manual execution. Excel retainage / CO rows are editable.

## Related guides

- [Analysis Workflow](analysis-workflow.md) — the forensic pipeline that fills the submission PDFs.
- [Cost Integration](cost-integration.md) — how to upload CBS and produce snapshots.
- [BI Dashboards](bi-dashboards.md) — Power BI / Tableau / Looker templates for portfolio-level views (non-submission).
