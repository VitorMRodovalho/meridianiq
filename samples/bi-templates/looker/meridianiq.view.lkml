# MeridianIQ — Looker views
# Copyright (c) 2026 Vitor Maia Rodovalho — MIT License
#
# Three views mirror the shape of /api/v1/bi/projects, /dcma-metrics,
# /activities. If you're running a Postgres extract table, adjust the
# sql_table_name on each view to match.

view: projects {
  sql_table_name: public.meridianiq_bi_projects ;;

  dimension: project_id {
    primary_key: yes
    type: string
    sql: ${TABLE}.project_id ;;
  }

  dimension: name {
    type: string
    sql: ${TABLE}.name ;;
  }

  dimension_group: data {
    type: time
    timeframes: [date, week, month, quarter, year]
    sql: ${TABLE}.data_date ;;
  }

  dimension: health_rating {
    type: string
    sql: ${TABLE}.health_rating ;;
  }

  dimension: dcma_is_green {
    type: yesno
    sql: ${TABLE}.dcma_score >= 85 ;;
  }

  measure: project_count {
    type: count_distinct
    sql: ${project_id} ;;
  }

  measure: avg_dcma_score {
    type: average
    sql: ${TABLE}.dcma_score ;;
    value_format_name: decimal_1
  }

  measure: avg_health_score {
    type: average
    sql: ${TABLE}.health_score ;;
    value_format_name: decimal_1
  }

  measure: dcma_green_share {
    type: number
    sql: 1.0 * SUM(CASE WHEN ${TABLE}.dcma_score >= 85 THEN 1 ELSE 0 END)
         / NULLIF(COUNT(*), 0) ;;
    value_format_name: percent_1
  }

  measure: total_negative_float_activities {
    type: sum
    sql: ${TABLE}.negative_float_count ;;
  }

  measure: avg_cpm_length_days {
    type: average
    sql: ${TABLE}.critical_path_length_days ;;
    value_format_name: decimal_1
  }
}

view: dcma_metrics {
  sql_table_name: public.meridianiq_bi_dcma_metrics ;;

  dimension: project_id {
    type: string
    sql: ${TABLE}.project_id ;;
  }

  dimension: metric_number {
    type: number
    sql: ${TABLE}.metric_number ;;
  }

  dimension: metric_name {
    type: string
    sql: ${TABLE}.metric_name ;;
  }

  dimension: value {
    type: number
    sql: ${TABLE}.value ;;
  }

  dimension: threshold {
    type: number
    sql: ${TABLE}.threshold ;;
  }

  dimension: unit {
    type: string
    sql: ${TABLE}.unit ;;
  }

  dimension: passed {
    type: yesno
    sql: ${TABLE}.passed ;;
  }

  dimension: direction {
    type: string
    sql: ${TABLE}.direction ;;
  }

  measure: pass_rate {
    type: number
    sql: 1.0 * SUM(CASE WHEN ${TABLE}.passed THEN 1 ELSE 0 END)
         / NULLIF(COUNT(*), 0) ;;
    value_format_name: percent_1
  }

  measure: avg_value {
    type: average
    sql: ${TABLE}.value ;;
    value_format_name: decimal_2
  }

  measure: failing_count {
    type: count
    filters: [passed: "no"]
  }
}

view: activities {
  sql_table_name: public.meridianiq_bi_activities ;;

  dimension: task_id {
    primary_key: yes
    type: string
    sql: ${TABLE}.task_id ;;
  }

  dimension: project_id {
    type: string
    sql: ${TABLE}.project_id ;;
  }

  dimension: task_code {
    type: string
    sql: ${TABLE}.task_code ;;
  }

  dimension: task_name {
    type: string
    sql: ${TABLE}.task_name ;;
  }

  dimension: task_type {
    type: string
    sql: ${TABLE}.task_type ;;
  }

  dimension: status_code {
    type: string
    sql: ${TABLE}.status_code ;;
  }

  dimension: wbs_id {
    type: string
    sql: ${TABLE}.wbs_id ;;
  }

  dimension: target_duration_hours {
    type: number
    sql: ${TABLE}.target_duration_hours ;;
  }

  dimension: cpm_total_float {
    type: number
    sql: ${TABLE}.cpm_total_float ;;
  }

  dimension: cpm_free_float {
    type: number
    sql: ${TABLE}.cpm_free_float ;;
  }

  dimension: is_critical {
    type: yesno
    sql: ${TABLE}.is_critical ;;
  }

  dimension: has_negative_float {
    type: yesno
    sql: ${TABLE}.cpm_total_float < 0 ;;
  }

  dimension_group: act_start {
    type: time
    timeframes: [date, week, month]
    sql: ${TABLE}.act_start_date ;;
  }

  dimension_group: act_end {
    type: time
    timeframes: [date, week, month]
    sql: ${TABLE}.act_end_date ;;
  }

  measure: activity_count {
    type: count
  }

  measure: critical_activity_ratio {
    type: number
    sql: 1.0 * SUM(CASE WHEN ${TABLE}.is_critical THEN 1 ELSE 0 END)
         / NULLIF(COUNT(*), 0) ;;
    value_format_name: percent_1
  }

  measure: avg_total_float_hours {
    type: average
    sql: ${TABLE}.cpm_total_float ;;
    value_format_name: decimal_1
  }

  measure: negative_float_activity_count {
    type: count
    filters: [has_negative_float: "yes"]
  }
}
