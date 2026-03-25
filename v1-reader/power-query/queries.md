# Power Query / M Code — Xer_Reader_PQ_sqlite

## TASK
```powerquery
let
    Source = xer,
    #"Filtered Rows" = Table.SelectRows(Source, each ([#"Table "] = "TASK") and ([Column1] <> "%T")),
    #"Promoted Headers" = Table.PromoteHeaders(#"Filtered Rows"),
    #"Removed Other Columns" = Table.SelectColumns(#"Promoted Headers",{"task_id", "proj_id", "wbs_id", "clndr_id", "phys_complete_pct", "rev_fdbk_flag", "lock_plan_flag", "auto_compute_act_flag", "complete_pct_type", "task_type", "duration_type", "status_code", "task_code", "task_name", "rsrc_id", "total_float_hr_cnt", "free_float_hr_cnt", "remain_drtn_hr_cnt", "act_work_qty", "remain_work_qty", "target_work_qty", "target_drtn_hr_cnt", "target_equip_qty", "act_equip_qty", "remain_equip_qty", "cstr_date", "act_start_date", "act_end_date", "late_start_date", "late_end_date", "expect_end_date", "early_start_date", "early_end_date", "restart_date", "reend_date", "target_start_date", "target_end_date", "rem_late_start_date", "rem_late_end_date", "cstr_type", "priority_type", "suspend_date", "resume_date", "float_path", "float_path_order", "guid", "tmpl_guid", "cstr_date2", "cstr_type2", "driving_path_flag", "act_this_per_work_qty", "act_this_per_equip_qty", "external_early_start_date", "external_late_end_date", "create_date", "update_date", "create_user", "update_user"}),
    #"Filtered Rows1" = Table.SelectRows(#"Removed Other Columns", each ([task_id] <> "task_id")),
    #"Changed Type2" = Table.TransformColumnTypes(#"Filtered Rows1",{{"total_float_hr_cnt", type number}, {"free_float_hr_cnt", type number}, {"remain_drtn_hr_cnt", type number}, {"act_work_qty", type number}, {"remain_work_qty", type number}, {"target_work_qty", type number}, {"target_drtn_hr_cnt", type number}, {"target_equip_qty", type number}, {"act_equip_qty", type number}, {"remain_equip_qty", type number}, {"cstr_date", type datetime}, {"act_start_date", type datetime}, {"act_end_date", type datetime}, {"late_start_date", type datetime}, {"late_end_date", type datetime}, {"expect_end_date", type datetime}, {"early_start_date", type datetime}, {"early_end_date", type datetime}, {"restart_date", type datetime}, {"reend_date", type datetime}, {"target_start_date", type datetime}, {"target_end_date", type datetime}, {"rem_late_start_date", type datetime}, {"rem_late_end_date", type datetime}, {"phys_complete_pct", type number}}),
    #"Changed Type3" = Table.TransformColumnTypes(#"Changed Type2",{{"cstr_date", type date}, {"act_start_date", type date}, {"act_end_date", type date}, {"late_start_date", type date}, {"late_end_date", type date}, {"expect_end_date", type date}, {"early_start_date", type date}, {"early_end_date", type date}, {"restart_date", type date}, {"reend_date", type date}, {"target_start_date", type date}, {"target_end_date", type date}, {"rem_late_start_date", type date}, {"rem_late_end_date", type date}}),
    Source_SQLITE = Odbc.DataSource("driver={SQLite3 ODBC Driver};database="&Path_SQLITE&";longnames=0;timeout=1000;notxn=0;dsn=SQLite Datasource", [HierarchicalNavigation=true]),
    TASK_Table = Source_SQLITE{[Name="TASK",Kind="Table"]}[Data],
    #"Renamed Columns2" = Table.RenameColumns(TASK_Table,{{"TASK_NAME", "task_name"}, {"TASK_CODE", "task_code"}, {"STATUS_CODE", "status_code"}}),
    #"Changed Type6" = Table.TransformColumnTypes(#"Renamed Columns2",{{"CLNDR_ID", type text}}),
    #"Renamed Columns1" = Table.RenameColumns(#"Changed Type6",{{"WBS_ID", "wbs_id"}}),
    #"Changed Type5" = Table.TransformColumnTypes(#"Renamed Columns1",{{"wbs_id", type text}}),
    #"Changed Type4" = Table.TransformColumnTypes(#"Changed Type5",{{"TASK_ID", type text}, {"PROJ_ID", type text}}),
    #"Renamed Columns" = Table.RenameColumns(#"Changed Type4",{{"PROJ_ID", "proj_id"}, {"TASK_ID", "task_id"}}),
    result = if Connections="XER" then #"Changed Type3" else #"Renamed Columns",
    Task_ID_Key = Table.AddColumn(result, "Task_ID_Key", each [proj_id]&"."&[task_id]),
    #"Changed Type" = Table.TransformColumnTypes(Task_ID_Key,{{"Task_ID_Key", type text}}),
    #"Added Custom1" = Table.AddColumn(#"Changed Type", "wbs_id_Key", each [proj_id]&"."&[wbs_id]),
    #"Changed Type1" = Table.TransformColumnTypes(#"Added Custom1",{{"wbs_id_Key", type text}})
in
    #"Changed Type1"
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

    Source_SQLITE = Odbc.DataSource("driver={SQLite3 ODBC Driver};database="&Path_SQLITE&";longnames=0;timeout=1000;notxn=0;dsn=SQLite Datasource", [HierarchicalNavigation=true]),
    TASK_Table = Source_SQLITE{[Name="PROJECT",Kind="Table"]}[Data],
    #"Removed Other Columns1" = Table.SelectColumns(TASK_Table,{"PROJ_ID", "LAST_RECALC_DATE", "PROJ_SHORT_NAME"}),
    #"Renamed Columns" = Table.RenameColumns(#"Removed Other Columns1",{{"PROJ_ID", "proj_id"}}),
    
    result = if Connections="XER" then #"Changed Type" else #"Renamed Columns",
    #"Changed Type1" = Table.TransformColumnTypes(result,{{"proj_id", type text}})
in
    #"Changed Type1"
```

## P6
```powerquery
let
    Source = TASK,
    #"Removed Other Columns" = Table.SelectColumns(Source,{"task_id", "proj_id", "wbs_id", "task_code", "task_name", "Task_ID_Key", "wbs_id_Key"}),
    #"Renamed Columns" = Table.RenameColumns(#"Removed Other Columns",{{"task_name", "Activity_name"}, {"task_code", "Activity_ID"}}),
    #"Removed Other Columns1" = Table.SelectColumns(#"Renamed Columns",{"Activity_ID", "Activity_name", "Task_ID_Key", "wbs_id_Key"})
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
    Source_SQLITE = Odbc.DataSource("driver={SQLite3 ODBC Driver};database="&Path_SQLITE&";longnames=0;timeout=1000;notxn=0;dsn=SQLite Datasource", [HierarchicalNavigation=true]),
    TASK_Table = Source_SQLITE{[Name="PROJWBS",Kind="Table"]}[Data],
    #"Renamed Columns" = Table.RenameColumns(TASK_Table,{{"WBS_ID", "wbs_id"}, {"PROJ_ID", "proj_id"}, {"SEQ_NUM", "seq_num"}, {"PROJ_NODE_FLAG", "proj_node_flag"}, {"WBS_SHORT_NAME", "wbs_short_name"}, {"WBS_NAME", "wbs_name"}, {"PARENT_WBS_ID", "parent_wbs_id"}}),
    #"Changed Type1" = Table.TransformColumnTypes(#"Renamed Columns",{{"wbs_id", type text}, {"proj_id", type text}, {"parent_wbs_id", type text}}),
    result = if Connections="XER" then #"Filtered Rows1" else #"Changed Type1",
    #"Removed Other Columns1" = Table.SelectColumns(result,{"wbs_id", "proj_id", "seq_num", "proj_node_flag", "wbs_short_name", "wbs_name", "parent_wbs_id"}),
    wbs_id_key = Table.AddColumn(#"Removed Other Columns1", "wbs_id_Key", each [proj_id]&"."&[wbs_id]),
    #"Changed Type" = Table.TransformColumnTypes(wbs_id_key,{{"wbs_id_Key", type text}}),
    Parent_wbs_id_key = Table.AddColumn(#"Changed Type", "Parent_wbs_id_Key", each if [proj_node_flag]="Y" then [wbs_id_Key] else [proj_id]&"."&[parent_wbs_id]),
    #"Changed Type2" = Table.TransformColumnTypes(Parent_wbs_id_key,{{"Parent_wbs_id_Key", type text}}),
    #"Removed Other Columns2" = Table.SelectColumns(#"Changed Type2",{"Parent_wbs_id_Key", "wbs_id_Key", "wbs_name", "wbs_short_name", "proj_id", "seq_num"})
in
    #"Removed Other Columns2"
```

## PREDECESSOR
```powerquery
let
    Source = xer,
    #"Filtered Rows2" = Table.SelectRows(Source, each ([#"Table "] = "TASKPRED") and ([Column1] <> "%T")),
    #"Promoted Headers" = Table.PromoteHeaders(#"Filtered Rows2"),
    #"Removed Other Columns" = Table.SelectColumns(#"Promoted Headers",{"task_id", "pred_task_id", "proj_id", "pred_proj_id", "pred_type", "lag_hr_cnt"}),
    #"Filtered Rows" = Table.SelectRows(#"Removed Other Columns", each ([proj_id] <> "proj_id")),
    Source_SQLITE = Odbc.DataSource("driver={SQLite3 ODBC Driver};database="&Path_SQLITE&";longnames=0;timeout=1000;notxn=0;dsn=SQLite Datasource", [HierarchicalNavigation=true]),
    TASK_Table = Source_SQLITE{[Name="TASKPRED",Kind="Table"]}[Data],
    #"Renamed Columns4" = Table.RenameColumns(TASK_Table,{{"PRED_PROJ_ID", "pred_proj_id"}}),
    #"Renamed Columns3" = Table.RenameColumns(#"Renamed Columns4",{{"LAG_HR_CNT", "lag_hr_cnt"}}),
    #"Renamed Columns2" = Table.RenameColumns(#"Renamed Columns3",{{"PRED_TASK_ID", "pred_task_id"}}),
    #"Changed Type5" = Table.TransformColumnTypes(#"Renamed Columns2",{{"pred_task_id", type text}}),
    #"Renamed Columns1" = Table.RenameColumns(#"Changed Type5",{{"TASK_ID", "task_id"}, {"PRED_TYPE", "pred_type"}}),
    #"Changed Type4" = Table.TransformColumnTypes(#"Renamed Columns1",{{"task_id", type text}}),
    #"Changed Type3" = Table.TransformColumnTypes(#"Changed Type4",{{"PROJ_ID", type text}}),
    #"Renamed Columns" = Table.RenameColumns(#"Changed Type3",{{"PROJ_ID", "proj_id"}}),
        
    result = if Connections="XER" then #"Filtered Rows" else #"Renamed Columns",
    #"Added Custom" = Table.AddColumn(result, "Task_id_key", each [proj_id]&"."&[task_id]),
    #"Changed Type1" = Table.TransformColumnTypes(#"Added Custom",{{"Task_id_key", type text}}),
    #"Replaced Value" = Table.ReplaceValue(#"Changed Type1","PR_","",Replacer.ReplaceText,{"pred_type"}),
    #"Added Custom1" = Table.AddColumn(#"Replaced Value", "pred_task_id_key", each [proj_id]&"."&[pred_task_id])
in
    #"Added Custom1"
```

## Successor
```powerquery
let
    Source = PREDECESSOR,
    #"Changed Type" = Table.TransformColumnTypes(Source,{{"pred_proj_id", type text}}),
    #"Removed Other Columns" = Table.SelectColumns(#"Changed Type",{"task_id", "pred_task_id", "proj_id", "pred_proj_id", "pred_type", "lag_hr_cnt"}),
    #"Added Custom1" = Table.AddColumn(#"Removed Other Columns", "Task_pred_id_key", each [pred_proj_id]&"."&[pred_task_id]),
    #"Changed Type2" = Table.TransformColumnTypes(#"Added Custom1",{{"Task_pred_id_key", type text}})
in
    #"Changed Type2"
```

## Schema
```powerquery
let
    Source = xer,
    #"Filtered Rows" = Table.SelectRows(Source, each ([Column1] = "ERMHDR")),
    #"Removed Other Columns" = Table.SelectColumns(#"Filtered Rows",{"Column1", "Column2"}),
Source_SQLITE = Odbc.DataSource("driver={SQLite3 ODBC Driver};database="&Path_SQLITE&";longnames=0;timeout=1000;notxn=0;dsn=SQLite Datasource", [HierarchicalNavigation=true]),
    TASK_Table = "sqlite",
    #"Converted to Table" = #table(1, {{TASK_Table}}),
    #"Added Custom" = Table.AddColumn(#"Converted to Table", "Column2", each ""),    
    result = if Connections="XER" then #"Removed Other Columns" else #"Added Custom"
in
    result
```

## Path_Source
```powerquery
let
    result = if Connections="XER" then Path else Path_SQLITE,
    #"Converted to Table" = #table(1, {{result}}),
    #"Renamed Columns" = Table.RenameColumns(#"Converted to Table",{{"Column1", "Path"}})
in
    #"Renamed Columns"
```

## Activity_Status
```powerquery
let
    Source = Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("i45WCvGOd0wuySxLVdJRgjJidcDCzvm5BTmpJSAJOBMq5ZdfElySWFQClAIyFSDs2FgA", BinaryEncoding.Base64), Compression.Deflate)), let _t = ((type text) meta [Serialized.Text = true]) in type table [status_code = _t, Description = _t])
in
    Source
```

## Source
```powerquery
let
    Source = Connections,
    #"Converted to Table" = #table(1, {{Source}}),
    #"Renamed Columns" = Table.RenameColumns(#"Converted to Table",{{"Column1", "Connections"}}),
    #"Changed Type" = Table.TransformColumnTypes(#"Renamed Columns",{{"Connections", type text}})
in
    #"Changed Type"
```

## P6_Calendars
```powerquery
let
    Source = xer,
    #"Filtered Rows" = Table.SelectRows(Source, each [#"Table "] = "CALENDAR" and [Column1] <> "%T"),
    #"Promoted Headers" = Table.PromoteHeaders(#"Filtered Rows"),
    #"Removed Columns" = Table.RemoveColumns(#"Promoted Headers",{"%F"}),
    clndr_id_key = Table.AddColumn(#"Removed Columns", "clndr_id_key", each if [clndr_type] ="CA_Project" then [proj_id]&"."&[clndr_id] else [clndr_id]),
    #"Removed Other Columns" = Table.SelectColumns(clndr_id_key,{"clndr_id", "clndr_name", "day_hr_cnt", "week_hr_cnt", "month_hr_cnt", "year_hr_cnt", "clndr_id_key"}),
    #"Changed Type2" = Table.TransformColumnTypes(#"Removed Other Columns",{{"day_hr_cnt", type number}, {"week_hr_cnt", type number}, {"month_hr_cnt", type number}, {"year_hr_cnt", type number}}),
    Source_SQLITE = Odbc.DataSource("driver={SQLite3 ODBC Driver};database="&Path_SQLITE&";longnames=0;timeout=1000;notxn=0;dsn=SQLite Datasource", [HierarchicalNavigation=true]),
    TASK_Table = Source_SQLITE{[Name="CALENDAR",Kind="Table"]}[Data],
    #"Changed Type" = Table.TransformColumnTypes(TASK_Table,{{"CLNDR_ID", type text}}),
   result = if Connections="XER" then #"Changed Type2" else #"Changed Type"
in
    result
```

