# Power Query / M Code — Xer_Compare_two_projects

## TASK
```powerquery
let
    Source = xer,
    #"Filtered Rows" = Table.SelectRows(Source, each ([#"Table "] = "TASK") and ([Column1] <> "%T")),
    #"Promoted Headers" = Table.PromoteHeaders(#"Filtered Rows"),
    #"Appended Query" = Table.Combine({#"Promoted Headers", Task_Schema}),
    #"Removed Other Columns" = Table.SelectColumns(#"Appended Query",{"task_id", "proj_id", "wbs_id", "clndr_id", "phys_complete_pct", "rev_fdbk_flag", "lock_plan_flag", "auto_compute_act_flag", "complete_pct_type", "task_type", "duration_type", "status_code", "task_code", "task_name", "rsrc_id", "total_float_hr_cnt", "free_float_hr_cnt", "remain_drtn_hr_cnt", "act_work_qty", "remain_work_qty", "target_work_qty", "target_drtn_hr_cnt", "target_equip_qty", "act_equip_qty", "remain_equip_qty", "cstr_date", "act_start_date", "act_end_date", "late_start_date", "late_end_date", "expect_end_date", "early_start_date", "early_end_date", "restart_date", "reend_date", "target_start_date", "target_end_date", "rem_late_start_date", "rem_late_end_date", "cstr_type", "priority_type", "suspend_date", "resume_date", "float_path", "float_path_order", "guid", "tmpl_guid", "cstr_date2", "cstr_type2", "driving_path_flag", "act_this_per_work_qty", "act_this_per_equip_qty", "external_early_start_date", "external_late_end_date", "create_date", "update_date", "create_user", "update_user"}),
    Task_ID_Key = Table.AddColumn(#"Removed Other Columns", "Task_ID_Key", each [proj_id]&"."&[task_id]),
    #"Changed Type" = Table.TransformColumnTypes(Task_ID_Key,{{"Task_ID_Key", type text}}),
    wbs_id_Key = Table.AddColumn(#"Changed Type", "wbs_id_Key", each [proj_id]&"."&[wbs_id]),
    clndr_id.Key = Table.AddColumn(wbs_id_Key, "clndr_id.Key", each [proj_id]&"."&[clndr_id]),
    #"Changed Type1" = Table.TransformColumnTypes(clndr_id.Key,{{"wbs_id_Key", type text}, {"clndr_id.Key", type text}}),
    #"Filtered Rows1" = Table.SelectRows(#"Changed Type1", each ([task_id] <> "task_id")),
    #"Changed Type2" = Table.TransformColumnTypes(#"Filtered Rows1",{{"total_float_hr_cnt", type number}, {"free_float_hr_cnt", type number}, {"remain_drtn_hr_cnt", type number}, {"act_work_qty", type number}, {"remain_work_qty", type number}, {"target_work_qty", type number}, {"target_drtn_hr_cnt", type number}, {"target_equip_qty", type number}, {"act_equip_qty", type number}, {"remain_equip_qty", type number}, {"cstr_date", type datetime}, {"act_start_date", type datetime}, {"act_end_date", type datetime}, {"late_start_date", type datetime}, {"late_end_date", type datetime}, {"expect_end_date", type datetime}, {"early_start_date", type datetime}, {"early_end_date", type datetime}, {"restart_date", type datetime}, {"reend_date", type datetime}, {"target_start_date", type datetime}, {"target_end_date", type datetime}, {"rem_late_start_date", type datetime}, {"rem_late_end_date", type datetime}, {"phys_complete_pct", type number}}),
    #"Changed Type3" = Table.TransformColumnTypes(#"Changed Type2",{{"cstr_date", type date}, {"act_start_date", type date}, {"act_end_date", type date}, {"late_start_date", type date}, {"late_end_date", type date}, {"expect_end_date", type date}, {"early_start_date", type date}, {"early_end_date", type date}, {"restart_date", type date}, {"reend_date", type date}, {"target_start_date", type date}, {"target_end_date", type date}, {"rem_late_start_date", type date}, {"rem_late_end_date", type date}})
in
    #"Changed Type3"
```

## PROJECT
```powerquery
let
    Source = xer,
    #"Filtered Rows" = Table.SelectRows(Source, each ([#"Table "] = "PROJECT") and ([Column1] <> "%T")),
    #"Promoted Headers" = Table.PromoteHeaders(#"Filtered Rows"),
    #"Removed Columns" = Table.RemoveColumns(#"Promoted Headers",{"%F"}),
    #"Removed Other Columns" = Table.SelectColumns(#"Removed Columns",{"proj_id", "proj_short_name", "last_recalc_date"}),
    #"Filtered Rows1" = Table.SelectRows(#"Removed Other Columns", each ([proj_id] <> "proj_id")),
    #"Changed Type" = Table.TransformColumnTypes(#"Filtered Rows1",{{"last_recalc_date", type datetime}}),
    #"Sorted Rows" = Table.Sort(#"Changed Type",{{"last_recalc_date", Order.Ascending}}),
    #"Added Index" = Table.AddIndexColumn(#"Sorted Rows", "Index", 1, 1)
in
    #"Added Index"
```

## P6
```powerquery
let
    Source = xer,
    #"Filtered Rows" = Table.SelectRows(Source, each ([#"Table "] = "TASK") and ([Column1] <> "%T")),
    #"Promoted Headers" = Table.PromoteHeaders(#"Filtered Rows"),
    #"Filtered Rows1" = Table.SelectRows(#"Promoted Headers", each ([task_id] <> "task_id")),
    #"Removed Other Columns" = Table.SelectColumns(#"Filtered Rows1",{"task_id", "proj_id", "wbs_id", "task_code", "task_name"}),
    #"Renamed Columns" = Table.RenameColumns(#"Removed Other Columns",{{"task_name", "Activity_name"}, {"task_code", "Activity_ID"}}),
    #"Added Custom" = Table.AddColumn(#"Renamed Columns", "Key", each [proj_id]&"."&[task_id]),
    #"Added Custom1" = Table.AddColumn(#"Added Custom", "wbs_id_key", each [proj_id]&"."&[wbs_id]),
    #"Changed Type" = Table.TransformColumnTypes(#"Added Custom1",{{"wbs_id_key", type text}}),
    #"Removed Other Columns1" = Table.SelectColumns(#"Changed Type",{"Activity_ID", "Activity_name", "Key", "wbs_id_key"})
in
    #"Removed Other Columns1"
```

## Metrics
```powerquery
let
    Source = Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("i45WcvTxUYqNBQA=", BinaryEncoding.Base64), Compression.Deflate)))
in
    Source
```

## PROJWBS
```powerquery
let
    Source = xer,
    #"Filtered Rows" = Table.SelectRows(Source, each ([#"Table "] = "PROJWBS") and ([Column1] <> "%T")),
    #"Promoted Headers" = Table.PromoteHeaders(#"Filtered Rows"),
    #"Removed Other Columns" = Table.SelectColumns(#"Promoted Headers",{"wbs_id", "proj_id", "obs_id", "seq_num",  "proj_node_flag", "sum_data_flag", "status_code", "wbs_short_name", "wbs_name", "phase_id", "parent_wbs_id", "ev_user_pct", "ev_etc_user_value", "orig_cost", "indep_remain_total_cost", "ann_dscnt_rate_pct", "dscnt_period_type", "indep_remain_work_qty", "anticip_start_date", "anticip_end_date", "ev_compute_type", "ev_etc_compute_type", "guid", "tmpl_guid", "plan_open_state"}),
    #"Filtered Rows1" = Table.SelectRows(#"Removed Other Columns", each ([proj_id] <> "proj_id")),
    #"Added Custom" = Table.AddColumn(#"Filtered Rows1", "wbs_id_Key", each [proj_id]&"."&[wbs_id]),
    #"Changed Type" = Table.TransformColumnTypes(#"Added Custom",{{"wbs_id_Key", type text}}),
    #"Removed Other Columns1" = Table.SelectColumns(#"Changed Type",{"wbs_id", "proj_id", "seq_num", "proj_node_flag", "wbs_short_name", "wbs_name", "parent_wbs_id", "wbs_id_Key"}),
    #"Added Custom1" = Table.AddColumn(#"Removed Other Columns1", "Parent_wbs_id_Key", each if [proj_node_flag]="Y" then [wbs_id_Key] else [proj_id]&"."&[parent_wbs_id]),
    #"Changed Type1" = Table.TransformColumnTypes(#"Added Custom1",{{"Parent_wbs_id_Key", type text}, {"seq_num", Int64.Type}})
in
    #"Changed Type1"
```

## PREDECESSOR
```powerquery
let
    Source = xer,
    #"Filtered Rows2" = Table.SelectRows(Source, each ([#"Table "] = "TASKPRED") and ([Column1] <> "%T")),
    #"Promoted Headers" = Table.PromoteHeaders(#"Filtered Rows2"),
    #"Appended Query" = Table.Combine({#"Promoted Headers", Predecessor_Schema}),
    #"Removed Other Columns" = Table.SelectColumns(#"Appended Query",{"task_id", "pred_task_id", "proj_id", "pred_proj_id", "pred_type", "lag_hr_cnt", "float_path", "aref", "arls"}),
    #"Added Custom" = Table.AddColumn(#"Removed Other Columns", "Task_id_key", each [proj_id]&"."&[task_id]),
    #"Changed Type1" = Table.TransformColumnTypes(#"Added Custom",{{"Task_id_key", type text}, {"aref", type datetime}, {"arls", type datetime}}),
    #"Filtered Rows" = Table.SelectRows(#"Changed Type1", each ([proj_id] <> "proj_id")),
    #"Removed Columns" = Table.RemoveColumns(#"Filtered Rows",{"task_id"}),
    #"Added Custom1" = Table.AddColumn(#"Removed Columns", "pred_task_id_key", each [proj_id]&"."&[pred_task_id]),
    #"Changed Type" = Table.TransformColumnTypes(#"Added Custom1",{{"pred_task_id_key", type text}}),
    #"Replaced Value" = Table.ReplaceValue(#"Changed Type","PR_","",Replacer.ReplaceText,{"pred_type"}),
    #"Changed Type2" = Table.TransformColumnTypes(#"Replaced Value",{{"lag_hr_cnt", type number}}),
    #"Added Custom2" = Table.AddColumn(#"Changed Type2", "Relationship Free Float", each [arls]-[aref]),
    #"Changed Type3" = Table.TransformColumnTypes(#"Added Custom2",{{"Relationship Free Float", type number}}),
    #"Removed Columns1" = Table.RemoveColumns(#"Changed Type3",{"aref", "arls"})
in
    #"Removed Columns1"
```

## Schema
```powerquery
let
    Source = xer,
    #"Filtered Rows" = Table.SelectRows(Source, each ([Column1] = "ERMHDR")),
    #"Removed Other Columns" = Table.SelectColumns(#"Filtered Rows",{"Column1", "Column2"}),
    #"Renamed Columns" = Table.RenameColumns(#"Removed Other Columns",{{"Column2", "Version"}}),
    #"Removed Other Columns1" = Table.SelectColumns(#"Renamed Columns",{"Version"})
in
    #"Removed Other Columns1"
```

## Path_Current
```powerquery
let
    Source = Path,
    #"Converted to Table" = #table(1, {{Source}}),
    #"Renamed Columns" = Table.RenameColumns(#"Converted to Table",{{"Column1", "Path"}}),
    #"Changed Type" = Table.TransformColumnTypes(#"Renamed Columns",{{"Path", type text}})
in
    #"Changed Type"
```

## Activity_Status
```powerquery
let
    Source = Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("i45WCvGOd0wuySxLVdJRgjJidcDCzvm5BTmpJSAJOBMq5ZdfElySWFQClAIyFSDs2FgA", BinaryEncoding.Base64), Compression.Deflate)), let _t = ((type text) meta [Serialized.Text = true]) in type table [status_code = _t, Description = _t])
in
    Source
```

## P6_Calendars
```powerquery
let
    Source = xer,
    #"Filtered Rows" = Table.SelectRows(Source, each [#"Table "] = "CALENDAR" and [Column1] <> "%T"),
    #"Promoted Headers" = Table.PromoteHeaders(#"Filtered Rows"),
    #"Appended Query" = Table.Combine({#"Promoted Headers", Calendar_Schema}),
    #"Removed Other Columns" = Table.SelectColumns(#"Appended Query",{"clndr_id", "default_flag", "clndr_name", "proj_id", "base_clndr_id", "last_chng_date", "clndr_type", "day_hr_cnt", "week_hr_cnt", "month_hr_cnt", "year_hr_cnt", "rsrc_private"}),
    #"Filtered Rows1" = Table.SelectRows(#"Removed Other Columns", each ([clndr_id] <> "clndr_id")),
    #"Changed Type" = Table.TransformColumnTypes(#"Filtered Rows1",{{"last_chng_date", type datetime}, {"year_hr_cnt", type number}, {"month_hr_cnt", type number}, {"week_hr_cnt", type number}, {"day_hr_cnt", type number}}),
    #"Added Custom" = Table.AddColumn(#"Changed Type", "clndr_id_key", each if [clndr_type] ="CA_Project" then [proj_id]&"."&[clndr_id] else [clndr_id]),
    #"Changed Type1" = Table.TransformColumnTypes(#"Added Custom",{{"clndr_id_key", type text}})
in
    #"Changed Type1"
```

