# MeridianIQ — Looker model template
# Copyright (c) 2026 Vitor Maia Rodovalho — MIT License
#
# This model assumes a Postgres connection named `meridianiq_pg` pointing
# at the Supabase database (read-only role, pooler port 6543). If you
# prefer the REST surface, run an extract job that lands the /bi/*
# endpoints into a flat table and point this connection there.
#
# See README.md in this directory for connection setup.

connection: "meridianiq_pg"

include: "meridianiq.view.lkml"

datagroup: meridianiq_daily {
  sql_trigger: SELECT CURRENT_DATE ;;
  max_cache_age: "24 hours"
}

persist_with: meridianiq_daily

explore: projects {
  label: "Projects"
  description: "Portfolio-level schedule KPIs: DCMA, health, CPM duration."

  join: dcma_metrics {
    type: left_outer
    relationship: one_to_many
    sql_on: ${projects.project_id} = ${dcma_metrics.project_id} ;;
  }

  join: activities {
    type: left_outer
    relationship: one_to_many
    sql_on: ${projects.project_id} = ${activities.project_id} ;;
  }
}

explore: dcma_metrics {
  label: "DCMA 14-point"
  description: "One row per (project, metric) — benchmarking surface."

  join: projects {
    type: left_outer
    relationship: many_to_one
    sql_on: ${dcma_metrics.project_id} = ${projects.project_id} ;;
  }
}

explore: activities {
  label: "Activities"
  description: "Activity-level detail with CPM-derived float / criticality."

  join: projects {
    type: left_outer
    relationship: many_to_one
    sql_on: ${activities.project_id} = ${projects.project_id} ;;
  }
}
