/** TypeScript versions of the backend's response shapes (backend/app/schemas.py). */

export type NodeStatus = 'ok' | 'warning' | 'critical' | 'offline'
export type AlertLevel = 'warning' | 'critical'
export type AlertStatus = 'open' | 'acknowledged' | 'resolved'
export type Comparator = 'gt' | 'lt'

/** Field name -> value (raw and derived). */
export type Values = Record<string, number | null>

export interface User {
  id: number
  email: string
  name: string
  role: 'admin' | 'engineer'
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface LatestReading {
  ts: string
  received_at: string
  seq: number | null
  values: Values
  quality_flags: string[]
}

export interface NodeOut {
  id: number
  name: string
  dev_eui: string
  description: string
  ref_lat: number | null
  ref_lon: number | null
  baseline_angle_x: number | null
  baseline_angle_y: number | null
  baseline_slope_angle: number | null
  baseline_set_at: string | null
  expected_interval_s: number
  created_at: string
  is_active: boolean
  status: NodeStatus
  last_seen: string | null
  latest: LatestReading | null
  active_alerts: { warning?: number; critical?: number }
}

export interface NodeDetail extends NodeOut {
  counts: { uplinks: number; flagged: number; missed: number }
}

export interface Alert {
  id: number
  node_id: number
  node_name: string
  rule_id: number | null
  level: AlertLevel
  parameter: string
  value: number | null
  threshold: number | null
  message: string
  status: AlertStatus
  opened_at: string
  acknowledged_by: number | null
  acknowledged_at: string | null
  resolved_at: string | null
  resolution_note: string | null
}

export interface AlertPage {
  items: Alert[]
  total: number
}

export interface DashboardSummary {
  server_time: string
  counts: {
    nodes: number
    online: number
    offline: number
    alerts_active: number
    alerts_new: number
    alerts_warning: number
    alerts_critical: number
  }
  nodes: NodeOut[]
  active_alerts: Alert[]
}

/** One chart point: timestamp plus one value per requested field. */
export interface ChartPoint {
  ts: string
  flagged: boolean
  gap?: boolean
  [field: string]: number | string | boolean | null | undefined
}

export interface ReadingSeries {
  node_id: number
  from: string
  to: string
  bucket_s: number
  fields: string[]
  points: ChartPoint[]
}

export interface MultiSeries {
  field: string
  from: string
  to: string
  bucket_s: number
  series: { node_id: number; name: string; points: { ts: string; v: number | null }[] }[]
}

export interface ReadingRow {
  id: number
  node_id: number
  node_name: string
  ts: string
  received_at: string
  seq: number | null
  values: Values
  quality_flags: string[]
}

export interface ReadingPage {
  items: ReadingRow[]
  total: number
  page: number
  page_size: number
}

/** Fields shared by a new rule and an existing one. */
export interface RuleInput {
  parameter: string
  comparator: Comparator
  warning_threshold: number | null
  critical_threshold: number | null
  warning_offset: number | null
  critical_offset: number | null
  consecutive_readings: number
  enabled: boolean
  justification: string
}

export interface AlertRule extends RuleInput {
  id: number
  node_id: number
  updated_by: number | null
  updated_at: string
  pending_baseline: boolean
}

export interface RuleChange {
  id: number
  rule_id: number
  node_id: number
  action: 'created' | 'updated' | 'deleted' | 'baseline'
  changed_by: number | null
  changed_by_name: string | null
  changed_at: string
  old_values: Record<string, unknown> | null
  new_values: Record<string, unknown> | null
  justification: string
}

export interface AlertDefaults {
  rules: Partial<RuleInput>[]
  parameters: Record<string, { label: string; unit: string }>
  note: string
}

export interface NodeCreated {
  node: NodeOut
  api_key: string
}
