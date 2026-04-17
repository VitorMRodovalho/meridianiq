// MeridianIQ — Power Query M template for Power BI Desktop
// Copyright (c) 2026 Vitor Maia Rodovalho — MIT License
//
// Usage
// -----
// 1. In Power BI Desktop: Home → Transform data → New Parameter
//    Create two text parameters:
//      - BaseUrl   (e.g. https://meridianiq.vitormr.dev  or  http://localhost:8080)
//      - ApiToken  (Supabase JWT; leave empty string "" for anonymous access)
// 2. Home → Get data → Blank Query. Open Advanced Editor and paste the
//    contents of this file. Save. You'll get a record with three query
//    entries: Projects, DCMAMetrics, Activities (ActivitiesFn takes
//    project_id).
// 3. For each of Projects / DCMAMetrics: right-click → Reference. Rename
//    the reference to Projects / DCMAMetrics. Home → Close & Apply.
// 4. For Activities: create a new blank query. Use
//    ActivitiesFn("<project_id>") to pull detail for one project.
//
// Pagination is handled by PageLoop (below) which walks the has_next flag
// until exhausted. MaxPages guards against runaway calls if the server
// misbehaves — bump it only if you have a very large portfolio.

let
    // ---- Parameters (created in Power BI Desktop before pasting this) ----
    _BaseUrl = try BaseUrl otherwise "https://meridianiq.vitormr.dev",
    _Token   = try ApiToken otherwise "",

    // ---- HTTP headers ----
    Headers =
        if _Token = "" then
            [ #"Accept" = "application/json" ]
        else
            [ #"Accept" = "application/json",
              #"Authorization" = "Bearer " & _Token ],

    // ---- One paginated request ----
    FetchPage = (path as text, limit as number, offset as number) as record =>
        let
            url = _BaseUrl & path,
            qs  = [ limit = Number.ToText(limit), offset = Number.ToText(offset) ],
            raw = Web.Contents(url, [ Query = qs, Headers = Headers ]),
            json = Json.Document(raw)
        in
            json,

    // ---- Walk all pages until has_next = false ----
    PageLoop = (path as text) as list =>
        let
            Limit = 500,
            MaxPages = 200,
            GetAll = List.Generate(
                () => [ page = 0, data = FetchPage(path, Limit, 0) ],
                each [page] < MaxPages and Record.Field([data], "items") <> null,
                each [ page = [page] + 1,
                       data = FetchPage(path, Limit, ([page] + 1) * Limit) ],
                each [data][items]
            ),
            Flat = List.Combine(GetAll),
            // Stop at the last non-empty page
            Trimmed = List.Select(Flat, each _ <> null)
        in
            Trimmed,

    // Simpler single-window fetch for the non-generator path (Looker-safe).
    FetchAll = (path as text) as list =>
        let
            first = FetchPage(path, 500, 0),
            total = Record.FieldOrDefault(first[pagination], "total", 0),
            pages = if total <= 500 then { first }
                    else
                        List.Combine({
                            { first },
                            List.Transform(
                                { 1 .. Number.RoundUp(total / 500) - 1 },
                                each FetchPage(path, 500, _ * 500)
                            )
                        }),
            items = List.Combine(List.Transform(pages, each _[items]))
        in
            items,

    // ---- Projects ----
    Projects =
        let
            rows  = FetchAll("/api/v1/bi/projects"),
            table = Table.FromList(rows, Splitter.SplitByNothing(), {"rec"}),
            expanded = Table.ExpandRecordColumn(
                table, "rec",
                { "project_id", "name",
                  "activity_count", "relationship_count", "data_date",
                  "dcma_score", "dcma_passed_count", "dcma_failed_count",
                  "health_score", "health_rating",
                  "critical_path_length_days", "negative_float_count" }
            ),
            typed = Table.TransformColumnTypes(expanded, {
                { "project_id", type text },
                { "name", type text },
                { "activity_count", Int64.Type },
                { "relationship_count", Int64.Type },
                { "data_date", type date },
                { "dcma_score", type number },
                { "dcma_passed_count", Int64.Type },
                { "dcma_failed_count", Int64.Type },
                { "health_score", type number },
                { "health_rating", type text },
                { "critical_path_length_days", type number },
                { "negative_float_count", Int64.Type }
            })
        in
            typed,

    // ---- DCMA metrics (14 rows per project) ----
    DCMAMetrics =
        let
            rows = FetchAll("/api/v1/bi/dcma-metrics"),
            table = Table.FromList(rows, Splitter.SplitByNothing(), {"rec"}),
            expanded = Table.ExpandRecordColumn(
                table, "rec",
                { "project_id", "project_name",
                  "metric_number", "metric_name", "value", "threshold",
                  "unit", "passed", "direction", "description" }
            ),
            typed = Table.TransformColumnTypes(expanded, {
                { "project_id", type text },
                { "project_name", type text },
                { "metric_number", Int64.Type },
                { "metric_name", type text },
                { "value", type number },
                { "threshold", type number },
                { "unit", type text },
                { "passed", type logical },
                { "direction", type text },
                { "description", type text }
            })
        in
            typed,

    // ---- Activities (parameterised by project_id) ----
    ActivitiesFn = (project_id as text) as table =>
        let
            path = "/api/v1/bi/activities?project_id=" & Uri.EscapeDataString(project_id),
            rows = FetchAll(path),
            table = Table.FromList(rows, Splitter.SplitByNothing(), {"rec"}),
            expanded = Table.ExpandRecordColumn(
                table, "rec",
                { "project_id", "task_id", "task_code", "task_name",
                  "task_type", "status_code", "wbs_id",
                  "target_duration_hours", "remaining_duration_hours",
                  "total_float_hours",
                  "act_start_date", "act_end_date",
                  "early_start_date", "early_end_date",
                  "late_start_date", "late_end_date",
                  "cpm_total_float", "cpm_free_float", "is_critical" }
            ),
            typed = Table.TransformColumnTypes(expanded, {
                { "project_id", type text },
                { "task_id", type text },
                { "task_code", type text },
                { "task_name", type text },
                { "task_type", type text },
                { "status_code", type text },
                { "wbs_id", type text },
                { "target_duration_hours", type number },
                { "remaining_duration_hours", type number },
                { "total_float_hours", type number },
                { "act_start_date", type datetime },
                { "act_end_date", type datetime },
                { "early_start_date", type datetime },
                { "early_end_date", type datetime },
                { "late_start_date", type datetime },
                { "late_end_date", type datetime },
                { "cpm_total_float", type number },
                { "cpm_free_float", type number },
                { "is_critical", type logical }
            })
        in
            typed,

    // ---- Export ----
    Export = [
        Projects = Projects,
        DCMAMetrics = DCMAMetrics,
        ActivitiesFn = ActivitiesFn
    ]
in
    Export
