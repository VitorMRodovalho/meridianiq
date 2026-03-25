# MIT License
# Copyright (c) 2026 Vitor Maia Rodovalho
"""Generate a third schedule snapshot for forensic analysis testing.

Produces ``sample_update2.xer`` with deliberate changes from the second update
``sample_update.xer`` (data date 2024-07-15 -> 2024-08-15):

- Data date advanced to 2024-08-15
- More activities completed (progress advanced further)
- 1 additional activity added (ACT-033 / A7030 "Punchlist Verification")
- 1 activity deleted (T-026 Landscaping -- was non-critical)
- 2 activities with further duration changes (T-028, T-025)
- Completion date pushed back ~10 days from sample_update (deliberate delay)
- Additional float consumption across remaining activities
"""
from __future__ import annotations

from pathlib import Path


def _tab(*parts: str) -> str:
    """Join parts with tabs."""
    return "\t".join(parts)


def generate_sample_update2_xer(output_path: str | Path | None = None) -> Path:
    """Generate a third schedule snapshot XER file and return its path.

    Args:
        output_path: Where to write the file. Defaults to
            ``tests/fixtures/sample_update2.xer`` relative to this script.

    Returns:
        Path to the generated file.
    """
    if output_path is None:
        output_path = Path(__file__).parent / "sample_update2.xer"
    else:
        output_path = Path(output_path)

    lines: list[str] = []

    def add(line: str) -> None:
        lines.append(line)

    # -- ERMHDR (data date advanced to 2024-08-15) --------
    add(_tab("ERMHDR", "22.0", "yyyy-mm-dd", "USD", "sample_update2.xer", "admin", "2024-08-15"))

    # -- CALENDAR (unchanged) -----------------------------
    add(_tab("%T", "CALENDAR"))
    add(_tab("%F", "clndr_id", "clndr_name", "day_hr_cnt", "week_hr_cnt", "clndr_type", "default_flag"))
    add(_tab("%R", "CAL-01", "5-Day Work Week", "8", "40", "CA_Base", "Y"))
    add(_tab("%R", "CAL-02", "7-Day Calendar", "8", "56", "CA_Base", "N"))

    # -- PROJECT (data date advanced) ---------------------
    add(_tab("%T", "PROJECT"))
    add(_tab("%F", "proj_id", "proj_short_name", "last_recalc_date", "plan_start_date", "plan_end_date", "scd_end_date", "sum_data_date"))
    add(_tab("%R", "PROJ-001", "Sample Construction", "2024-08-15 08:00", "2024-01-02 08:00", "2024-12-31 17:00", "2024-12-31 17:00", "2024-08-15 08:00"))

    # -- PROJWBS (unchanged) ------------------------------
    add(_tab("%T", "PROJWBS"))
    add(_tab("%F", "wbs_id", "proj_id", "parent_wbs_id", "wbs_short_name", "wbs_name", "seq_num", "proj_node_flag"))
    add(_tab("%R", "WBS-001", "PROJ-001", "", "PROJ", "Sample Construction Project", "1", "Y"))
    add(_tab("%R", "WBS-010", "PROJ-001", "WBS-001", "PRECN", "Pre-Construction", "10", "N"))
    add(_tab("%R", "WBS-020", "PROJ-001", "WBS-001", "FOUND", "Foundation", "20", "N"))
    add(_tab("%R", "WBS-030", "PROJ-001", "WBS-001", "STRUC", "Structure", "30", "N"))
    add(_tab("%R", "WBS-040", "PROJ-001", "WBS-001", "FINSH", "Finishes", "40", "N"))
    add(_tab("%R", "WBS-050", "PROJ-001", "WBS-001", "CLOSE", "Closeout", "50", "N"))
    add(_tab("%R", "WBS-021", "PROJ-001", "WBS-020", "EXCAV", "Excavation", "21", "N"))
    add(_tab("%R", "WBS-022", "PROJ-001", "WBS-020", "CONC", "Concrete", "22", "N"))
    add(_tab("%R", "WBS-031", "PROJ-001", "WBS-030", "STEEL", "Steel Erection", "31", "N"))
    add(_tab("%R", "WBS-041", "PROJ-001", "WBS-040", "PAINT", "Painting", "41", "N"))

    # -- RSRC (unchanged) ---------------------------------
    add(_tab("%T", "RSRC"))
    add(_tab("%F", "rsrc_id", "rsrc_name", "rsrc_type"))
    add(_tab("%R", "R-001", "General Labor", "RT_Labor"))
    add(_tab("%R", "R-002", "Crane Operator", "RT_Labor"))
    add(_tab("%R", "R-003", "Concrete Pump", "RT_Equip"))

    # -- TASK ---------------------------------------------
    add(_tab("%T", "TASK"))
    add(_tab(
        "%F",
        "task_id", "proj_id", "wbs_id", "clndr_id",
        "task_code", "task_name", "task_type", "status_code",
        "total_float_hr_cnt", "free_float_hr_cnt",
        "remain_drtn_hr_cnt", "target_drtn_hr_cnt",
        "act_start_date", "act_end_date",
        "early_start_date", "early_end_date",
        "late_start_date", "late_end_date",
        "target_start_date", "target_end_date",
        "restart_date", "reend_date",
        "phys_complete_pct", "complete_pct_type",
        "duration_type", "cstr_type", "cstr_date", "cstr_type2", "cstr_date2",
        "float_path", "float_path_order", "driving_path_flag", "priority_type",
        "act_work_qty", "remain_work_qty", "target_work_qty",
    ))

    def task_row(
        tid: str, wbs: str, cal: str, code: str, name: str,
        ttype: str, status: str,
        tf: str, ff: str, rem_dur: str, tgt_dur: str,
        act_s: str, act_e: str,
        es: str, ef: str, ls: str, lf: str,
        ts: str, te: str,
        rs: str, re: str,
        pct: str, pct_type: str, dur_type: str,
        cstr_type: str = "", cstr_date: str = "",
        cstr_type2: str = "", cstr_date2: str = "",
        fp: str = "", fpo: str = "", dpf: str = "N", pri: str = "PT_Normal",
        aw: str = "0", rw: str = "0", tw: str = "0",
    ) -> None:
        add(_tab(
            "%R", tid, "PROJ-001", wbs, cal,
            code, name, ttype, status,
            tf, ff, rem_dur, tgt_dur,
            act_s, act_e, es, ef, ls, lf, ts, te, rs, re,
            pct, pct_type, dur_type,
            cstr_type, cstr_date, cstr_type2, cstr_date2,
            fp, fpo, dpf, pri, aw, rw, tw,
        ))

    # -- All originally complete activities remain complete (T-001 to T-015) --

    task_row("T-001", "WBS-010", "CAL-01", "A1000", "Project Start", "TT_mile", "TK_Complete",
             "0", "0", "0", "0",
             "2024-01-02 08:00", "2024-01-02 08:00",
             "2024-01-02 08:00", "2024-01-02 08:00",
             "2024-01-02 08:00", "2024-01-02 08:00",
             "2024-01-02 08:00", "2024-01-02 08:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="1", dpf="Y")

    # T-002: keep retroactive date from update1 (same as update1)
    task_row("T-002", "WBS-010", "CAL-01", "A1010", "Site Survey", "TT_Task", "TK_Complete",
             "0", "0", "0", "80",
             "2024-01-04 08:00", "2024-01-17 17:00",
             "2024-01-03 08:00", "2024-01-16 17:00",
             "2024-01-03 08:00", "2024-01-16 17:00",
             "2024-01-03 08:00", "2024-01-16 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="2", dpf="Y")

    task_row("T-003", "WBS-010", "CAL-01", "A1020", "Permits & Approvals", "TT_Task", "TK_Complete",
             "0", "0", "0", "160",
             "2024-01-17 08:00", "2024-02-13 17:00",
             "2024-01-17 08:00", "2024-02-13 17:00",
             "2024-01-17 08:00", "2024-02-13 17:00",
             "2024-01-17 08:00", "2024-02-13 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="3", dpf="Y")

    task_row("T-004", "WBS-010", "CAL-01", "A1030", "Mobilisation", "TT_Task", "TK_Complete",
             "40", "0", "0", "40",
             "2024-01-17 08:00", "2024-01-23 17:00",
             "2024-01-17 08:00", "2024-01-23 17:00",
             "2024-01-22 08:00", "2024-01-26 17:00",
             "2024-01-17 08:00", "2024-01-23 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn")

    task_row("T-005", "WBS-021", "CAL-01", "A2010", "Site Clearing", "TT_Task", "TK_Complete",
             "0", "0", "0", "40",
             "2024-02-14 08:00", "2024-02-20 17:00",
             "2024-02-14 08:00", "2024-02-20 17:00",
             "2024-02-14 08:00", "2024-02-20 17:00",
             "2024-02-14 08:00", "2024-02-20 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="4", dpf="Y")

    task_row("T-006", "WBS-021", "CAL-01", "A2020", "Excavation", "TT_Task", "TK_Complete",
             "0", "0", "0", "80",
             "2024-02-21 08:00", "2024-03-05 17:00",
             "2024-02-21 08:00", "2024-03-05 17:00",
             "2024-02-21 08:00", "2024-03-05 17:00",
             "2024-02-21 08:00", "2024-03-05 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="5", dpf="Y")

    task_row("T-007", "WBS-022", "CAL-01", "A2030", "Foundation Rebar", "TT_Task", "TK_Complete",
             "0", "0", "0", "80",
             "2024-03-06 08:00", "2024-03-19 17:00",
             "2024-03-06 08:00", "2024-03-19 17:00",
             "2024-03-06 08:00", "2024-03-19 17:00",
             "2024-03-06 08:00", "2024-03-19 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="6", dpf="Y")

    task_row("T-008", "WBS-022", "CAL-01", "A2040", "Foundation Pour", "TT_Task", "TK_Complete",
             "0", "0", "0", "40",
             "2024-03-20 08:00", "2024-03-26 17:00",
             "2024-03-20 08:00", "2024-03-26 17:00",
             "2024-03-20 08:00", "2024-03-26 17:00",
             "2024-03-20 08:00", "2024-03-26 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="7", dpf="Y")

    task_row("T-009", "WBS-022", "CAL-01", "A2050", "Foundation Cure", "TT_Task", "TK_Complete",
             "0", "0", "0", "80",
             "2024-03-27 08:00", "2024-04-09 17:00",
             "2024-03-27 08:00", "2024-04-09 17:00",
             "2024-03-27 08:00", "2024-04-09 17:00",
             "2024-03-27 08:00", "2024-04-09 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="8", dpf="Y")

    task_row("T-010", "WBS-022", "CAL-01", "A2060", "Backfill", "TT_Task", "TK_Complete",
             "80", "80", "0", "40",
             "2024-03-27 08:00", "2024-04-02 17:00",
             "2024-03-27 08:00", "2024-04-02 17:00",
             "2024-04-08 08:00", "2024-04-12 17:00",
             "2024-03-27 08:00", "2024-04-02 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn")

    task_row("T-011", "WBS-020", "CAL-01", "A2070", "Foundation Complete", "TT_finmile", "TK_Complete",
             "0", "0", "0", "0",
             "2024-04-10 08:00", "2024-04-10 08:00",
             "2024-04-10 08:00", "2024-04-10 08:00",
             "2024-04-10 08:00", "2024-04-10 08:00",
             "2024-04-10 08:00", "2024-04-10 08:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="9", dpf="Y")

    task_row("T-012", "WBS-031", "CAL-01", "A3010", "Steel Delivery", "TT_Task", "TK_Complete",
             "0", "0", "0", "40",
             "2024-04-10 08:00", "2024-04-16 17:00",
             "2024-04-10 08:00", "2024-04-16 17:00",
             "2024-04-10 08:00", "2024-04-16 17:00",
             "2024-04-10 08:00", "2024-04-16 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="10", dpf="Y")

    task_row("T-013", "WBS-031", "CAL-01", "A3020", "Column Erection", "TT_Task", "TK_Complete",
             "0", "0", "0", "80",
             "2024-04-17 08:00", "2024-04-30 17:00",
             "2024-04-17 08:00", "2024-04-30 17:00",
             "2024-04-17 08:00", "2024-04-30 17:00",
             "2024-04-17 08:00", "2024-04-30 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="11", dpf="Y")

    task_row("T-014", "WBS-031", "CAL-01", "A3030", "Beam Installation", "TT_Task", "TK_Complete",
             "0", "0", "0", "80",
             "2024-05-01 08:00", "2024-05-14 17:00",
             "2024-05-01 08:00", "2024-05-14 17:00",
             "2024-05-01 08:00", "2024-05-14 17:00",
             "2024-05-01 08:00", "2024-05-14 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="12", dpf="Y")

    task_row("T-015", "WBS-031", "CAL-01", "A3040", "Deck Pour", "TT_Task", "TK_Complete",
             "0", "0", "0", "40",
             "2024-05-15 08:00", "2024-05-21 17:00",
             "2024-05-15 08:00", "2024-05-21 17:00",
             "2024-05-15 08:00", "2024-05-21 17:00",
             "2024-05-15 08:00", "2024-05-21 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="13", dpf="Y")

    # -- Activities that were active in update1, now complete --

    task_row("T-016", "WBS-030", "CAL-01", "A3050", "Roof Framing", "TT_Task", "TK_Complete",
             "0", "0", "0", "80",
             "2024-05-22 08:00", "2024-06-07 17:00",
             "2024-05-22 08:00", "2024-06-07 17:00",
             "2024-05-22 08:00", "2024-06-07 17:00",
             "2024-05-22 08:00", "2024-06-04 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="14", dpf="Y")

    task_row("T-017", "WBS-030", "CAL-01", "A3060", "MEP Rough-In", "TT_Task", "TK_Complete",
             "0", "0", "0", "120",
             "2024-05-22 08:00", "2024-06-14 17:00",
             "2024-05-22 08:00", "2024-06-14 17:00",
             "2024-05-22 08:00", "2024-06-14 17:00",
             "2024-05-22 08:00", "2024-06-14 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn")

    task_row("T-018", "WBS-030", "CAL-01", "A3070", "Exterior Cladding", "TT_Task", "TK_Complete",
             "0", "0", "0", "120",
             "2024-05-15 08:00", "2024-06-07 17:00",
             "2024-05-15 08:00", "2024-06-07 17:00",
             "2024-05-15 08:00", "2024-06-07 17:00",
             "2024-05-15 08:00", "2024-06-07 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn")

    task_row("T-019", "WBS-031", "CAL-01", "A3080", "Welding Inspection", "TT_Task", "TK_Complete",
             "0", "0", "0", "40",
             "2024-05-22 08:00", "2024-05-28 17:00",
             "2024-05-22 08:00", "2024-05-28 17:00",
             "2024-05-22 08:00", "2024-05-28 17:00",
             "2024-05-22 08:00", "2024-05-28 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn")

    task_row("T-020", "WBS-030", "CAL-01", "A3090", "Fire Protection", "TT_LOE", "TK_Complete",
             "0", "0", "0", "80",
             "2024-05-22 08:00", "2024-06-04 17:00",
             "2024-05-22 08:00", "2024-06-04 17:00",
             "2024-05-22 08:00", "2024-06-04 17:00",
             "2024-05-22 08:00", "2024-06-04 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn")

    # T-021: Roof Membrane -- now complete (was active in update1)
    task_row("T-021", "WBS-030", "CAL-01", "A4010", "Roof Membrane", "TT_Task", "TK_Complete",
             "0", "0", "0", "56",
             "2024-06-10 08:00", "2024-06-21 17:00",
             "2024-06-10 08:00", "2024-06-21 17:00",
             "2024-06-10 08:00", "2024-06-21 17:00",
             "2024-06-10 08:00", "2024-06-21 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="15", dpf="Y")

    # T-022: Structure Complete -- already complete in update1
    task_row("T-022", "WBS-030", "CAL-01", "A4020", "Structure Complete", "TT_finmile", "TK_Complete",
             "0", "0", "0", "0",
             "2024-06-17 08:00", "2024-06-17 08:00",
             "2024-06-17 08:00", "2024-06-17 08:00",
             "2024-06-17 08:00", "2024-06-17 08:00",
             "2024-06-17 08:00", "2024-06-17 08:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="16", dpf="Y")

    # T-023: Interior Painting -- now complete
    task_row("T-023", "WBS-041", "CAL-01", "A5010", "Interior Painting", "TT_Task", "TK_Complete",
             "0", "0", "0", "80",
             "2024-06-17 08:00", "2024-07-05 17:00",
             "2024-06-17 08:00", "2024-07-05 17:00",
             "2024-06-17 08:00", "2024-07-05 17:00",
             "2024-06-17 08:00", "2024-06-28 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="17", dpf="Y")

    # T-024: Flooring -- now active, was not-started in update1
    task_row("T-024", "WBS-041", "CAL-01", "A5020", "Flooring", "TT_Task", "TK_Active",
             "0", "0", "24", "60",
             "2024-07-08 08:00", "",
             "2024-07-08 08:00", "2024-07-22 17:00",
             "2024-07-08 08:00", "2024-07-22 17:00",
             "2024-07-08 08:00", "2024-07-17 17:00",
             "2024-07-15 08:00", "2024-07-22 17:00",
             "60", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="18", dpf="Y")

    # T-025: Fixtures & Fittings -- DURATION INCREASED from 64h to 96h (delay)
    task_row("T-025", "WBS-040", "CAL-01", "A5030", "Fixtures & Fittings", "TT_Task", "TK_Active",
             "0", "0", "72", "96",
             "2024-07-08 08:00", "",
             "2024-07-08 08:00", "2024-07-26 17:00",
             "2024-07-08 08:00", "2024-07-26 17:00",
             "2024-07-08 08:00", "2024-07-17 17:00",
             "2024-07-15 08:00", "2024-07-26 17:00",
             "25", "CP_Drtn", "DT_FixedDrtn")

    # T-026: DELETED (Landscaping removed from scope)

    # T-027: Final Inspection -- pushed back due to delays
    task_row("T-027", "WBS-050", "CAL-01", "A6010", "Final Inspection", "TT_Task", "TK_NotStart",
             "0", "0", "40", "40",
             "", "",
             "2024-08-05 08:00", "2024-08-09 17:00",
             "2024-08-05 08:00", "2024-08-09 17:00",
             "2024-08-05 08:00", "2024-08-09 17:00",
             "2024-08-05 08:00", "2024-08-09 17:00",
             "0", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="19", dpf="Y")

    # T-028: Punch List -- DURATION INCREASED from 80h to 120h (delay)
    task_row("T-028", "WBS-050", "CAL-01", "A6020", "Punch List", "TT_Task", "TK_NotStart",
             "0", "0", "120", "120",
             "", "",
             "2024-08-12 08:00", "2024-08-30 17:00",
             "2024-08-12 08:00", "2024-08-30 17:00",
             "2024-08-12 08:00", "2024-08-30 17:00",
             "2024-08-12 08:00", "2024-08-30 17:00",
             "0", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="20", dpf="Y",
             cstr_type="CS_MEF", cstr_date="2024-08-02 17:00")

    # T-030: Project Completion -- pushed back ~10 days (was Aug 12 in update1, now ~Aug 22)
    task_row("T-030", "WBS-050", "CAL-01", "A6030", "Project Completion", "TT_mile", "TK_NotStart",
             "0", "0", "0", "0",
             "", "",
             "2024-09-06 08:00", "2024-09-06 08:00",
             "2024-09-06 08:00", "2024-09-06 08:00",
             "2024-09-06 08:00", "2024-09-06 08:00",
             "2024-09-06 08:00", "2024-09-06 08:00",
             "0", "CP_Drtn", "DT_FixedDrtn",
             fp="1", fpo="21", dpf="Y")

    # T-031: Quality Hold Point -- now complete
    task_row("T-031", "WBS-040", "CAL-01", "A7010", "Quality Hold Point", "TT_Task", "TK_Complete",
             "0", "0", "0", "40",
             "2024-07-08 08:00", "2024-07-15 17:00",
             "2024-07-08 08:00", "2024-07-15 17:00",
             "2024-07-08 08:00", "2024-07-15 17:00",
             "2024-07-08 08:00", "2024-07-15 17:00", "", "",
             "100", "CP_Drtn", "DT_FixedDrtn")

    # T-032: Commissioning -- still not started, pushed back
    task_row("T-032", "WBS-050", "CAL-01", "A7020", "Commissioning", "TT_Task", "TK_NotStart",
             "0", "0", "40", "40",
             "", "",
             "2024-09-02 08:00", "2024-09-06 17:00",
             "2024-09-02 08:00", "2024-09-06 17:00",
             "2024-09-02 08:00", "2024-09-06 17:00",
             "2024-09-02 08:00", "2024-09-06 17:00",
             "0", "CP_Drtn", "DT_FixedDrtn")

    # T-033: NEW ACTIVITY -- Punchlist Verification
    task_row("T-033", "WBS-050", "CAL-01", "A7030", "Punchlist Verification", "TT_Task", "TK_NotStart",
             "0", "0", "24", "24",
             "", "",
             "2024-08-30 08:00", "2024-09-02 17:00",
             "2024-08-30 08:00", "2024-09-02 17:00",
             "2024-08-30 08:00", "2024-09-02 17:00",
             "2024-08-30 08:00", "2024-09-02 17:00",
             "0", "CP_Drtn", "DT_FixedDrtn")

    # -- TASKPRED -----------------------------------------
    add(_tab("%T", "TASKPRED"))
    add(_tab("%F", "task_pred_id", "task_id", "pred_task_id", "proj_id", "pred_proj_id", "pred_type", "lag_hr_cnt"))

    rel_id = 0

    def rel(succ: str, pred: str, rtype: str = "PR_FS", lag: str = "0") -> None:
        nonlocal rel_id
        rel_id += 1
        add(_tab("%R", f"TP-{rel_id:03d}", succ, pred, "PROJ-001", "PROJ-001", rtype, lag))

    # Original critical path chain (FS):
    rel("T-002", "T-001")   # 1
    rel("T-003", "T-002")   # 2
    rel("T-005", "T-003")   # 3
    rel("T-006", "T-005")   # 4
    rel("T-007", "T-006")   # 5
    rel("T-008", "T-007")   # 6
    rel("T-009", "T-008")   # 7
    rel("T-011", "T-009")   # 8
    rel("T-012", "T-011")   # 9
    rel("T-013", "T-012")   # 10
    rel("T-014", "T-013")   # 11
    rel("T-015", "T-014")   # 12
    rel("T-016", "T-015")   # 13
    rel("T-021", "T-016")   # 14
    rel("T-022", "T-021")   # 15
    rel("T-023", "T-022")   # 16
    rel("T-024", "T-023")   # 17
    rel("T-027", "T-024")   # 18
    rel("T-028", "T-027")   # 19
    rel("T-030", "T-028")   # 20

    # Off-critical FS links (kept from update1)
    rel("T-004", "T-002")   # 21
    rel("T-010", "T-008")   # 22
    rel("T-010", "T-009", "PR_SS")  # 23
    rel("T-017", "T-015")   # 24
    rel("T-018", "T-014")   # 25
    rel("T-019", "T-013")   # 26
    rel("T-019", "T-014", "PR_FF")  # 27
    rel("T-020", "T-015")   # 28
    rel("T-025", "T-022")   # 29
    # T-026 deleted, so its rels removed: was rel 30 (T-026 <- T-022), rel 32 (T-027 <- T-026)
    rel("T-027", "T-025")   # 30
    rel("T-017", "T-016", "PR_SS")  # 31
    rel("T-018", "T-016", "PR_FF")  # 32

    rel("T-022", "T-019")   # 33
    rel("T-022", "T-020")   # 34
    rel("T-025", "T-023", "PR_FF")  # 35
    rel("T-024", "T-025")   # 36

    # Relationships from update1 new activities
    rel("T-031", "T-024")   # 37
    rel("T-032", "T-028")   # 38
    rel("T-030", "T-032")   # 39
    rel("T-031", "T-023")   # 40
    rel("T-032", "T-031")   # 41

    # NEW: T-033 relationships
    rel("T-033", "T-028")   # 42: Punchlist Verification after Punch List
    rel("T-032", "T-033")   # 43: Commissioning after Punchlist Verification

    # -- TASKRSRC -----------------------------------------
    add(_tab("%T", "TASKRSRC"))
    add(_tab("%F", "taskrsrc_id", "task_id", "rsrc_id", "proj_id", "target_qty", "act_reg_qty", "remain_qty", "target_cost", "act_reg_cost", "remain_cost"))

    def taskrsrc(trid: str, tid: str, rid: str, tq: str, aq: str, rq: str, tc: str, ac: str, rc: str) -> None:
        add(_tab("%R", trid, tid, rid, "PROJ-001", tq, aq, rq, tc, ac, rc))

    taskrsrc("TR-001", "T-002", "R-001", "80", "80", "0", "4000", "4000", "0")
    taskrsrc("TR-002", "T-005", "R-001", "40", "40", "0", "2000", "2000", "0")
    taskrsrc("TR-003", "T-006", "R-001", "160", "160", "0", "8000", "8000", "0")
    taskrsrc("TR-004", "T-007", "R-001", "160", "160", "0", "8000", "8000", "0")
    taskrsrc("TR-005", "T-008", "R-003", "40", "40", "0", "6000", "6000", "0")
    taskrsrc("TR-006", "T-013", "R-002", "80", "80", "0", "6000", "6000", "0")
    taskrsrc("TR-007", "T-014", "R-002", "80", "80", "0", "6000", "6000", "0")
    taskrsrc("TR-008", "T-016", "R-001", "80", "80", "0", "4000", "4000", "0")
    taskrsrc("TR-009", "T-023", "R-001", "80", "80", "0", "4000", "4000", "0")
    taskrsrc("TR-010", "T-024", "R-001", "60", "36", "24", "3000", "1800", "1200")

    # -- ACTVTYPE -----------------------------------------
    add(_tab("%T", "ACTVTYPE"))
    add(_tab("%F", "actv_code_type_id", "actv_code_type", "proj_id"))
    add(_tab("%R", "ACT-01", "Discipline", "PROJ-001"))
    add(_tab("%R", "ACT-02", "Phase", "PROJ-001"))

    # -- ACTVCODE -----------------------------------------
    add(_tab("%T", "ACTVCODE"))
    add(_tab("%F", "actv_code_id", "actv_code_type_id", "actv_code_name", "short_name"))
    add(_tab("%R", "AC-01", "ACT-01", "Civil", "CIV"))
    add(_tab("%R", "AC-02", "ACT-01", "Structural", "STR"))
    add(_tab("%R", "AC-03", "ACT-02", "Construction", "CONST"))

    # -- TASKACTV -----------------------------------------
    add(_tab("%T", "TASKACTV"))
    add(_tab("%F", "task_id", "actv_code_id"))
    add(_tab("%R", "T-005", "AC-01"))
    add(_tab("%R", "T-006", "AC-01"))
    add(_tab("%R", "T-013", "AC-02"))
    add(_tab("%R", "T-014", "AC-02"))

    # -- End of file --------------------------------------
    add("%E")

    content = "\n".join(lines) + "\n"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


if __name__ == "__main__":
    path = generate_sample_update2_xer()
    print(f"Generated: {path}")
